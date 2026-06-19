import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _support import make_fake_curses


class ExamplePluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

    @classmethod
    def tearDownClass(cls):
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def _load_plugin_module(self, plugin_id):
        repo_root = Path(__file__).resolve().parents[1]
        init_path = repo_root / "examples" / "plugins" / plugin_id / "__init__.py"
        module_name = "test_example_plugin_" + plugin_id.replace("-", "_")
        spec = importlib.util.spec_from_file_location(module_name, init_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_todo_plugin_draws_non_dict_items_from_json(self):
        mod = self._load_plugin_module("todo-list")
        with tempfile.TemporaryDirectory() as td:
            data_path = Path(td) / "todos.json"
            data_path.write_text('["raw task", {"text": "ok", "done": true}]', encoding="utf-8")
            with mock.patch.object(mod.Plugin, "_data_path", return_value=str(data_path)):
                plugin = mod.Plugin("Todo", 0, 0, 40, 10)

        with (
            mock.patch.object(mod, "safe_addstr") as safe_addstr,
            mock.patch.object(mod, "theme_attr", return_value=0),
        ):
            plugin.draw_content(None, 0, 0, 40, 10)

        rendered = " ".join(call.args[3] for call in safe_addstr.call_args_list)
        self.assertIn("raw task", rendered)
        self.assertIn("ok", rendered)

    def test_sticky_notes_normalizes_loaded_lines(self):
        mod = self._load_plugin_module("sticky-notes")
        with tempfile.TemporaryDirectory() as td:
            data_path = Path(td) / "notes.json"
            data_path.write_text('{"lines": [1, null, "x"]}', encoding="utf-8")
            with mock.patch.object(mod.Plugin, "_data_path", return_value=str(data_path)):
                plugin = mod.Plugin("Notes", 0, 0, 40, 10)

        self.assertEqual(plugin.lines, ["1", "None", "x"])

    def test_contacts_plugin_draws_non_dict_items_from_json(self):
        mod = self._load_plugin_module("contacts")
        with tempfile.TemporaryDirectory() as td:
            data_path = Path(td) / "contacts.json"
            data_path.write_text('["raw contact", {"name": "Ada"}]', encoding="utf-8")
            with mock.patch.object(mod.Plugin, "_data_path", return_value=str(data_path)):
                plugin = mod.Plugin("Contacts", 0, 0, 40, 10)

        with (
            mock.patch.object(mod, "safe_addstr") as safe_addstr,
            mock.patch.object(mod, "theme_attr", return_value=0),
        ):
            plugin.draw_content(None, 0, 0, 40, 10)

        rendered = " ".join(call.args[3] for call in safe_addstr.call_args_list)
        self.assertIn("raw contact", rendered)
        self.assertIn("Ada", rendered)

    def test_db_browser_quotes_table_names(self):
        mod = self._load_plugin_module("db-browser")
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "example.db"
            con = sqlite3.connect(db_path)
            try:
                con.execute('CREATE TABLE "we""ird" (id INTEGER)')
                con.execute('INSERT INTO "we""ird" VALUES (1)')
                con.commit()
            finally:
                con.close()

            plugin = mod.Plugin("DB", 0, 0, 40, 10, path=str(db_path))
            self.assertIn('we"ird', plugin.tables)
            plugin._load_rows('we"ird')

        self.assertEqual(plugin.rows[0], "id")
        self.assertEqual(plugin.rows[1], "1")


if __name__ == "__main__":
    unittest.main()
