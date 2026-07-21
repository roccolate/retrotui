import types
import unittest
from unittest import mock

from retrotui.apps.wifi_manager import WifiManagerWindow
from retrotui.core.event_loop import _tick_notifications


class IdleRuntimeRegressionTests(unittest.TestCase):
    def test_notification_stack_invalidates_once_until_state_changes(self):
        toast = types.SimpleNamespace(created_at=1.0)
        notifications = types.SimpleNamespace(
            tick=mock.Mock(return_value=False),
            visible_toasts=[toast],
        )
        app = types.SimpleNamespace(_notifications=notifications)

        self.assertTrue(_tick_notifications(app))
        self.assertFalse(_tick_notifications(app))

        notifications.visible_toasts = []
        self.assertTrue(_tick_notifications(app))
        self.assertFalse(_tick_notifications(app))

    def test_notification_expiry_requests_one_redraw(self):
        notifications = types.SimpleNamespace(
            tick=mock.Mock(side_effect=[True, False]),
            visible_toasts=[],
        )
        app = types.SimpleNamespace(_notifications=notifications)

        self.assertTrue(_tick_notifications(app))
        self.assertFalse(_tick_notifications(app))

    def test_scan_worker_uses_captured_executable_after_attribute_change(self):
        with mock.patch(
            "retrotui.apps.wifi_manager.shutil.which",
            return_value=None,
        ):
            win = WifiManagerWindow(0, 0, 60, 20)
        win.nmcli = None
        win._scan_in_progress = True
        rescan = types.SimpleNamespace(returncode=0, stdout="", stderr="")
        listing = types.SimpleNamespace(returncode=0, stdout="", stderr="")

        with mock.patch(
            "retrotui.apps.wifi_manager.subprocess.run",
            side_effect=[rescan, listing],
        ) as run_mock:
            win._scan_worker(None, "/usr/bin/nmcli")

        self.assertEqual(
            run_mock.call_args_list[0].args[0][0],
            "/usr/bin/nmcli",
        )
        self.assertEqual(
            run_mock.call_args_list[1].args[0][0],
            "/usr/bin/nmcli",
        )
        self.assertFalse(win._scan_in_progress)
        self.assertEqual(win._status_msg, "Scan complete.")

    def test_refresh_passes_captured_executable_to_worker_scope(self):
        with mock.patch(
            "retrotui.apps.wifi_manager.shutil.which",
            return_value=None,
        ):
            win = WifiManagerWindow(0, 0, 60, 20)
        win.nmcli = "/usr/bin/nmcli"
        win.radio_on = True

        with mock.patch.object(
            win,
            "_start_worker",
            return_value=object(),
        ) as start:
            win.refresh()

        self.assertEqual(start.call_args.args[1], "/usr/bin/nmcli")


if __name__ == "__main__":
    unittest.main()
