"""End-to-end smoke test against a running, seeded system (stdlib only).

Customer creates a request -> dispatcher triages it, finds an available technician and assigns a visit
-> a second request assigned to the same technician and window must be rejected with 409.
Also checks multi-tenant isolation (a customer of another org cannot read the request).
Exit code is non-zero on any unexpected result. Creates two demo requests; deletes nothing.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("API_URL", "http://localhost:8000") + "/api/v1"
PASSWORD = "Demo-2345!"
TZ = timezone(timedelta(hours=6))  # Asia/Bishkek


def call(method, path, token=None, org=None, body=None):
    headers = {"content-type": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    if org:
        headers["x-organization-id"] = str(org)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as err:
        raw = err.read()
        return err.code, json.loads(raw) if raw else None


def check(condition, message):
    if not condition:
        print(f"FAIL: {message}")
        sys.exit(1)
    print(f"ok: {message}")


def login(email):
    status, data = call("POST", "/auth/login", body={"email": email, "password": PASSWORD})
    check(status == 200, f"login {email}")
    return data["access_token"]


def org_of(token, role):
    _, me = call("GET", "/me", token)
    return next(m["organization_id"] for m in me["memberships"] if m["role"] == role)


def main():
    status, _ = call("GET", "/health/ready")
    check(status == 200, "readiness")

    customer = login("customer1.a@fixflow.test")
    dispatcher = login("dispatcher.a@fixflow.test")
    org = org_of(customer, "customer")
    check(org == org_of(dispatcher, "dispatcher"), "customer and dispatcher share the organization")

    _, categories = call("GET", "/categories", customer, org)
    _, properties = call("GET", "/properties", customer, org)
    body = {
        "title": "Smoke test: boiler loses pressure",
        "description": "Created by scripts/smoke.py to verify the whole flow end to end.",
        "category_id": categories[0]["id"],
        "property_id": properties[0]["id"],
    }
    status, first = call("POST", "/requests", customer, org, body)
    check(status == 201 and first["status"] == "SUBMITTED", "customer creates a request")
    status, second = call("POST", "/requests", customer, org, body)
    check(status == 201, "customer creates a second request")

    for req in (first, second):
        status, _ = call(
            "POST", f"/requests/{req['id']}/transitions", dispatcher, org, {"to_status": "TRIAGED"}
        )
        check(status == 200, f"dispatcher triages #{req['id']}")

    # a weekday visit about five weeks ahead, 10:00-11:00 local time
    day = datetime.now(TZ).replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=35)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    window = {"start_at": day.isoformat(), "end_at": (day + timedelta(hours=1)).isoformat()}

    query = f"?start_at={window['start_at'].replace('+', '%2B')}&end_at={window['end_at'].replace('+', '%2B')}"
    status, candidates = call("GET", f"/requests/{first['id']}/candidates{query}", dispatcher, org)
    check(status == 200, "candidate technicians are listed")
    free = [c for c in candidates if c["available"]]
    check(bool(free), "at least one technician is available for the window")
    technician = free[0]["technician_id"]

    status, _ = call(
        "POST", f"/requests/{first['id']}/assignments", dispatcher, org,
        {**window, "technician_id": technician},
    )
    check(status == 201, "dispatcher assigns the visit")

    status, error = call(
        "POST", f"/requests/{second['id']}/assignments", dispatcher, org,
        {**window, "technician_id": technician},
    )
    check(status == 409, f"double booking is rejected with 409 (got {status}: {error})")

    other = login("customer1.b@fixflow.test")
    other_org = org_of(other, "customer")
    status, _ = call("GET", f"/requests/{first['id']}", other, other_org)
    check(status == 404, "another organization cannot see the request (404)")

    print("smoke: all checks passed")


if __name__ == "__main__":
    main()
