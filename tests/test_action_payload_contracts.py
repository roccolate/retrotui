import unittest

from retrotui.core.actions import (
    ConfigUpdatePayload,
    FileTransferPayload,
    ProcessSignalPayload,
    SaveConfirmPayload,
)


class ActionPayloadContractTests(unittest.TestCase):
    def test_save_confirm_payload_coerces_legacy_mapping(self):
        discard = lambda: None
        payload = SaveConfirmPayload.from_value({
            "on_discard": discard,
            "on_cancel": "not callable",
            "message": 42,
        })

        self.assertIs(payload.on_discard, discard)
        self.assertIsNone(payload.on_cancel)
        self.assertEqual(payload.message, "42")
        self.assertIs(payload["on_discard"], discard)

    def test_file_transfer_payload_supports_legacy_dest_alias(self):
        payload = FileTransferPayload.from_value({
            "source": " /tmp/source ",
            "dest": " /tmp/destination ",
        })

        self.assertEqual(payload.source, "/tmp/source")
        self.assertEqual(payload.destination, "/tmp/destination")
        self.assertEqual(payload.get("destination"), "/tmp/destination")

    def test_process_signal_payload_rejects_invalid_numbers(self):
        payload = ProcessSignalPayload.from_value({
            "pid": "not-a-pid",
            "signal": object(),
            "command": None,
        })

        self.assertEqual(payload.pid, 0)
        self.assertEqual(payload.signal, 15)
        self.assertEqual(payload.command, "")

    def test_config_update_payload_drops_unknown_fields(self):
        payload = ConfigUpdatePayload.from_value({
            "show_hidden": "false",
            "word_wrap_default": "yes",
            "unexpected": "must not reach apply_preferences",
        })

        self.assertEqual(payload.as_kwargs(), {
            "show_hidden": False,
            "word_wrap_default": True,
        })


if __name__ == "__main__":
    unittest.main()
