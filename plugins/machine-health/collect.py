#!/usr/bin/env python3
"""Collect this machine's stats into feeds/machine-health.json, which the Machine Health plugin polls.

Run with --print to see the payload without writing it.
"""
import glob
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time


def run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def first(pattern):
    paths = sorted(glob.glob(pattern))
    return read(paths[0]) if paths else ""


def uptime():
    secs = int(float(read("/proc/uptime").split()[0]))
    days, hours = secs // 86400, secs % 86400 // 3600
    return f"{days}d {hours}h" if days else f"{hours}h {secs % 3600 // 60}m"


def memory_pct():
    info = dict(line.split(":") for line in read("/proc/meminfo").splitlines())
    total, avail = (int(info[k].split()[0]) for k in ("MemTotal", "MemAvailable"))
    return round(100 * (total - avail) / total)


def cpu_temp():
    for hwmon in glob.glob("/sys/class/hwmon/hwmon*"):
        if read(f"{hwmon}/name") in ("k10temp", "coretemp"):
            raw = read(f"{hwmon}/temp1_input")
            if raw:
                return round(int(raw) / 1000)
    return None


def ssd_temp():
    raw = first("/sys/class/nvme/nvme0/hwmon*/temp1_input")
    return round(int(raw) / 1000) if raw else None


def wifi():
    iface = re.search(r"Interface (\S+)", run("iw", "dev"))
    if not iface:
        return {"connected": False}
    link = run("iw", "dev", iface.group(1), "link")
    ssid = re.search(r"SSID: (.+)", link)
    if not ssid:
        return {"connected": False}
    signal = re.search(r"signal: (-?\d+)", link)
    rate = re.search(r"rx bitrate: ([\d.]+)", link)
    return {
        "connected": True,
        "ssid": ssid.group(1).strip(),
        "signal_dbm": int(signal.group(1)) if signal else None,
        "rx_mbps": round(float(rate.group(1))) if rate else None,
    }


def containers():
    out = run("docker", "ps", "-a", "--format", "{{.Names}}\t{{.State}}\t{{.Status}}")
    rows = []
    for line in out.splitlines():
        name, state, status = line.split("\t")
        health = re.search(r"\((healthy|unhealthy|health: starting)\)", status)
        rows.append({
            "name": name,
            "state": state,
            "ok": state == "running" and not (health and health.group(1) == "unhealthy"),
            "status": re.sub(r"\s*\(.*\)", "", status),
        })
    return sorted(rows, key=lambda r: (r["ok"], r["name"]))


def tailscale():
    try:
        data = json.loads(run("tailscale", "status", "--json"))
    except ValueError:
        return []
    peers = [{"name": p["HostName"], "online": bool(p["Online"])} for p in (data.get("Peer") or {}).values()]
    return sorted(peers, key=lambda p: (not p["online"], p["name"]))


def battery():
    pct = first("/sys/class/power_supply/BAT*/capacity")
    if not pct:
        return None
    return {"pct": int(pct), "status": first("/sys/class/power_supply/BAT*/status")}


def collect():
    disk = shutil.disk_usage("/")
    load = read("/proc/loadavg").split()[0]
    rows = containers()
    return {
        "host": socket.gethostname(),
        "updated_at": time.strftime("%H:%M"),
        "uptime": uptime(),
        "load": load,
        "load_pct": round(100 * float(load) / (os.cpu_count() or 1)),
        "mem_pct": memory_pct(),
        "disk_pct": round(100 * disk.used / disk.total),
        "disk_free_gb": round(disk.free / 1e9),
        "cpu_temp": cpu_temp(),
        "ssd_temp": ssd_temp(),
        "battery": battery(),
        "wifi": wifi(),
        "containers": rows,
        "containers_down": sum(not r["ok"] for r in rows),
        "tailscale": tailscale(),
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


def main():
    payload = collect()
    if "--print" in sys.argv:
        print(json.dumps(payload, indent=2))
        return
    write_feed("machine-health", payload)


if __name__ == "__main__":
    main()
