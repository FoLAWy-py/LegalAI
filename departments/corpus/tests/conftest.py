"""Offline fixtures for corpus tests. All data is synthetic (jurisdiction ZZ, SYNTHETIC); no network."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from legalai_corpus.fetch import HttpResponse, PoliteFetcher, RawStore
from legalai_corpus.origins import Origin, OriginStatus

ZZ_HOST = "law.zz.example"
ZZ_BASE = f"https://{ZZ_HOST}"

ZZ_ORIGINS = (
    Origin("zz-official", (ZZ_HOST,), "ZZ", OriginStatus.APPROVED, "synthetic approved origin"),
    Origin("zz-mirror", ("mirror.zz.example",), "ZZ", OriginStatus.REJECTED, "synthetic mirror"),
    Origin("zz-pending", ("pending.zz.example",), "ZZ", OriginStatus.PENDING_PMO, "synthetic pending"),
)


@dataclass
class FakeClock:
    t: float = 1000.0
    sleeps: list[float] = field(default_factory=list)
    start: datetime = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.t += seconds

    def now(self) -> datetime:
        return self.start + timedelta(seconds=self.t)


@dataclass
class FakeTransport:
    """Serves canned responses; records (time, url, headers) of every request."""

    clock: FakeClock
    pages: dict[str, HttpResponse] = field(default_factory=dict)
    calls: list[tuple[float, str, dict[str, str]]] = field(default_factory=list)

    def set(self, url: str, body: bytes, status: int = 200, headers: Mapping[str, str] | None = None) -> None:
        self.pages[url] = HttpResponse(status, url, dict(headers or {}), body)

    def get(self, url: str, headers: Mapping[str, str]) -> HttpResponse:
        self.calls.append((self.clock.t, url, dict(headers)))
        self.clock.t += 0.1  # request duration
        resp = self.pages.get(url)
        if resp is None:
            return HttpResponse(404, url, {}, b"not found")
        etag = resp.headers.get("etag")
        if etag and headers.get("If-None-Match") == etag:
            return HttpResponse(304, url, dict(resp.headers), b"")
        return resp

    def urls(self) -> list[str]:
        return [u for _, u, _ in self.calls]


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def transport(clock: FakeClock) -> FakeTransport:
    t = FakeTransport(clock)
    t.set(
        f"{ZZ_BASE}/robots.txt",
        b"User-agent: *\nDisallow: /private/\n",
        headers={"content-type": "text/plain"},
    )
    return t


@pytest.fixture
def make_fetcher(tmp_path: Path, transport: FakeTransport, clock: FakeClock) -> Callable[..., PoliteFetcher]:
    def make(**kwargs: object) -> PoliteFetcher:
        options: dict[str, object] = {"origins": ZZ_ORIGINS, **kwargs}
        return PoliteFetcher(
            RawStore(tmp_path / "corpus"),
            transport=transport,
            clock=clock,
            **options,  # type: ignore[arg-type]
        )

    return make


def zz_page(body_html: str, title: str = "SYNTHETIC ZZ page") -> bytes:
    """A synthetic official-looking page: navigation noise around a #content container."""
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><title>"
        + title
        + "</title><script>var nav = '第九条 not law';</script></head><body>"
        "<div class='nav'>首页 &gt; 法律</div>"
        "<div id='content' class='text main'>" + body_html + "</div>"
        "<div class='footer'>SYNTHETIC footer 版权所有</div></body></html>"
    ).encode()


def build_pdf(lines: list[tuple[float, float, str]]) -> bytes:
    """Minimal one-page PDF with Helvetica text lines at (x, y). ASCII text only."""
    ops = ["BT", "/F1 12 Tf"]
    for x, y, text in lines:
        esc = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"1 0 0 1 {x} {y} Tm ({esc}) Tj")
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


class ZZHelpers:
    base = ZZ_BASE
    host = ZZ_HOST
    origins = ZZ_ORIGINS

    def page(self, body_html: str, title: str = "SYNTHETIC ZZ page") -> bytes:
        return zz_page(body_html, title)

    def pdf(self, lines: list[tuple[float, float, str]]) -> bytes:
        return build_pdf(lines)


@pytest.fixture
def zz() -> ZZHelpers:
    return ZZHelpers()
