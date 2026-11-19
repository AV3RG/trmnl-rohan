#!/usr/bin/env python3
"""Collect T3 Code thread status for the TRMNL "T3 Threads" plugin.

Reads T3 Code's local state database read-only and writes feeds/t3-threads.json.
  Working = the thread's latest run is still running.
  Ready   = the thread has stopped and is waiting for you (not yet settled or archived).

Usage: collect.py [--print]
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

DB = os.environ.get("T3_STATE_DB", os.path.expanduser("~/.t3/userdata/statev2.sqlite"))

QUERY = """
select t.title, t.payload_json, p.title as project,
       r.status as run_status, r.requested_at, r.completed_at,
       (select count(*) from orchestration_v2_projection_runtime_requests q
         where q.thread_id = t.thread_id and q.status != 'resolved') as pending
  from orchestration_v2_projection_threads t
  left join projection_projects p on p.project_id = t.project_id
  left join orchestration_v2_projection_runs r on r.run_id = (
       select run_id from orchestration_v2_projection_runs
        where thread_id = t.thread_id order by ordinal desc limit 1)
 where t.deleted_at is null and t.archived_at is null
"""


def ago(iso, now):
    if not iso:
        return ""
    secs = max(0, int((now - datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()))
    if secs < 3600:
        return f"{max(1, secs // 60)}m"
    if secs < 86400:
        return f"{secs // 3600}h {secs % 3600 // 60:02d}m"
    return f"{secs // 86400}d"


def collect():
    now = datetime.now(timezone.utc)
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=10)
    db.row_factory = sqlite3.Row
    working, ready, settled = [], [], 0
    for row in db.execute(QUERY):
        meta = json.loads(row["payload_json"])
        if meta.get("lineage", {}).get("parentThreadId"):
            continue  # sub-threads are part of their parent's work
        item = {"title": " ".join(row["title"].split()), "project": "" if row["project"] in (None, "No project") else row["project"]}
        if row["run_status"] == "running" and not row["pending"]:
            item["since"] = row["requested_at"]
            working.append(item)
        elif meta.get("settledAt"):
            settled += 1
        else:
            item["since"] = row["completed_at"] or row["requested_at"] or meta.get("updatedAt")
            item["note"] = ("needs your answer" if row["pending"] else
                            {"failed": "failed", "interrupted": "stopped", "cancelled": "stopped"}.get(row["run_status"], ""))
            ready.append(item)
    db.close()
    working.sort(key=lambda i: i["since"] or "")
    ready.sort(key=lambda i: i["since"] or "", reverse=True)
    for item in working + ready:
        item["ago"] = ago(item.pop("since"), now)
    return {
        "working": working, "ready": ready,
        "working_count": len(working), "ready_count": len(ready), "settled_count": settled,
        "updated_at": datetime.now().strftime("%H:%M"),
    }


def write_feed(name, payload):
    """Write the payload where the server's plugin polls it (feeds/<name>.json), atomically."""
    feeds = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "feeds")
    os.makedirs(feeds, exist_ok=True)
    tmp = os.path.join(feeds, f".{name}.tmp")
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.chmod(tmp, 0o644)
    os.replace(tmp, os.path.join(feeds, f"{name}.json"))
    print(f"wrote feeds/{name}.json")


if __name__ == "__main__":
    data = collect()
    if "--print" in sys.argv:
        print(json.dumps(data, indent=2))
    else:
        write_feed("t3-threads", data)
