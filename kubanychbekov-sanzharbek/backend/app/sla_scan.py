"""Local SLA scanner (SLA-07): finds overdue requests and creates ONE escalation for each.

Run:  python -m app.sla_scan      (safe to run repeatedly or from several processes)
No external scheduler is needed; run it by hand or from cron/Task Scheduler.
"""

from app.db.session import get_sessionmaker
from app.services.sla import scan_and_escalate


def main() -> None:
    with get_sessionmaker()() as db:
        created = scan_and_escalate(db)
    print(f"escalations created: {created}")


if __name__ == "__main__":
    main()
