"""Operator CLI for corpus. The data dir is always an explicit argument (no environment reading here).

python -m legalai_corpus fetch    --data-dir D URL...           # download/cache raw files
python -m legalai_corpus ingest   --data-dir D --manifest M     # fetch + extract + store versions
python -m legalai_corpus verify   --data-dir D                  # re-hash every stored version
python -m legalai_corpus spotcheck --data-dir D --checks C        # offline, independent re-parse
"""

import argparse
import json
import sys
from pathlib import Path

from legalai_corpus.fetch import DEFAULT_USER_AGENT, PoliteFetcher, RawStore


def _corpus_root(data_dir: str) -> Path:
    return Path(data_dir).expanduser().resolve() / "corpus"


def _fetcher(args: argparse.Namespace) -> PoliteFetcher:
    ua = DEFAULT_USER_AGENT if not args.contact else f"{DEFAULT_USER_AGENT} contact: {args.contact}"
    return PoliteFetcher(RawStore(_corpus_root(args.data_dir)), user_agent=ua, on_event=_say)


def _say(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="legalai_corpus")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "ingest", "verify", "spotcheck"):
        p = sub.add_parser(name)
        p.add_argument("--data-dir", required=True)
        p.add_argument("--refresh", action="store_true", help="re-check upstream (conditional GET + hash)")
        p.add_argument("--contact", default=None, help="optional operator contact appended to User-Agent")
        if name == "fetch":
            p.add_argument("urls", nargs="+")
        if name == "ingest":
            p.add_argument("--manifest", required=True)
        if name == "spotcheck":
            p.add_argument("--checks", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "fetch":
        fetcher = _fetcher(args)
        for url in args.urls:
            result = fetcher.fetch(url, refresh=args.refresh)
            print(
                json.dumps({"outcome": result.outcome.value, **result.record.to_json()}, ensure_ascii=False)
            )
        return 0
    if args.cmd == "ingest":
        from legalai_corpus.ingest import ingest_manifest, load_manifest
        from legalai_corpus.store import FileSourceStore

        report = ingest_manifest(
            load_manifest(Path(args.manifest)),
            _fetcher(args),
            FileSourceStore(Path(args.data_dir).expanduser().resolve()),
            refresh=args.refresh,
        )
        print(json.dumps(report, ensure_ascii=False, indent=1))
        return 0
    if args.cmd == "verify":
        from legalai_corpus.store import FileSourceStore

        store = FileSourceStore(Path(args.data_dir).expanduser().resolve())
        count = store.verify_all()
        print(f"verified {count} stored versions: content hashes and contract validation OK")
        return 0
    if args.cmd == "spotcheck":
        from legalai_corpus.spotcheck import run_spotcheck

        results = run_spotcheck(Path(args.data_dir).expanduser().resolve(), Path(args.checks))
        print(json.dumps(results, ensure_ascii=False, indent=1))
        return 0 if all(r["match"] for r in results) else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
