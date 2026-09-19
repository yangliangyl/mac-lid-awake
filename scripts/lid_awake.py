#!/usr/bin/env python3
"""Inspect, repair, or restore Mac closed-lid sleep state with explicit intent."""

import argparse
import datetime
import json
import platform
import plistlib
import re
import subprocess
import time
from pathlib import Path


KNOWN_LID_APPS = {
    "Amphetamine": Path("/Applications/Amphetamine.app"),
    "Amped": Path("/Applications/Amped.app"),
    "StayAwake": Path("/Applications/StayAwake.app"),
    "macowl": Path("/Applications/macowl.app"),
    "LidRun": Path("/Applications/LidRun.app"),
    "Adrafinil": Path("/Applications/Adrafinil.app"),
}
POWER_PROTECT_RULE = Path("/private/etc/sudoers.d/amphetamine_powerProtect")
POWER_PROTECT_SCRIPT = (
    Path.home()
    / "Library/Application Scripts/com.if.Amphetamine/powerProtect.scpt"
)
AMPHETAMINE_PREFS = (
    Path.home()
    / "Library/Containers/com.if.Amphetamine/Data/Library/Preferences/com.if.Amphetamine.plist"
)


def command(args, timeout=12):
    try:
        process = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": process.returncode == 0,
            "out": process.stdout.strip(),
            "error": process.stderr.strip() if process.returncode else "",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "out": "", "error": str(exc)}


def sleep_disabled():
    result = command(["/usr/bin/pmset", "-g"])
    match = re.search(r"^\s*SleepDisabled\s+([01])\s*$", result["out"], re.M)
    return int(match[1]) if result["ok"] and match else None


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
    return command([
        "/usr/bin/osascript", "-e",
        'tell application "Amphetamine" to ' + expression,
    ])


def detected_lid_tools():
    return [name for name, path in KNOWN_LID_APPS.items() if path.is_dir()]


def ownership_check(owner):
    tools = detected_lid_tools()
    if owner != "amphetamine":
        return False, "Repair owner must be explicitly confirmed as amphetamine", tools
    if "Amphetamine" not in tools:
        return False, "Amphetamine is not installed; use onboarding instead of repair", tools
    if len(tools) != 1:
        return False, "Keepawake owner is ambiguous because multiple known tools are installed", tools
    running = command(["/usr/bin/pgrep", "-x", "Amphetamine"])
    if not running["ok"]:
        return False, "Amphetamine is not running", tools
    return True, None, tools


def power_protect_authorized():
    if not POWER_PROTECT_SCRIPT.is_file() or not POWER_PROTECT_RULE.is_file():
        return False, "Power Protect files are incomplete"
    result = command(["/usr/bin/sudo", "-n", "-l", "/usr/bin/pmset"])
    if not result["ok"] or "/usr/bin/pmset" not in result["out"]:
        return False, "Existing Power Protect authorization could not be verified"
    return True, None


def refresh_amphetamine(before, actions, allow_start_session=False):
    """Use Amphetamine's API after ownership is established; return (ok, reason)."""
    try:
        settings = plistlib.loads(AMPHETAMINE_PREFS.read_bytes())
    except (OSError, ValueError, plistlib.InvalidFileException):
        settings = {}
    if settings.get("Enable CDM Warning", True):
        return False, "Closed-display warning may require visible user interaction"

    active = app_command("session is active")
    actions.append({"step": "read_amphetamine_session", **active})
    if not active["ok"] or active["out"] not in ("true", "false"):
        return False, "Cannot determine whether an Amphetamine session is active"

    expressions = []
    if active["out"] == "false":
        if not allow_start_session:
            return False, "Starting an infinite Amphetamine session was not authorized"
        expressions.append(
            "start new session with options {duration:0, interval:0, displaySleepAllowed:true}"
        )
    elif before["lid_closed"] is False:
        expressions.append("disable closed display mode")
    expressions.append("enable closed display mode")

    for expression in expressions:
        result = app_command(expression)
        actions.append({"step": expression, **result})
        if not result["ok"]:
            return False, f"Amphetamine command failed: {expression}"
    return True, None


def _wait_for_value(expected, attempts=3):
    for _ in range(attempts):
        time.sleep(1)
        if sleep_disabled() == expected:
            return True
    return False


def _verify(expected, report, success_status):
    after = snapshot()
    time.sleep(1)
    confirmed = sleep_disabled()
    report.update(after=after, second_sleep_disabled_read=confirmed)
    if after["sleep_disabled"] == expected and confirmed == expected:
        report["status"] = success_status
        return report, 0
    report.update(status="blocked", reason="SleepDisabled could not be confirmed on two reads")
    return report, 2


def _repair(before, report, owner, confirm_repair, allow_start_session, allow_pmset):
    if not confirm_repair:
        report.update(
            status="blocked",
            reason="Repair intent and battery/AC sleep impact were not acknowledged",
        )
        return report, 2

    owner_ok, reason, tools = ownership_check(owner)
    report["detected_lid_tools"] = tools
    if not owner_ok:
        report.update(status="blocked", reason=reason)
        return report, 2

    refreshed, reason = refresh_amphetamine(
        before, report["actions"], allow_start_session=allow_start_session
    )
    if not refreshed:
        report.update(status="blocked", reason=reason)
        return report, 2
    if not _wait_for_value(1):
        if not allow_pmset:
            report.update(
                status="blocked",
                reason="Direct pmset repair was not separately authorized",
            )
            return report, 2
        authorized, reason = power_protect_authorized()
        if not authorized:
            report.update(status="blocked", reason=reason)
            return report, 2
        result = command([
            "/usr/bin/sudo", "-n", "/usr/bin/pmset", "-a", "disablesleep", "1"
        ])
        report["actions"].append({"step": "verified_power_protect_pmset", **result})
        if not result["ok"]:
            report.update(status="blocked", reason="Authorized pmset repair failed")
            return report, 2
    return _verify(1, report, "repaired")


def _restore(before, report, owner, confirm_restore, allow_pmset):
    if not confirm_restore:
        report.update(
            status="blocked",
            reason="Restore intent and battery/AC sleep impact were not acknowledged",
        )
        return report, 2
    owner_ok, reason, tools = ownership_check(owner)
    report["detected_lid_tools"] = tools
    if not owner_ok:
        report.update(status="blocked", reason=reason)
        return report, 2

    disabled = app_command("disable closed display mode")
    report["actions"].append({"step": "disable closed display mode", **disabled})
    if not disabled["ok"]:
        report.update(status="blocked", reason="Amphetamine closed-display mode could not be disabled")
        return report, 2
    if not _wait_for_value(0):
        if not allow_pmset:
            report.update(
                status="blocked",
                reason="Direct pmset restore was not separately authorized",
            )
            return report, 2
        authorized, reason = power_protect_authorized()
        if not authorized:
            report.update(status="blocked", reason=reason)
            return report, 2
        result = command([
            "/usr/bin/sudo", "-n", "/usr/bin/pmset", "-a", "disablesleep", "0"
        ])
        report["actions"].append({"step": "verified_power_protect_pmset_restore", **result})
        if not result["ok"]:
            report.update(status="blocked", reason="Authorized pmset restore failed")
            return report, 2
    return _verify(0, report, "restored")


def execute(
    mode,
    owner=None,
    confirm_repair=False,
    confirm_restore=False,
    allow_start_session=False,
    allow_pmset=False,
):
    report = {"mode": mode, "actions": [], "physical_lid_test": "not_performed"}
    if platform.system() != "Darwin":
        return {**report, "status": "blocked", "reason": "Requires macOS"}, 2

    before = snapshot()
    report["before"] = before
    if before["sleep_disabled"] is None or before["lid_closed"] is None:
        return {
            **report,
            "status": "unknown",
            "reason": "Cannot read sleep setting or laptop lid sensor",
        }, 2

    if mode == "check":
        status = "configured" if before["sleep_disabled"] == 1 else "not_configured"
        return {**report, "status": status}, 0 if status == "configured" else 1
    if mode == "ensure":
        if before["sleep_disabled"] == 1:
            return _verify(1, report, "configured")
        return _repair(
            before, report, owner, confirm_repair, allow_start_session, allow_pmset
        )
    if mode == "restore":
        if before["sleep_disabled"] == 0:
            return _verify(0, report, "restored")
        return _restore(before, report, owner, confirm_restore, allow_pmset)
    raise ValueError(f"unsupported mode: {mode}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("check", "ensure", "restore"))
    parser.add_argument("--owner", choices=("amphetamine",))
    parser.add_argument("--confirm-repair", action="store_true")
    parser.add_argument("--confirm-restore", action="store_true")
    parser.add_argument("--allow-start-session", action="store_true")
    parser.add_argument("--allow-pmset", action="store_true")
    args = parser.parse_args(argv)
    report, code = execute(
        args.mode,
        owner=args.owner,
        confirm_repair=args.confirm_repair,
        confirm_restore=args.confirm_restore,
        allow_start_session=args.allow_start_session,
        allow_pmset=args.allow_pmset,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
