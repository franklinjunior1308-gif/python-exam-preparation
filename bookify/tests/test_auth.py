from app.extensions import db
from app.models import Business, User

from conftest import PW, login


def test_customer_registration(client):
    r = client.post("/register", data={"name": "Jo Doe", "email": "JO@Example.com", "password": PW,
                                       "confirm_password": PW}, follow_redirects=True)
    assert r.status_code == 200
    u = User.query.filter_by(email="jo@example.com").one()
    assert u.role == "customer"
    assert u.password_hash != PW and u.check_password(PW)


def test_duplicate_email_rejected(client, world):
    r = client.post("/register", data={"name": "Dup", "email": "c1@test.test", "password": PW,
                                       "confirm_password": PW}, follow_redirects=True)
    assert b"already exists" in r.data
    assert User.query.filter_by(email="c1@test.test").count() == 1


def test_registration_validation(client):
    r = client.post("/register", data={"name": "X", "email": "bad", "password": "short",
                                       "confirm_password": "nope"}, follow_redirects=True)
    assert b"valid email" in r.data and b"at least 8" in r.data
    assert User.query.count() == 0


def test_business_registration(client):
    r = client.post("/register-business", data={
        "name": "Owner", "email": "owner@biz.test", "password": PW, "confirm_password": PW,
        "business_name": "My Salon", "category": "Beauty salon", "timezone": "Europe/London"}, follow_redirects=True)
    assert r.status_code == 200
    b = Business.query.filter_by(slug="my-salon").one()
    assert b.owner.role == "admin"


def test_business_registration_invalid_timezone(client):
    client.post("/register-business", data={
        "name": "Owner", "email": "o@biz.test", "password": PW, "confirm_password": PW,
        "business_name": "Bad TZ", "timezone": "Mars/Olympus"})
    assert Business.query.count() == 0


def test_login_success_and_logout(client, world):
    r = login(client, "c1@test.test")
    assert b"Hi Cust" in r.data
    r = client.post("/logout", follow_redirects=True)
    assert b"logged out" in r.data
    assert client.get("/dashboard").status_code == 302


def test_login_invalid_credentials(client, world):
    r = login(client, "c1@test.test", "wrong-password")
    assert b"Invalid email or password" in r.data
    r = login(client, "nobody@test.test")
    assert b"Invalid email or password" in r.data


def test_login_redirect_is_not_open(client, world):
    r = client.post("/login?next=https://evil.example/", data={"email": "c1@test.test", "password": PW})
    assert r.status_code == 302 and "evil.example" not in r.headers["Location"]


def test_inactive_account_cannot_login(client, world):
    world.c1.is_active_account = False
    db.session.commit()
    assert b"Invalid email or password" in login(client, "c1@test.test").data
