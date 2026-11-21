"""Load fake demo data.  Usage:  python seed.py [--reset]

Requires the schema to exist first (`flask --app wsgi db upgrade`).
All names, emails and the shared password below are fictional demo values.
"""
import sys
from datetime import time, timedelta

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import (Booking, Business, Notification, Service, StaffMember, User,  # noqa: E402
                        WorkSchedule, staff_services, utcnow)
from app.services.availability import AvailabilityService  # noqa: E402
from app.services.booking_manager import BookingError, BookingManager  # noqa: E402
from app.utils import local_to_utc, to_local  # noqa: E402

DEMO_PASSWORD = "Demo1234!"


def mk_user(name, email, role):
    u = User(name=name, email=email, role=role)
    u.set_password(DEMO_PASSWORD)
    db.session.add(u)
    db.session.flush()
    return u


def mk_business(owner, name, slug, category, desc, address, tz, services, staff_defs):
    b = Business(owner_id=owner.id, name=name, slug=slug, category=category, description=desc,
                 address=address, phone="+44 20 7946 0000", timezone=tz)
    db.session.add(b)
    db.session.flush()
    svc = [Service(business_id=b.id, name=n, description=d, price_cents=p, duration_minutes=m)
           for n, d, p, m in services]
    db.session.add_all(svc)
    db.session.flush()
    members = []
    for name_, email, title, idxs, days in staff_defs:
        u = mk_user(name_, email, "staff")
        sm = StaffMember(business_id=b.id, user_id=u.id, title=title)
        sm.services = [svc[i] for i in idxs]
        db.session.add(sm)
        db.session.flush()
        for d in days:
            db.session.add(WorkSchedule(staff_id=sm.id, weekday=d, start_time=time(9), end_time=time(17)))
        members.append(sm)
    db.session.commit()
    return b, svc, members


def seed():
    admin1 = mk_user("Alex Morgan", "admin@demo.test", "admin")
    admin2 = mk_user("Priya Shah", "admin2@demo.test", "admin")
    cust1 = mk_user("Jamie Rivera", "customer@demo.test", "customer")
    cust2 = mk_user("Sam Okafor", "customer2@demo.test", "customer")

    b1, s1, st1 = mk_business(
        admin1, "Sharp & Co Barbershop", "sharp-and-co", "Barbershop",
        "Classic cuts, hot-towel shaves and beard sculpting in the heart of town.",
        "12 Demo Street, London", "Europe/London",
        [("Classic haircut", "Scissor or clipper cut with a neat finish.", 2500, 30),
         ("Beard trim", "Shape and tidy with hot towel.", 1500, 30),
         ("Haircut + beard", "The full works.", 3800, 60),
         ("Hot towel shave", "Traditional straight-razor shave.", 3000, 45),
         ("Kids cut", "For under-12s.", 1800, 30)],
        [("Dan Whitaker", "dan@demo.test", "Senior barber", [0, 1, 2, 3, 4], [0, 1, 2, 3, 4]),
         ("Mia Chen", "mia@demo.test", "Barber", [0, 1, 2, 4], [1, 2, 3, 4, 5]),
         ("Leo Patel", "leo@demo.test", "Junior barber", [0, 4], [0, 2, 4])])
    b2, s2, st2 = mk_business(
        admin2, "Glow Beauty Studio", "glow-beauty", "Beauty salon",
        "Facials, nails and lashes by friendly specialists.",
        "5 Sample Avenue, London", "Europe/London",
        [("Express facial", "45 minute refresh.", 4500, 45),
         ("Gel manicure", "Long-lasting colour.", 3500, 60)],
        [("Zoe Larsen", "zoe@demo.test", "Beauty therapist", [0, 1], [0, 1, 2, 3, 4])])

    now = utcnow()
    # Past completed bookings (inserted directly: history for stats).
    day = to_local(now, b1.timezone).date() - timedelta(days=1)
    made = 0
    while made < 4:
        if day.weekday() < 5:
            start = local_to_utc(day, time(10 + made), b1.timezone)
            svc = s1[made % 3]
            db.session.add(Booking(business_id=b1.id, customer_id=(cust1 if made % 2 else cust2).id,
                                   service_id=svc.id, staff_id=st1[0].id, start_time=start,
                                   end_time=start + timedelta(minutes=svc.duration_minutes), status="completed",
                                   price_cents=svc.price_cents, duration_minutes=svc.duration_minutes))
            made += 1
        day -= timedelta(days=1)
    db.session.commit()

    # Future bookings via the real engine.
    today = to_local(now, b1.timezone).date()
    created = 0
    for offset in range(1, 10):
        d = today + timedelta(days=offset)
        for svc, cust in ((s1[0], cust1), (s1[2], cust2), (s1[1], cust1)):
            slots = AvailabilityService.get_slots(b1, svc, d)
            if len(slots) > 3 and created < 6:
                pick = slots[(created * 3) % len(slots)]
                try:
                    BookingManager.create_booking(cust, b1, svc.id, pick["staff_ids"][0], pick["start"], "Demo booking")
                    created += 1
                except BookingError:
                    pass
    # One cancelled booking for realism.
    first = Booking.query.filter_by(business_id=b1.id, status="confirmed").order_by(Booking.start_time.desc()).first()
    if first:
        BookingManager.cancel_booking(first.customer, first)
    print("Seeded. Demo accounts (password for all: %s):" % DEMO_PASSWORD)
    for label, email in [("Admin (Sharp & Co)", "admin@demo.test"), ("Admin (Glow)", "admin2@demo.test"),
                         ("Staff", "dan@demo.test"), ("Customer", "customer@demo.test")]:
        print(f"  {label:22s} {email}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        if "--reset" in sys.argv:
            for model in (Notification, Booking, WorkSchedule):
                model.query.delete()
            db.session.execute(staff_services.delete())
            for model in (StaffMember, Service, Business, User):
                model.query.delete()
            db.session.commit()
        if User.query.first():
            print("Database already has data. Use --reset to wipe and reseed.")
            sys.exit(1)
        seed()
