"""Polite, robots-aware, cached downloader for approved origins (REQ-PMO-0002 AC5).

Guarantees:
- Only URLs of APPROVED origins are requested (including every redirect hop). Links are never followed.
- robots.txt of each host is fetched first and obeyed for the configured user agent. A robots.txt that
  is unavailable (any non-200 status, network error, or an HTML page instead of robots rules) blocks the
  host (fail closed, PMO rule).
- At most one request per host every `min_interval` seconds (>= 2 s; robots Crawl-delay wins if larger).
- Raw bytes are stored content-addressed (`raw/objects/<sha256>`) and never modified. Every network
  response is appended to `raw/fetch-log.jsonl`; `raw/latest.json` maps URL -> latest record.
- Re-runs without `refresh` make no request for a cached URL. With `refresh`, a conditional GET is sent
  and the new body's hash is compared to the cached one: outcome UNCHANGED / NOT_MODIFIED / CHANGED.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from urllib.parse import urljoin, urlsplit

from legalai_corpus.origins import ORIGINS, Origin, require_approved

DEFAULT_USER_AGENT = "LegalAI-corpus/0.1 (legal research corpus; rate-limited)"
MIN_ALLOWED_INTERVAL_S = 2.0
DEFAULT_INTERVAL_S = 3.0
MAX_REDIRECTS = 5


@dataclass(frozen=True)
class HttpResponse:
    status: int
    url: str
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    """Performs one HTTP GET without following redirects. Header names in the response are lower-case."""

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


class UrllibTransport:
    """Real network transport (stdlib). Redirects are returned, not followed, so each hop is checked."""

    def __init__(self, timeout_s: float = 60.0) -> None:
        self._timeout = timeout_s
        self._opener = urllib.request.build_opener(_NoRedirect())

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        request = urllib.request.Request(url, headers=dict(headers), method="GET")
        try:
            with self._opener.open(request, timeout=self._timeout) as resp:
                return HttpResponse(
                    resp.status, url, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
                )
        except urllib.error.HTTPError as err:
            body = err.read() if err.fp is not None else b""
            hdrs = {k.lower(): v for k, v in err.headers.items()} if err.headers else {}
            return HttpResponse(err.code, url, hdrs, body)


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...

    def now(self) -> datetime: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)

    def now(self) -> datetime:
        return datetime.now(UTC)


class FetchError(Exception):
    """A download could not be completed authoritatively (HTTP error, robots block, bad redirect)."""


class RobotsDisallowed(FetchError):
    """robots.txt forbids the URL (or could not be read, which is treated as forbidding)."""


class FetchOutcome(StrEnum):
    CACHED = "cached"  # no request made; cached copy returned
    NEW = "new"  # first download of this URL
    UNCHANGED = "unchanged"  # re-downloaded, identical hash
    NOT_MODIFIED = "not-modified"  # server answered 304 to a conditional GET
    CHANGED = "changed"  # re-downloaded, different hash: upstream change detected


@dataclass(frozen=True)
class RawRecord:
    """Provenance of one stored raw object for one URL."""

    url: str
    final_url: str
    sha256: str
    size: int
    content_type: str
    first_retrieved_at: datetime
    last_checked_at: datetime
    etag: str | None = None
    last_modified: str | None = None

    def to_json(self) -> dict[str, object]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "sha256": self.sha256,
            "size": self.size,
            "content_type": self.content_type,
            "first_retrieved_at": self.first_retrieved_at.isoformat(),
            "last_checked_at": self.last_checked_at.isoformat(),
            "etag": self.etag,
            "last_modified": self.last_modified,
        }

    @classmethod
    def from_json(cls, d: Mapping[str, object]) -> "RawRecord":
        def opt(key: str) -> str | None:
            value = d.get(key)
            return None if value is None else str(value)

        return cls(
            url=str(d["url"]),
            final_url=str(d["final_url"]),
            sha256=str(d["sha256"]),
            size=int(str(d["size"])),
            content_type=str(d["content_type"]),
            first_retrieved_at=datetime.fromisoformat(str(d["first_retrieved_at"])),
            last_checked_at=datetime.fromisoformat(str(d["last_checked_at"])),
            etag=opt("etag"),
            last_modified=opt("last_modified"),
        )


@dataclass(frozen=True)
class FetchResult:
    record: RawRecord
    outcome: FetchOutcome
    previous_sha256: str | None = None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


class RawStore:
    """Content-addressed store of raw downloads under `<root>/raw/`."""

    def __init__(self, corpus_root: Path) -> None:
        self.root = corpus_root / "raw"
        self.objects = self.root / "objects"
        self._latest_path = self.root / "latest.json"
        self._log_path = self.root / "fetch-log.jsonl"

    def _latest(self) -> dict[str, dict[str, object]]:
        if not self._latest_path.exists():
            return {}
        data: dict[str, dict[str, object]] = json.loads(self._latest_path.read_text(encoding="utf-8"))
        return data

    def latest(self, url: str) -> RawRecord | None:
        entry = self._latest().get(url)
        return None if entry is None else RawRecord.from_json(entry)

    def put_object(self, data: bytes) -> str:
        digest = sha256_hex(data)
        path = self.objects / digest
        if not path.exists():
            _atomic_write(path, data)
        return digest

    def read_object(self, digest: str) -> bytes:
        """Return raw bytes; raises if the stored object no longer matches its address (tampering)."""
        data = (self.objects / digest).read_bytes()
        if sha256_hex(data) != digest:
            raise FetchError(f"raw object {digest} is corrupt (hash mismatch)")
        return data

    def set_latest(self, record: RawRecord) -> None:
        latest = self._latest()
        latest[record.url] = record.to_json()
        _atomic_write(
            self._latest_path,
            json.dumps(latest, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"),
        )

    def log(self, event: Mapping[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self._log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


@dataclass
class _HostState:
    last_request: float | None = None
    robots: urllib.robotparser.RobotFileParser | None = None
    crawl_delay: float = 0.0
    blocked_reason: str | None = None


@dataclass
class PoliteFetcher:
    """Downloads approved-origin URLs politely and caches them in a RawStore."""

    raw: RawStore
    transport: Transport = field(default_factory=UrllibTransport)
    clock: Clock = field(default_factory=SystemClock)
    user_agent: str = DEFAULT_USER_AGENT
    min_interval_s: float = DEFAULT_INTERVAL_S
    origins: tuple[Origin, ...] = ORIGINS
    on_event: Callable[[str], None] | None = None
    _hosts: dict[str, _HostState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.min_interval_s < MIN_ALLOWED_INTERVAL_S:
            raise ValueError(f"min_interval_s must be >= {MIN_ALLOWED_INTERVAL_S}")
        if not self.user_agent.strip():
            raise ValueError("an identifying User-Agent is required")

    # -- public -------------------------------------------------------------------------------------
    def fetch(self, url: str, refresh: bool = False) -> FetchResult:
        """Return the raw record for `url`, downloading only if not cached or if `refresh` is set."""
        require_approved(url, self.origins)
        cached = self.raw.latest(url)
        if cached is not None and not refresh:
            self.raw.read_object(cached.sha256)  # integrity check of the cached bytes
            return FetchResult(cached, FetchOutcome.CACHED, cached.sha256)

        headers = {"User-Agent": self.user_agent}
        if cached is not None:
            if cached.etag:
                headers["If-None-Match"] = cached.etag
            if cached.last_modified:
                headers["If-Modified-Since"] = cached.last_modified
        resp = self._get_following_redirects(url, headers)
        now = self.clock.now()
        if resp.status == 304 and cached is not None:
            record = RawRecord(**{**cached.__dict__, "last_checked_at": now})
            self.raw.set_latest(record)
            self._log(url, resp, cached.sha256, FetchOutcome.NOT_MODIFIED, now)
            return FetchResult(record, FetchOutcome.NOT_MODIFIED, cached.sha256)
        if resp.status != 200:
            self._log(url, resp, None, None, now)
            raise FetchError(f"GET {url} -> HTTP {resp.status}")
        if not resp.body:
            raise FetchError(f"GET {url} returned an empty body")

        digest = self.raw.put_object(resp.body)
        if cached is not None and cached.sha256 == digest:
            outcome = FetchOutcome.UNCHANGED
            first = cached.first_retrieved_at
        else:
            outcome = FetchOutcome.CHANGED if cached is not None else FetchOutcome.NEW
            first = now
        record = RawRecord(
            url=url,
            final_url=resp.url,
            sha256=digest,
            size=len(resp.body),
            content_type=resp.headers.get("content-type", ""),
            first_retrieved_at=first,
            last_checked_at=now,
            etag=resp.headers.get("etag"),
            last_modified=resp.headers.get("last-modified"),
        )
        self.raw.set_latest(record)
        self._log(url, resp, digest, outcome, now, previous=None if cached is None else cached.sha256)
        return FetchResult(record, outcome, None if cached is None else cached.sha256)

    # -- internals ----------------------------------------------------------------------------------
    def _get_following_redirects(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            require_approved(current, self.origins)
            self._check_robots(current)
            resp = self._request(current, headers)
            if resp.status in (301, 302, 303, 307, 308):
                location = resp.headers.get("location")
                if not location:
                    raise FetchError(f"redirect without Location from {current}")
                current = urljoin(current, location)
                continue
            return resp
        raise FetchError(f"too many redirects from {url}")

    def _host(self, url: str) -> tuple[str, _HostState]:
        parts = urlsplit(url)
        key = f"{parts.scheme}://{parts.netloc}".lower()
        return key, self._hosts.setdefault(key, _HostState())

    def _request(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        _, state = self._host(url)
        interval = max(self.min_interval_s, state.crawl_delay)
        if state.last_request is not None:
            wait = interval - (self.clock.monotonic() - state.last_request)
            if wait > 0:
                self.clock.sleep(wait)
        if self.on_event:
            self.on_event(f"GET {url}")
        try:
            return self.transport.get(url, headers)
        finally:
            state.last_request = self.clock.monotonic()

    def _check_robots(self, url: str) -> None:
        base, state = self._host(url)
        if state.robots is None and state.blocked_reason is None:
            robots_url = base + "/robots.txt"
            try:
                resp = self._request(robots_url, {"User-Agent": self.user_agent})
                hops = 0
                # RFC 9309 §2.3.1.2: follow at least five redirects; only to approved hosts.
                while resp.status in (301, 302, 303, 307, 308) and hops < MAX_REDIRECTS:
                    target = urljoin(resp.url, resp.headers.get("location", ""))
                    require_approved(target, self.origins)
                    resp = self._request(target, {"User-Agent": self.user_agent})
                    hops += 1
            except OSError as err:
                state.blocked_reason = f"robots.txt unreachable: {err}"
            else:
                state.robots, state.crawl_delay, state.blocked_reason = parse_robots(resp, self.user_agent)
            self.raw.log(
                {
                    "kind": "robots",
                    "url": robots_url,
                    "at": self.clock.now().isoformat(),
                    "blocked_reason": state.blocked_reason,
                }
            )
        if state.blocked_reason is not None:
            raise RobotsDisallowed(f"{base}: {state.blocked_reason}")
        assert state.robots is not None
        if not state.robots.can_fetch(self.user_agent, url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")

    def _log(
        self,
        url: str,
        resp: HttpResponse,
        digest: str | None,
        outcome: FetchOutcome | None,
        at: datetime,
        previous: str | None = None,
    ) -> None:
        self.raw.log(
            {
                "kind": "fetch",
                "url": url,
                "final_url": resp.url,
                "status": resp.status,
                "sha256": digest,
                "previous_sha256": previous,
                "outcome": None if outcome is None else outcome.value,
                "at": at.isoformat(),
            }
        )


def parse_robots(
    resp: HttpResponse, user_agent: str
) -> tuple[urllib.robotparser.RobotFileParser | None, float, str | None]:
    """Interpret a robots.txt response. Returns (parser, crawl_delay, blocked_reason).

    Stricter than RFC 9309, by PMO rule (REQ-PMO-0002, 2026-10-30): a robots.txt that is unavailable
    means "not permitted". So any non-200 status blocks the host, and so does a 200 response whose body
    is an HTML page (a soft-404 or homepage served in place of robots.txt), because that is not a
    robots policy at all. Only a real robots file is parsed and obeyed.
    """
    if resp.status != 200:
        return None, 0.0, f"robots.txt HTTP {resp.status}: unavailable, treated as not permitted"
    if _looks_like_html(resp):
        return None, 0.0, "robots.txt is an HTML page (no robots policy): treated as not permitted"
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(resp.body.decode("utf-8", errors="replace").splitlines())
    delay = parser.crawl_delay(user_agent)
    return parser, float(delay) if delay is not None else 0.0, None


def _looks_like_html(resp: HttpResponse) -> bool:
    if "html" in resp.headers.get("content-type", "").lower():
        return True
    head = resp.body[:512].lstrip().lower()
    return head.startswith((b"<!doctype", b"<html", b"<?xml", b"<head", b"<"))
