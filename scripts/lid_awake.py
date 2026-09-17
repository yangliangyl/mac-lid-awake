#!/usr/bin/env python3
"""Inspect or restore Mac closed-lid keepawake using existing local facilities."""

import argparse
import datetime
import json
import platform
import plistlib
import re
import subprocess
import time
from pathlib import Path


def command(args, timeout=12):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"ok": p.returncode == 0, "out": p.stdout.strip(),
                "error": p.stderr.strip() if p.returncode else ""}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "out": "", "error": str(exc)}


def sleep_disabled():
    r = command(["/usr/bin/pmset", "-g"])
    m = re.search(r"^\s*SleepDisabled\s+([01])\s*$", r["out"], re.M)
    return int(m[1]) if r["ok"] and m else None


def snapshot():
    lid = command(["/usr/sbin/ioreg", "-r", "-k", "AppleClamshellState", "-d", "1"])
    match = re.search(r'"AppleClamshellState"\s*=\s*(Yes|No)', lid["out"])
    battery = command(["/usr/bin/pmset", "-g", "batt"])
    assertions = command(["/usr/bin/pmset", "-g", "assertions"])
    return {
        "time": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sleep_disabled": sleep_disabled(),
        "lid_closed": match[1] == "Yes" if lid["ok"] and match else None,
        "power": battery["out"] if battery["ok"] else battery["error"],
        "assertions": assertions["out"] if assertions["ok"] else assertions["error"],
    }


def app_command(expression):
    # Amphetamine's documented scripting API, not GUI scripting/System Events.
    return command(["/usr/bin/osascript", "-e",
                    'tell application "Amphetamine" to ' + expression])


def refresh_amphetamine(before, actions):
    running = command(["/usr/bin/pgrep", "-x", "Amphetamine"])
    prefs = Path.home() / "Library/Containers/com.if.Amphetamine/Data/Library/Preferences/com.if.Amphetamine.plist"
    if not running["ok"]:
        actions.append({"step": "amphetamine", "skipped": "App is not running"})
        return
    try:
        settings = plistlib.loads(prefs.read_bytes())
    except (OSError, ValueError, plistlib.InvalidFileException):
        settings = {}
    if settings.get("Enable CDM Warning", True):
        actions.append({"step": "amphetamine", "skipped": "Closed-display warning may require user interaction"})
        return
    active = app_command("session is active")
    if not active["ok"] or active["out"] not in ("true", "false"):
        actions.append({"step": "read_amphetamine_session", **active})
        return
    expressions = []
    if active["out"] == "false":
        expressions.append("start new session with options {duration:0, interval:0, displaySleepAllowed:true}")
    elif before["lid_closed"] is False:
        expressions.append("disable closed display mode")
    expressions.append("enable closed display mode")
    for expression in expressions:
        result = app_command(expression)
        actions.append({"step": expression, **result})
        if not result["ok"]:
            break


def execute(mode):
    report = {"mode": mode, "actions": [], "physical_lid_test": "not_performed"}
    if platform.system() != "Darwin":
        return {**report, "status": "blocked", "reason": "Requires macOS"}, 2
    before = snapshot()
    report["before"] = before
    if before["sleep_disabled"] is None or before["lid_closed"] is None:
        return {**report, "status": "unknown", "reason": "Cannot read sleep setting or laptop lid sensor"}, 2
    if mode == "check":
        status = "configured" if before["sleep_disabled"] == 1 else "not_configured"
        return {**report, "status": status}, 0 if status == "configured" else 1
    if before["sleep_disabled"] == 0:
        refresh_amphetamine(before, report["actions"])
        # Power Protect applies asynchronously. Allow a bounded settling period.
        for _ in range(3):
            time.sleep(1)
            if sleep_disabled() == 1:
                break
        else:
            authorization = Path("/private/etc/sudoers.d/amphetamine_powerProtect")
            if authorization.is_file():
                result = command(["/usr/bin/sudo", "-n", "/usr/bin/pmset", "-a", "disablesleep", "1"])
                report["actions"].append({"step": "existing_power_protect_authorization", **result})
            else:
                report["actions"].append({"step": "power_protect", "skipped": "Existing authorization not found"})
    time.sleep(1)
    after = snapshot()
    time.sleep(1)
    confirmed = sleep_disabled()
    report.update(after=after, second_sleep_disabled_read=confirmed)
    if after["sleep_disabled"] == 1 and confirmed == 1:
        report["status"] = "repaired" if before["sleep_disabled"] == 0 else "configured"
        return report, 0
    report.update(status="blocked", reason="Keepawake setting could not be confirmed on two reads")
    return report, 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "ensure"))
    args = parser.parse_args()
    report, code = execute(args.mode)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
