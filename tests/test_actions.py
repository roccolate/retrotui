import unittest

from retrotui.core.actions import ActionResult, ActionType, AppAction


class ActionResultTests(unittest.TestCase):
    def test_action_result_stores_type_and_payload(self):
        result = ActionResult(ActionType.OPEN_FILE, "/tmp/demo.txt")
        self.assertEqual(result.type, ActionType.OPEN_FILE)
        self.assertEqual(result.payload, "/tmp/demo.txt")

    def test_action_result_payload_defaults_to_none(self):
        result = ActionResult(ActionType.EXECUTE)
        self.assertEqual(result.type, ActionType.EXECUTE)
        self.assertIsNone(result.payload)

    def test_app_action_parses_legacy_string_values(self):
        self.assertEqual(AppAction("filemanager"), AppAction.FILE_MANAGER)
        self.assertEqual(AppAction("np_save"), AppAction.NP_SAVE)
        self.assertEqual(AppAction("calculator"), AppAction.CALCULATOR)


if __name__ == "__main__":
    unittest.main()
