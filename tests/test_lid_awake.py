#!/usr/bin/env python3

import importlib.util
from pathlib import Path
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lid_awake.py"
SPEC = importlib.util.spec_from_file_location("lid_awake", SCRIPT)
lid = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lid)


def state(value, lid_closed=False):
    return {
        "time": "fixture",
        "sleep_disabled": value,
        "lid_closed": lid_closed,
        "power": "fixture power",
        "assertions": "fixture assertions",
    }


class LidAwakeTests(unittest.TestCase):
    def test_non_mac_stops_before_any_system_command(self):
        with mock.patch.object(lid.platform, "system", return_value="Linux"), \
                mock.patch.object(lid, "command") as command:
            report, code = lid.execute("check")
        self.assertEqual(2, code)
        self.assertEqual("blocked", report["status"])
        command.assert_not_called()

    def test_read_failure_is_unknown_and_never_repairs(self):
        with mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                mock.patch.object(lid, "snapshot", return_value=state(None)), \
                mock.patch.object(lid, "refresh_amphetamine") as refresh:
            report, code = lid.execute("ensure", owner="amphetamine", confirm_repair=True)
        self.assertEqual(2, code)
        self.assertEqual("unknown", report["status"])
        refresh.assert_not_called()

    def test_check_is_read_only(self):
        with mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                mock.patch.object(lid, "snapshot", return_value=state(0)), \
                mock.patch.object(lid, "ownership_check") as owner, \
                mock.patch.object(lid, "refresh_amphetamine") as refresh, \
                mock.patch.object(lid, "app_command") as app:
            report, code = lid.execute("check")
        self.assertEqual(1, code)
        self.assertEqual("not_configured", report["status"])
        owner.assert_not_called()
        refresh.assert_not_called()
        app.assert_not_called()

    def test_already_configured_ensure_performs_no_repair_write(self):
        with mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                mock.patch.object(lid, "snapshot", side_effect=[state(1), state(1)]), \
                mock.patch.object(lid, "sleep_disabled", return_value=1), \
                mock.patch.object(lid.time, "sleep"), \
                mock.patch.object(lid, "ownership_check") as owner, \
                mock.patch.object(lid, "refresh_amphetamine") as refresh:
            report, code = lid.execute("ensure")
        self.assertEqual(0, code)
        self.assertEqual("configured", report["status"])
        owner.assert_not_called()
        refresh.assert_not_called()

    def test_repair_requires_explicit_intent_and_owner(self):
        with mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                mock.patch.object(lid, "snapshot", return_value=state(0)), \
                mock.patch.object(lid, "ownership_check") as owner:
            report, code = lid.execute("ensure", owner="amphetamine")
        self.assertEqual(2, code)
        self.assertIn("not acknowledged", report["reason"])
        owner.assert_not_called()

        with mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                mock.patch.object(lid, "snapshot", return_value=state(0)):
            report, code = lid.execute("ensure", confirm_repair=True)
        self.assertEqual(2, code)
        self.assertIn("explicitly confirmed", report["reason"])

    def test_app_absent_or_ambiguous_owner_stops_before_write(self):
        for tools in ([], ["Amphetamine", "Amped"]):
            with self.subTest(tools=tools), \
                    mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                    mock.patch.object(lid, "snapshot", return_value=state(0)), \
                    mock.patch.object(lid, "detected_lid_tools", return_value=tools), \
                    mock.patch.object(lid, "command") as command, \
                    mock.patch.object(lid, "app_command") as app:
                report, code = lid.execute(
                    "ensure", owner="amphetamine", confirm_repair=True
                )
            self.assertEqual(2, code)
            self.assertEqual("blocked", report["status"])
            command.assert_not_called()
            app.assert_not_called()

    def test_inactive_session_needs_separate_authorization(self):
        actions = []
        responses = [{"ok": True, "out": "false", "error": ""}]
        with mock.patch.object(lid.Path, "read_bytes", return_value=b"fixture"), \
                mock.patch.object(lid.plistlib, "loads", return_value={"Enable CDM Warning": False}), \
                mock.patch.object(lid, "app_command", side_effect=responses) as app:
            ok, reason = lid.refresh_amphetamine(state(0), actions, False)
        self.assertFalse(ok)
        self.assertIn("not authorized", reason)
        self.assertEqual(1, app.call_count)

    def test_old_authorization_file_alone_does_not_allow_pmset(self):
        with mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                mock.patch.object(lid, "snapshot", return_value=state(0)), \
                mock.patch.object(lid, "ownership_check", return_value=(True, None, ["Amphetamine"])), \
                mock.patch.object(lid, "refresh_amphetamine", return_value=(True, None)), \
                mock.patch.object(lid, "_wait_for_value", return_value=False), \
                mock.patch.object(lid, "power_protect_authorized") as auth, \
                mock.patch.object(lid, "command") as command:
            report, code = lid.execute(
                "ensure",
                owner="amphetamine",
                confirm_repair=True,
                allow_start_session=True,
                allow_pmset=False,
            )
        self.assertEqual(2, code)
        self.assertIn("not separately authorized", report["reason"])
        auth.assert_not_called()
        command.assert_not_called()

    def test_missing_power_protect_authorization_stops(self):
        with mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                mock.patch.object(lid, "snapshot", return_value=state(0)), \
                mock.patch.object(lid, "ownership_check", return_value=(True, None, ["Amphetamine"])), \
                mock.patch.object(lid, "refresh_amphetamine", return_value=(True, None)), \
                mock.patch.object(lid, "_wait_for_value", return_value=False), \
                mock.patch.object(lid, "power_protect_authorized", return_value=(False, "fixture missing")), \
                mock.patch.object(lid, "command") as command:
            report, code = lid.execute(
                "ensure",
                owner="amphetamine",
                confirm_repair=True,
                allow_start_session=True,
                allow_pmset=True,
            )
        self.assertEqual(2, code)
        self.assertEqual("fixture missing", report["reason"])
        command.assert_not_called()

    def test_post_repair_second_read_failure_is_not_success(self):
        with mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                mock.patch.object(lid, "snapshot", side_effect=[state(0), state(1)]), \
                mock.patch.object(lid, "ownership_check", return_value=(True, None, ["Amphetamine"])), \
                mock.patch.object(lid, "refresh_amphetamine", return_value=(True, None)), \
                mock.patch.object(lid, "_wait_for_value", return_value=True), \
                mock.patch.object(lid, "sleep_disabled", return_value=0), \
                mock.patch.object(lid.time, "sleep"):
            report, code = lid.execute(
                "ensure",
                owner="amphetamine",
                confirm_repair=True,
                allow_start_session=True,
            )
        self.assertEqual(2, code)
        self.assertEqual("blocked", report["status"])

    def test_restore_never_starts_a_session(self):
        calls = []

        def fake_app(expression):
            calls.append(expression)
            return {"ok": True, "out": "", "error": ""}

        with mock.patch.object(lid.platform, "system", return_value="Darwin"), \
                mock.patch.object(lid, "snapshot", side_effect=[state(1), state(0)]), \
                mock.patch.object(lid, "ownership_check", return_value=(True, None, ["Amphetamine"])), \
                mock.patch.object(lid, "app_command", side_effect=fake_app), \
                mock.patch.object(lid, "_wait_for_value", return_value=True), \
                mock.patch.object(lid, "sleep_disabled", return_value=0), \
                mock.patch.object(lid.time, "sleep"):
            report, code = lid.execute(
                "restore", owner="amphetamine", confirm_restore=True
            )
        self.assertEqual(0, code)
        self.assertEqual("restored", report["status"])
        self.assertEqual(["disable closed display mode"], calls)
        self.assertFalse(any("start new session" in expression for expression in calls))


if __name__ == "__main__":
    unittest.main()
