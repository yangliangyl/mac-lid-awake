#!/usr/bin/env python3
"""Read-only onboarding audit for Mac closed-lid keepawake dependencies."""

import json
import platform
import plistlib
import re
import subprocess
from pathlib import Path


def run(args, timeout=15):
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def main():
    report = {"platform": platform.system(), "ready_for_onboarding": False}
    if platform.system() != "Darwin":
        report["reason"] = "Requires macOS"
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    _, ioreg, _ = run(["/usr/sbin/ioreg", "-r", "-k", "AppleClamshellState", "-d", "1"])
    lid = re.search(r'"AppleClamshellState"\s*=\s*(Yes|No)', ioreg)
    report["laptop_lid_sensor"] = lid is not None
    report["lid_closed"] = lid.group(1) == "Yes" if lid else None

    _, hardware, _ = run(["/usr/sbin/system_profiler", "SPHardwareDataType"])
    chip = re.search(r"^\s*Chip:\s*(.+)$", hardware, re.M)
    model = re.search(r"^\s*Model Name:\s*(.+)$", hardware, re.M)
    report["model"] = model.group(1) if model else None
    report["chip"] = chip.group(1) if chip else None
    report["apple_silicon"] = bool(chip and chip.group(1).startswith("Apple"))

    app = Path("/Applications/Amphetamine.app")
    report["amphetamine"] = {"installed": app.is_dir()}
    if app.is_dir():
        info = app / "Contents/Info.plist"
        try:
            plist = plistlib.loads(info.read_bytes())
            report["amphetamine"].update(
                bundle_id=plist.get("CFBundleIdentifier"),
                version=plist.get("CFBundleShortVersionString"),
            )
        except (OSError, ValueError, plistlib.InvalidFileException):
            report["amphetamine"]["metadata_error"] = "Cannot read Info.plist"
    report["amphetamine"]["running"] = run(["/usr/bin/pgrep", "-x", "Amphetamine"])[0] == 0

    known_apps = {
        "Amped": Path("/Applications/Amped.app"),
        "StayAwake": Path("/Applications/StayAwake.app"),
        "macowl": Path("/Applications/macowl.app"),
        "LidRun": Path("/Applications/LidRun.app"),
        "Adrafinil": Path("/Applications/Adrafinil.app"),
    }
    detected = [name for name, path in known_apps.items() if path.is_dir()]
    if app.is_dir():
        detected.insert(0, "Amphetamine")
    report["known_lid_tools"] = detected
    report["ownership_conflict"] = len(detected) > 1

    script = Path.home() / "Library/Application Scripts/com.if.Amphetamine/powerProtect.scpt"
    rule = Path("/private/etc/sudoers.d/amphetamine_powerProtect")
    auth_code, auth_out, _ = run(["/usr/bin/sudo", "-n", "-l", "/usr/bin/pmset"])
    report["power_protect"] = {
        "script_present": script.is_file(),
        "authorization_present": rule.is_file(),
        "pmset_authorized": auth_code == 0 and "/usr/bin/pmset" in auth_out,
    }

    _, pmset, _ = run(["/usr/bin/pmset", "-g"])
    state = re.search(r"^\s*SleepDisabled\s+([01])\s*$", pmset, re.M)
    report["sleep_disabled"] = int(state.group(1)) if state else None
    _, custom, _ = run(["/usr/bin/pmset", "-g", "custom"])
    report["power_policy"] = {
        "battery_sleep_minutes": _policy_value(custom, "Battery Power", "sleep"),
        "ac_sleep_minutes": _policy_value(custom, "AC Power", "sleep"),
    }
    batt_code, batt, batt_error = run(["/usr/bin/pmset", "-g", "batt"])
    report["power"] = batt if batt_code == 0 else batt_error
    report["ready_for_onboarding"] = report["laptop_lid_sensor"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ready_for_onboarding"] else 2


def _policy_value(text, section, key):
    match = re.search(
        rf"^{re.escape(section)}:\s*$([\s\S]*?)(?=^[^\s].*:\s*$|\Z)", text, re.M
    )
    if not match:
        return None
    value = re.search(rf"^\s*{re.escape(key)}\s+(\d+)\s*$", match.group(1), re.M)
    return int(value.group(1)) if value else None


if __name__ == "__main__":
    raise SystemExit(main())
