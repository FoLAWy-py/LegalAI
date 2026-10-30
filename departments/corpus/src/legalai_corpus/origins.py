"""Registry of assessed origins. The fetcher refuses every host that is not listed here as APPROVED.

The authoritative assessment (terms, robots, reasons) is `departments/corpus/docs/origins.md`; this module
mirrors its decisions so they are enforced in code. Changing a status here without updating origins.md
(and, for approval, satisfying the PMO rule in REQ-PMO-0002 §2.1) is a defect.
"""

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit


class OriginStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING_PMO = "pending-pmo"


@dataclass(frozen=True)
class Origin:
    """One assessed origin. `hosts` are exact, lower-case host names (no wildcards)."""

    key: str
    hosts: tuple[str, ...]
    jurisdiction: str
    status: OriginStatus
    reason: str
    schemes: tuple[str, ...] = ("https",)


class OriginNotApproved(Exception):
    """Raised when a URL's host is unknown or not approved. Downloads from it are forbidden."""


ORIGINS: tuple[Origin, ...] = (
    Origin(
        key="cn-npc-www",
        hosts=("www.npc.gov.cn",),
        jurisdiction="CN",
        status=OriginStatus.APPROVED,
        reason="NPC official site (hosted by the NPCSC General Office); publishes law texts and the NPCSC "
        "Gazette. robots.txt disallows only YisouSpider; no terms restricting retrieval. HTTPS handshake "
        "fails from the corpus host, so http is allowed (see origins.md).",
        schemes=("http", "https"),
    ),
    Origin(
        key="cn-spc",
        hosts=("www.court.gov.cn",),
        jurisdiction="CN",
        status=OriginStatus.APPROVED,
        reason="SPC official site; no robots.txt (soft-404 HTML); no terms beyond a copyright notice.",
    ),
    Origin(
        key="cn-csrc",
        hosts=("www.csrc.gov.cn",),
        jurisdiction="CN",
        status=OriginStatus.APPROVED,
        reason="CSRC official site; no robots.txt; legal statement forbids altering, selling or leasing "
        "site information (we store unaltered raw files and do not sell).",
    ),
    Origin(
        key="cn-npc-flk",
        hosts=("flk.npc.gov.cn",),
        jurisdiction="CN",
        status=OriginStatus.REJECTED,
        reason="robots.txt: 'User-agent: * Disallow: /' and an explicit ban on automated collection.",
    ),
    Origin(
        key="cn-spp",
        hosts=("www.spp.gov.cn",),
        jurisdiction="CN",
        status=OriginStatus.PENDING_PMO,
        reason="Footer forbids reposting, excerpting or mirroring without written authorisation.",
    ),
    Origin(
        key="cn-wenshu",
        hosts=("wenshu.court.gov.cn",),
        jurisdiction="CN",
        status=OriginStatus.REJECTED,
        reason="Rejected for v1 by PMO rule; robots.txt also disallows all other agents.",
    ),
    Origin(
        key="us-govinfo",
        hosts=("www.govinfo.gov", "api.govinfo.gov"),
        jurisdiction="US",
        status=OriginStatus.PENDING_PMO,
        reason="Assessed on paper only; no US download under REQ-PMO-0002.",
    ),
    Origin(
        key="us-ecfr",
        hosts=("www.ecfr.gov",),
        jurisdiction="US",
        status=OriginStatus.PENDING_PMO,
        reason="Assessed on paper only; no US download under REQ-PMO-0002.",
    ),
    Origin(
        key="us-uscode",
        hosts=("uscode.house.gov",),
        jurisdiction="US",
        status=OriginStatus.PENDING_PMO,
        reason="Assessed on paper only; no US download under REQ-PMO-0002.",
    ),
    Origin(
        key="us-uscourts",
        hosts=("www.uscourts.gov",),
        jurisdiction="US",
        status=OriginStatus.PENDING_PMO,
        reason="Assessed on paper only; no US download under REQ-PMO-0002.",
    ),
    Origin(
        key="us-courtlistener",
        hosts=("www.courtlistener.com",),
        jurisdiction="US",
        status=OriginStatus.REJECTED,
        reason="Aggregator (not the issuing body) under the PMO rule; case law is out of scope.",
    ),
)


def origin_for_url(url: str, origins: tuple[Origin, ...] = ORIGINS) -> Origin:
    """Return the origin whose host list contains the URL's host. Raises OriginNotApproved if none."""
    host = (urlsplit(url).hostname or "").lower()
    for origin in origins:
        if host in origin.hosts:
            return origin
    raise OriginNotApproved(f"host {host!r} is not an assessed origin")


def require_approved(url: str, origins: tuple[Origin, ...] = ORIGINS) -> Origin:
    """Return the APPROVED origin serving `url`, or raise OriginNotApproved (wrong host, status or scheme)."""
    origin = origin_for_url(url, origins)
    if origin.status is not OriginStatus.APPROVED:
        raise OriginNotApproved(f"origin {origin.key} is {origin.status.value}: {origin.reason}")
    scheme = urlsplit(url).scheme.lower()
    if scheme not in origin.schemes:
        raise OriginNotApproved(f"scheme {scheme!r} not allowed for origin {origin.key}")
    return origin
