"""Whole main scenario through the real HTTP API, as each role (what the web and the phone do).

Run against a seeded system:  API_URL=http://localhost:8000 python scripts/e2e_scenario.py
It creates one completed demo request (and one cancelled helper request) each time it runs.
"""

import json
import os
import struct
import sys
import urllib.error
import urllib.request
import uuid
import zlib
from datetime import datetime, timedelta, timezone

BASE = os.environ.get("API_URL", "http://localhost:8000") + "/api/v1"
PW = "Demo-2345!"
TZ = timezone(timedelta(hours=6))


def call(method, path, token=None, org=None, body=None, raw=None, ctype=None):
    headers = {}
    if token:
        headers["authorization"] = f"Bearer {token}"
    if org:
        headers["x-organization-id"] = str(org)
    data = raw
    if raw is None and body is not None:
        data = json.dumps(body).encode()
        headers["content-type"] = "application/json"
    if ctype:
        headers["content-type"] = ctype
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            b = resp.read()
            return resp.status, (json.loads(b) if b and resp.headers.get_content_type() == "application/json" else b)
    except urllib.error.HTTPError as e:
        b = e.read()
        try:
            return e.code, json.loads(b)
        except Exception:
            return e.code, b


def ok(cond, msg, extra=""):
    print(("ok:   " if cond else "FAIL: ") + msg + (f"  {extra}" if extra and not cond else ""))
    if not cond:
        sys.exit(1)


def login(email):
    s, d = call("POST", "/auth/login", body={"email": email, "password": PW})
    ok(s == 200, f"login {email}")
    return d["access_token"]


def org_of(tok, role):
    _, me = call("GET", "/me", tok)
    return next(m["organization_id"] for m in me["memberships"] if m["role"] == role)


def png():
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    rows = b"".join(b"\x00" + b"\xdd\x33\x33" * 32 for _ in range(24))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 32, 24, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def upload(tok, org, rid, cmd):
    boundary = "----fx" + uuid.uuid4().hex
    parts = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="client_command_id"\r\n\r\n{cmd}\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="purpose"\r\n\r\nevidence\r\n'
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="p.png"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode() + png() + f"\r\n--{boundary}--\r\n".encode()
    return call("POST", f"/requests/{rid}/attachments", tok, org, raw=parts, ctype=f"multipart/form-data; boundary={boundary}")


customer = login("customer1.a@fixflow.test")
dispatcher = login("dispatcher.a@fixflow.test")
tech = login("tech2.a@fixflow.test")
org = org_of(customer, "customer")
torg = org_of(tech, "technician")
ok(org == torg, "customer, dispatcher and technician share the organization")

_, cats = call("GET", "/categories", customer, org)
hvac = next(c for c in cats if c["name"] == "HVAC")
_, props = call("GET", "/properties", customer, org)

# 1. customer creates a request with a photo
s, req = call("POST", "/requests", customer, org, {
    "title": "E2E scenario: air conditioner not cooling",
    "description": "Created by the end-to-end scenario script for the phone check.",
    "category_id": hvac["id"], "property_id": props[0]["id"]})
ok(s == 201 and req["status"] == "SUBMITTED", "1. customer creates an HVAC request", req)
rid = req["id"]
s, att = upload(customer, org, rid, uuid.uuid4().hex)
ok(s == 201, "1. customer attaches a photo", att)

# 2. dispatcher triages and assigns Azamat (tech2.a) through Smart Assign
s, _ = call("POST", f"/requests/{rid}/transitions", dispatcher, org, {"to_status": "TRIAGED"})
ok(s == 200, "2. dispatcher triages")
s, sugg = call("GET", f"/requests/{rid}/suggestions", dispatcher, org)
ok(s == 200 and sugg, "2. Smart Assign returns suggestions")
azamat = next((x for x in sugg if "Azamat" in x.get("full_name", x.get("technician_name", ""))), None)
print("      suggestions:", [(x.get("full_name") or x.get("technician_name"), x.get("score")) for x in sugg][:4])
pick = azamat or sugg[0]
if not azamat:
    print("      note: Azamat is not in the top suggestions; assigning him directly")
_, techs = call("GET", "/technicians", dispatcher, org)
azamat_id = next(t["id"] for t in techs if t["email"] == "tech2.a@fixflow.test")
day = datetime.now(TZ).replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=21 + uuid.uuid4().int % 150)
while day.weekday() >= 5:
    day += timedelta(days=1)
win = {"start_at": day.isoformat(), "end_at": (day + timedelta(hours=1)).isoformat(), "technician_id": azamat_id}
s, asg = call("POST", f"/requests/{rid}/assignments", dispatcher, org, win)
ok(s == 201, "2. dispatcher assigns Azamat", asg)
s, req2 = call("POST", "/requests", customer, org, {"title": "E2E second request", "description": "To provoke a double booking conflict.", "category_id": hvac["id"], "property_id": props[0]["id"]})
call("POST", f"/requests/{req2['id']}/transitions", dispatcher, org, {"to_status": "TRIAGED"})
s, asg2 = call("POST", f"/requests/{req2['id']}/assignments", dispatcher, org, win)
ok(s == 409, "2. while the first visit is active, booking the same technician at the same time is refused (409)", (s, asg2))
call("POST", f"/assignments/{asg2['id']}/unassign", dispatcher, org) if s == 201 else None
call("POST", f"/requests/{req2['id']}/transitions", dispatcher, org, {"to_status": "CANCELED", "reason": "e2e cleanup"})

# 3. phone: the task appears in /my/tasks
s, tasks = call("GET", "/my/tasks", tech, org)
mine = next((t for t in tasks if t["request_id"] == rid), None)
ok(s == 200 and mine is not None, "3. the task appears in the technician's list", [t.get("request_id") for t in tasks][:6])
for to in ("ACCEPTED", "IN_PROGRESS"):
    s, r = call("POST", f"/requests/{rid}/transitions", tech, org, {"to_status": to})
    ok(s == 200, f"3. technician -> {to}", r)

# 4. note + photo, replayed with the same command id (offline retry) -> exactly one copy
cmd = uuid.uuid4().hex
body = {"body": "Checked the compressor, refrigerant is low.", "visibility": "public", "client_command_id": cmd}
s1, n1 = call("POST", f"/requests/{rid}/notes", tech, org, body)
s2, n2 = call("POST", f"/requests/{rid}/notes", tech, org, body)
ok(s1 == 201 and s2 in (200, 201) and n1["id"] == n2["id"], "4. note retried with the same id is stored once", (s1, n1, s2, n2))
_, notes = call("GET", f"/requests/{rid}/notes", dispatcher, org)
ok(sum(1 for n in notes if n["body"].startswith("Checked the compressor")) == 1, "4. the web sees exactly one copy")
pc = uuid.uuid4().hex
s1, p1 = upload(tech, org, rid, pc)
s2, p2 = upload(tech, org, rid, pc)
ok(s1 == 201 and s2 in (200, 201) and p1["id"] == p2["id"], "4. photo retried with the same id is stored once")

# 5. complete
s, r = call("POST", f"/requests/{rid}/complete", tech, org, {"summary": "Refilled refrigerant and tested cooling, all fine.", "client_command_id": uuid.uuid4().hex})
ok(s == 200 and r["status"] == "COMPLETED", "5. technician completes the work", r)

# 6. dispatcher sees it, customer rates, double booking gives 409
_, seen = call("GET", f"/requests/{rid}", dispatcher, org)
ok(seen["status"] == "COMPLETED", "6. dispatcher sees COMPLETED", seen.get("status"))
ok(seen.get("sla") and seen["sla"].get("finished"), "6. SLA result is final")
_, hist = call("GET", f"/requests/{rid}/history", dispatcher, org)
print("      history:", [h["to_status"] for h in hist])
s, fb = call("POST", f"/requests/{rid}/feedback", customer, org, {"rating": 5, "comment": "Fast and clean."})
ok(s == 201 and fb["rating"] == 5, "6. customer rates 5/5", fb)
s, fb2 = call("POST", f"/requests/{rid}/feedback", customer, org, {"rating": 4})
ok(s == 409, "6. a second rating is refused (409)")
print("E2E scenario: all checks passed, request id", rid)
