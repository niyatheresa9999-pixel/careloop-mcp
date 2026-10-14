"""CareLoop MCP - voice-first medication check-ins and family alerts for caregivers.
Self-hosted MCP server, Streamable HTTP. Not medical advice."""
import json, os, uuid
from datetime import datetime, timedelta, time
from mcp.server.fastmcp import FastMCP

DB = os.environ.get("CARELOOP_DB", "careloop.json")
GRACE = timedelta(minutes=60)      # a dose is 'due' for 60 min, then 'overdue'
WINDOW = timedelta(hours=4)        # a late dose still counts for its slot
mcp = FastMCP("CareLoop", host=os.environ.get("HOST", "0.0.0.0"),
              port=int(os.environ.get("PORT", "8000")))

def _load():
    try:
        with open(DB) as f:
            return json.load(f)
    except Exception:
        return {"meds": [], "logs": [], "notes": [], "alerts": []}

def _save(d):
    with open(DB, "w") as f:
        json.dump(d, f, indent=2)

def _now(s):
    return datetime.fromisoformat(s) if s else datetime.now()

def _slots(m, day):
    return [datetime.combine(day, time.fromisoformat(t)) for t in m["times"]]

def _covered(d, m, slot):
    return any(l["med_id"] == m["id"] and l["status"] == "taken"
               and slot - GRACE <= datetime.fromisoformat(l["ts"]) <= slot + WINDOW
               for l in d["logs"])

def _meds(d, person):
    return [m for m in d["meds"] if m["person"].lower() == person.lower()]

def _status(d, person, now):
    out = []
    for m in _meds(d, person):
        for s in _slots(m, now.date()):
            if s > now:
                continue
            st = ("taken" if _covered(d, m, s)
                  else "overdue" if now > s + GRACE else "due")
            out.append({"med": m["name"], "dose": m["dose"],
                        "slot": s.strftime("%H:%M"), "status": st})
    return out

def _escalate(d, person, msg):
    d["alerts"].append({"ts": datetime.now().isoformat(), "person": person, "msg": msg})
    arn = os.environ.get("SNS_TOPIC_ARN")   # optional: real SMS/email via Amazon SNS
    if arn:
        try:
            import boto3
            boto3.client("sns").publish(TopicArn=arn, Message=msg)
        except Exception:
            pass

@mcp.tool()
def add_medication(person: str, name: str, dose: str, times: str) -> str:
    """Add a medication. times is comma separated 24h, e.g. '08:00,20:00'."""
    d = _load()
    d["meds"].append({"id": uuid.uuid4().hex[:6], "person": person, "name": name,
                      "dose": dose, "times": [t.strip() for t in times.split(",")]})
    _save(d)
    return f"Added {name} {dose} for {person} at {times}."

@mcp.tool()
def log_dose(person: str, name: str, status: str = "taken", when: str = "") -> str:
    """Record that a dose was taken or skipped. when is optional ISO time."""
    d = _load()
    for m in _meds(d, person):
        if m["name"].lower() == name.lower():
            d["logs"].append({"med_id": m["id"], "status": status, "ts": _now(when).isoformat()})
            _save(d)
            return f"Logged {name} as {status} for {person}."
    return f"I don't have {name} on {person}'s list."

@mcp.tool()
def check_status(person: str, now: str = "") -> str:
    """What has been taken, is due, or is overdue today for this person."""
    rows = _status(_load(), person, _now(now))
    if not rows:
        return f"No doses scheduled yet today for {person}."
    return "\n".join(f"{r['slot']} {r['med']} {r['dose']}: {r['status']}" for r in rows)

@mcp.tool()
def log_note(person: str, note: str) -> str:
    """Save a wellbeing note, e.g. 'felt dizzy after lunch' or 'good mood today'."""
    d = _load()
    d["notes"].append({"person": person, "note": note, "ts": datetime.now().isoformat()})
    _save(d)
    return "Note saved."

@mcp.tool()
def family_digest(person: str, now: str = "") -> str:
    """Spoken-style summary for the family. Alerts family if 2+ doses are overdue."""
    d = _load()
    n = _now(now)
    rows = _status(d, person, n)
    overdue = [r for r in rows if r["status"] == "overdue"]
    taken = [r for r in rows if r["status"] == "taken"]
    msg = f"{person}: {len(taken)} doses taken, {len(overdue)} overdue so far today."
    if overdue:
        msg += " Overdue: " + ", ".join(f"{r['med']} at {r['slot']}" for r in overdue) + "."
    if len(overdue) >= 2:
        _escalate(d, person, f"CareLoop alert: {person} has {len(overdue)} overdue doses. Please check in.")
        msg += " I've alerted the family."
    notes = [x for x in d["notes"] if x["person"].lower() == person.lower()]
    if notes:
        msg += f" Latest note: {notes[-1]['note']}."
    _save(d)
    return msg

@mcp.tool()
def doctor_report(person: str, days: int = 7, now: str = "") -> str:
    """Adherence summary per medication plus notes, for a doctor visit."""
    d = _load()
    n = _now(now)
    lines = [f"{days}-day report for {person}:"]
    for m in _meds(d, person):
        due = got = 0
        for k in range(days):
            for s in _slots(m, (n - timedelta(days=k)).date()):
                if s + GRACE < n:
                    due += 1
                    got += _covered(d, m, s)
        lines.append(f"- {m['name']} {m['dose']}: {got}/{due} doses ({round(100*got/due) if due else 0}%)")
    cutoff = (n - timedelta(days=days)).isoformat()
    for x in d["notes"]:
        if x["person"].lower() == person.lower() and x["ts"] >= cutoff:
            lines.append(f"- Note {x['ts'][:10]}: {x['note']}")
    return "\n".join(lines)

@mcp.tool()
def load_demo_data(person: str = "Dad") -> str:
    """Seed demo meds and a week of history (some missed doses) for the video."""
    d = _load()
    for name, dose, times in [("Metformin", "500mg", ["08:00", "20:00"]), ("Lisinopril", "10mg", ["08:00"])]:
        d["meds"].append({"id": uuid.uuid4().hex[:6], "person": person, "name": name, "dose": dose, "times": times})
    i = 0
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    for m in d["meds"]:
        for k in range(1, 8):
            for s in _slots(m, (today - timedelta(days=k)).date()):
                i += 1
                if i % 5:
                    d["logs"].append({"med_id": m["id"], "status": "taken",
                                      "ts": (s + timedelta(minutes=10)).isoformat()})
    d["notes"].append({"person": person, "note": "felt dizzy in the morning",
                       "ts": (today - timedelta(days=2)).isoformat()})
    _save(d)
    return f"Demo data loaded for {person}."

if __name__ == "__main__":
    mcp.run(transport="streamable-http")  # http://HOST:PORT/mcp
