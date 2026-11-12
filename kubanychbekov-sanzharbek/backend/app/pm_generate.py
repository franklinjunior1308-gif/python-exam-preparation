"""Local generator of preventive-maintenance requests (PM-05).

Run:  python -m app.pm_generate                 (all organizations, events up to today)
      python -m app.pm_generate --as-of 2026-12-31
Safe to repeat: events that already exist are skipped, never duplicated.
"""

import argparse
from datetime import date

from app.db.session import get_sessionmaker
from app.services.maintenance import generate_everywhere


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, default=None, help="YYYY-MM-DD")
    args = parser.parse_args()
    with get_sessionmaker()() as db:
        for name, day, created, skipped in generate_everywhere(db, args.as_of):
            print(f"{name}: up to {day} -> created {created}, already existed {skipped}")


if __name__ == "__main__":
    main()
