"""
scripts/admin.py
----------------
Operator CLI for the tables the public API can only write to.

USAGE
-----
  python scripts/admin.py stats
  python scripts/admin.py reports [--status open] [--limit 20]
  python scripts/admin.py resolve <report-id> [--status resolved|dismissed|open]

Runs against DATABASE_URL. This is the "admin CLI" from the specification:
no browser session, no user account, just a shell on the host.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend import db  # noqa: E402

VALID_STATUSES = ("open", "resolved", "dismissed")


def _human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def cmd_stats(_args) -> int:
    stats = db.count_stats()
    print(f"Landmarks:            {stats['landmarks']}")
    print(f"Model classes:        {stats['classes']} ({stats['validated_classes']} validated)")
    print(f"Published photos:     {stats['published_photos']}")
    print(f"Itineraries:          {stats['itineraries']} ({stats['itineraries_last_7_days']} in 7 days)")
    print(f"Reports:              {stats['reports']} ({stats['open_reports']} open, "
          f"{stats['reports_last_7_days']} in 7 days)")
    print(f"Database size:        {_human_bytes(stats['database_bytes'])}")
    return 0


def cmd_reports(args) -> int:
    status = args.status
    if status is not None and status not in VALID_STATUSES:
        print(f"--status must be one of {VALID_STATUSES}", file=sys.stderr)
        return 2

    rows = db.list_reports(status=status, limit=args.limit)
    if not rows:
        print("No reports.")
        return 0

    for row in rows:
        landmark = row["landmark_name"] or row["landmark_id"] or "(no landmark)"
        print(f"{row['id']}  {row['created_at'][:19]}  {row['status']:<9} "
              f"{row['category']:<12} {landmark}")
        print(f"    {row['message']}")
    return 0


def cmd_resolve(args) -> int:
    if args.status not in VALID_STATUSES:
        print(f"--status must be one of {VALID_STATUSES}", file=sys.stderr)
        return 2
    updated = db.update_report_status(args.report_id, args.status)
    if updated is None:
        print(f"Report not found: {args.report_id}", file=sys.stderr)
        return 1
    print(json.dumps(updated, indent=2))
    return 0


def main() -> int:
    if not db.is_configured():
        print("DATABASE_URL is not set.", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(description="Pushkinskaya Street Explorer admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="print row counts and database size").set_defaults(func=cmd_stats)

    reports = sub.add_parser("reports", help="list problem reports")
    reports.add_argument("--status", choices=VALID_STATUSES, default=None)
    reports.add_argument("--limit", type=int, default=20)
    reports.set_defaults(func=cmd_reports)

    resolve = sub.add_parser("resolve", help="change a report's status")
    resolve.add_argument("report_id")
    resolve.add_argument("--status", choices=VALID_STATUSES, default="resolved")
    resolve.set_defaults(func=cmd_resolve)

    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:  # pragma: no cover - operator-facing message
        print(f"Database error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
