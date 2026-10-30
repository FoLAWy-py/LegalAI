"""Downloader (REQ-PMO-0002 AC5): approved origins only, robots, rate limit, cache, change detection."""

import json
from itertools import pairwise

import pytest

from legalai_corpus import FetchOutcome, OriginNotApproved, RobotsDisallowed
from legalai_corpus.fetch import MIN_ALLOWED_INTERVAL_S, FetchError


def test_refuses_unknown_rejected_and_pending_origins_without_any_request(make_fetcher, transport) -> None:
    fetcher = make_fetcher()
    for url in (
        "https://unknown.example/a",
        "https://mirror.zz.example/a",
        "https://pending.zz.example/a",
        "http://law.zz.example/a",  # scheme not allowed for this origin
    ):
        with pytest.raises(OriginNotApproved):
            fetcher.fetch(url)
    assert transport.calls == []


def test_refuses_cached_copy_once_origin_is_no_longer_approved(make_fetcher, transport, zz) -> None:
    transport.set(f"{zz.base}/doc", b"x")
    make_fetcher().fetch(f"{zz.base}/doc")
    downgraded = tuple(
        o
        if o.key != "zz-official"
        else type(o)(o.key, o.hosts, o.jurisdiction, type(o.status)("pending-pmo"), "")
        for o in zz.origins
    )
    with pytest.raises(OriginNotApproved):
        make_fetcher(origins=downgraded).fetch(f"{zz.base}/doc")


def test_robots_rules_are_obeyed(make_fetcher, transport, zz) -> None:
    with pytest.raises(RobotsDisallowed):
        make_fetcher().fetch(f"{zz.base}/private/x")
    assert transport.urls() == [f"{zz.base}/robots.txt"]


@pytest.mark.parametrize(
    ("status", "body", "ctype"),
    [
        (404, b"not found", "text/html"),
        (403, b"forbidden", "text/html"),
        (503, b"busy", "text/plain"),
        (200, b"<!DOCTYPE html><html><body>home</body></html>", "text/html"),  # soft-404 / homepage
        (200, b"<html><body>home</body></html>", "text/plain"),  # HTML with a wrong content type
    ],
)
def test_unavailable_robots_fails_closed(make_fetcher, transport, zz, status, body, ctype) -> None:
    transport.set(f"{zz.base}/robots.txt", body, status=status, headers={"content-type": ctype})
    transport.set(f"{zz.base}/doc", b"x")
    with pytest.raises(RobotsDisallowed):
        make_fetcher().fetch(f"{zz.base}/doc")
    assert f"{zz.base}/doc" not in transport.urls()


def test_rate_limit_spaces_requests_per_host(make_fetcher, transport, clock, zz) -> None:
    for i in range(3):
        transport.set(f"{zz.base}/d{i}", b"x%d" % i)
    fetcher = make_fetcher(min_interval_s=3.0)
    for i in range(3):
        fetcher.fetch(f"{zz.base}/d{i}")
    times = [t for t, _, _ in transport.calls]
    assert len(times) == 4  # robots + 3 documents
    assert all(b - a >= 3.0 - 1e-9 for a, b in pairwise(times))


def test_crawl_delay_larger_than_interval_wins(make_fetcher, transport, zz) -> None:
    transport.set(f"{zz.base}/robots.txt", b"User-agent: *\nCrawl-delay: 7\nDisallow:\n")
    transport.set(f"{zz.base}/a", b"a")
    transport.set(f"{zz.base}/b", b"b")
    fetcher = make_fetcher()
    fetcher.fetch(f"{zz.base}/a")
    fetcher.fetch(f"{zz.base}/b")
    times = [t for t, _, _ in transport.calls]
    assert times[2] - times[1] >= 7.0 - 1e-9


def test_interval_below_floor_and_empty_user_agent_rejected(make_fetcher) -> None:
    with pytest.raises(ValueError):
        make_fetcher(min_interval_s=MIN_ALLOWED_INTERVAL_S - 0.5)
    with pytest.raises(ValueError):
        make_fetcher(user_agent="  ")


def test_identifying_user_agent_sent(make_fetcher, transport, zz) -> None:
    transport.set(f"{zz.base}/doc", b"x")
    make_fetcher(user_agent="LegalAI-corpus/test").fetch(f"{zz.base}/doc")
    assert all(h["User-Agent"] == "LegalAI-corpus/test" for _, _, h in transport.calls)


def test_rerun_uses_cache_without_network(make_fetcher, transport, zz, tmp_path) -> None:
    transport.set(f"{zz.base}/doc", b"official bytes")
    first = make_fetcher().fetch(f"{zz.base}/doc")
    assert first.outcome is FetchOutcome.NEW
    n_calls = len(transport.calls)
    second = make_fetcher().fetch(f"{zz.base}/doc")  # a fresh process: new fetcher, same data dir
    assert second.outcome is FetchOutcome.CACHED
    assert second.record.sha256 == first.record.sha256
    assert len(transport.calls) == n_calls
    obj = tmp_path / "corpus" / "raw" / "objects" / first.record.sha256
    assert obj.read_bytes() == b"official bytes"


def test_refresh_detects_unchanged_changed_and_not_modified(make_fetcher, transport, zz, tmp_path) -> None:
    url = f"{zz.base}/doc"
    transport.set(url, b"v1")
    fetcher = make_fetcher()
    v1 = fetcher.fetch(url)
    assert fetcher.fetch(url, refresh=True).outcome is FetchOutcome.UNCHANGED
    transport.set(url, b"v2")
    changed = fetcher.fetch(url, refresh=True)
    assert changed.outcome is FetchOutcome.CHANGED
    assert changed.previous_sha256 == v1.record.sha256
    assert changed.record.sha256 != v1.record.sha256
    # the old raw object is kept (immutable history)
    assert (tmp_path / "corpus" / "raw" / "objects" / v1.record.sha256).exists()
    transport.set(url, b"v2", headers={"etag": '"e2"'})
    fetcher.fetch(url, refresh=True)
    nm = fetcher.fetch(url, refresh=True)
    assert nm.outcome is FetchOutcome.NOT_MODIFIED
    assert transport.calls[-1][2].get("If-None-Match") == '"e2"'
    log = [json.loads(line) for line in (tmp_path / "corpus/raw/fetch-log.jsonl").read_text().splitlines()]
    assert [e["outcome"] for e in log if e["kind"] == "fetch"] == [
        "new",
        "unchanged",
        "changed",
        "unchanged",
        "not-modified",
    ]


def test_redirect_to_unapproved_host_refused(make_fetcher, transport, zz) -> None:
    transport.set(f"{zz.base}/moved", b"", status=302, headers={"location": "https://mirror.zz.example/x"})
    with pytest.raises(OriginNotApproved):
        make_fetcher().fetch(f"{zz.base}/moved")


def test_redirect_within_origin_followed_and_final_url_recorded(make_fetcher, transport, zz) -> None:
    transport.set(f"{zz.base}/old", b"", status=301, headers={"location": "/new"})
    transport.set(f"{zz.base}/new", b"body")
    result = make_fetcher().fetch(f"{zz.base}/old")
    assert result.record.final_url == f"{zz.base}/new"


def test_http_error_raises(make_fetcher, transport, zz) -> None:
    with pytest.raises(FetchError):
        make_fetcher().fetch(f"{zz.base}/missing")


def test_corrupt_cached_object_detected(make_fetcher, transport, zz, tmp_path) -> None:
    transport.set(f"{zz.base}/doc", b"original")
    rec = make_fetcher().fetch(f"{zz.base}/doc").record
    (tmp_path / "corpus" / "raw" / "objects" / rec.sha256).write_bytes(b"tampered")
    with pytest.raises(FetchError):
        make_fetcher().fetch(f"{zz.base}/doc")
