"""Desktop Icons and Menu Editor windows."""

import curses

from dataclasses import replace

from ..constants import ICONS, ICONS_ASCII
from ..core.actions import ActionResult, ActionType, AppAction
from ..ui.window import Window
from ..utils import draw_box, normalize_key_code, safe_addstr, theme_attr


class _BaseSelectionEditorWindow(Window):
    """Shared checkbox editor UI for icon/menu visibility."""

    MIN_WIDTH = 58
    MIN_HEIGHT = 20
    LIST_PADDING = 4
    CATEGORY_ORDER = ("File", "Apps", "Games", "Edit", "Help", "Plugins")

    def __init__(self, title, x, y, w, h, app):
        super().__init__(title, x, y, max(self.MIN_WIDTH, w), max(self.MIN_HEIGHT, h), resizable=False)
        self.app = app
        self.in_list = True
        self.selected_button = 0
        self.buttons = ["Save", "Cancel"]
        self._tab_ranges = []
        self._btn_ranges = []
        self._help_text = ""
        self._status_text = ""
        self._load_choices()

    def _load_choices(self):
        hidden = self._current_hidden_set()
        choices = {}
        for entry in self._iter_catalog_entries():
            category = str(entry.get("category") or "Apps")
            label = str(entry.get("label") or "")
            value = str(entry.get("value") or "").strip().lower()
            if not label or not value:
                continue
            choices.setdefault(category, []).append([label, value, value not in hidden])

        for cat_entries in choices.values():
            cat_entries.sort(key=lambda item: item[0].lower())

        ordered = [cat for cat in self.CATEGORY_ORDER if cat in choices]
        ordered.extend(sorted(cat for cat in choices if cat not in set(ordered)))
        self.categories = ordered
        self.choices = {cat: choices.get(cat, []) for cat in self.categories}
        self.active_cat_idx = 0
        self.sel_indices = {cat: 0 for cat in self.categories}
        self.offsets = {cat: 0 for cat in self.categories}

    def _iter_catalog_entries(self):
        raise NotImplementedError

    def _current_hidden_set(self):
        raise NotImplementedError

    def _save_hidden_values(self, hidden_values):
        raise NotImplementedError

    def _current_category(self):
        if not self.categories:
            return None
        idx = max(0, min(self.active_cat_idx, len(self.categories) - 1))
        self.active_cat_idx = idx
        return self.categories[idx]

    def _visible_rows(self):
        return max(4, self.h - 10)

    def _list_rect(self):
        list_x = self.x + 2
        list_y = self.y + 6
        list_w = max(12, self.w - self.LIST_PADDING)
        list_h = self._visible_rows()
        return list_x, list_y, list_w, list_h

    def _set_config_field(self, field_name, value):
        """Persist field on frozen dataclass config and test doubles."""
        try:
            self.app.config = replace(self.app.config, **{field_name: value})
            return
        except TypeError:
            pass
        setattr(self.app.config, field_name, value)

    def _selected_hidden_values(self):
        hidden_values = []
        for cat in self.categories:
            for _, value, checked in self.choices.get(cat, []):
                if not checked:
                    hidden_values.append(value)
        return sorted(set(hidden_values))

    def _move_selection(self, direction):
        category = self._current_category()
        if category is None:
            return
        items = self.choices.get(category, [])
        if not items:
            return
        sel_idx = self.sel_indices[category]
        if direction < 0:
            sel_idx = max(0, sel_idx - 1)
        else:
            sel_idx = min(len(items) - 1, sel_idx + 1)
        self.sel_indices[category] = sel_idx

        offset = self.offsets[category]
        visible_rows = self._visible_rows()
        if sel_idx < offset:
            offset = sel_idx
        elif sel_idx >= offset + visible_rows:
            offset = sel_idx - visible_rows + 1
        self.offsets[category] = max(0, offset)

    def _toggle_current_item(self):
        category = self._current_category()
        if category is None:
            return
        items = self.choices.get(category, [])
        if not items:
            return
        idx = self.sel_indices[category]
        items[idx][2] = not items[idx][2]

    def _activate_button(self):
        if self.selected_button != 0:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)

        hidden_values = self._selected_hidden_values()
        try:
            self._save_hidden_values(hidden_values)
        except OSError as exc:
            return ActionResult(ActionType.SAVE_ERROR, str(exc))
        return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)

    def draw(self, stdscr):
        if not self.visible:
            return

        super().draw(stdscr)
        body_attr = theme_attr("window_body")
        selected_attr = body_attr | curses.A_REVERSE
        bold_attr = body_attr | curses.A_BOLD

        safe_addstr(stdscr, self.y + 1, self.x + 2, self._help_text.ljust(self.w - 4)[: self.w - 4], body_attr)
        safe_addstr(stdscr, self.y + 2, self.x + 2, self._status_text.ljust(self.w - 4)[: self.w - 4], body_attr)

        # Tabs
        tab_y = self.y + 4
        tab_x = self.x + 2
        self._tab_ranges = []
        for idx, cat in enumerate(self.categories):
            tab = f" {cat} "
            attr = selected_attr if (self.active and self.in_list and idx == self.active_cat_idx) else bold_attr
            safe_addstr(stdscr, tab_y, tab_x, tab, attr)
            self._tab_ranges.append((tab_x, tab_x + len(tab), idx))
            tab_x += len(tab) + 1

        list_x, list_y, list_w, list_h = self._list_rect()
        draw_box(stdscr, list_y - 1, list_x - 1, list_h + 2, list_w + 2, body_attr, double=False)

        category = self._current_category()
        items = self.choices.get(category, []) if category else []
        offset = self.offsets.get(category, 0) if category else 0
        selected_idx = self.sel_indices.get(category, 0) if category else 0

        for row in range(list_h):
            idx = offset + row
            if idx < len(items):
                label, _, checked = items[idx]
                mark = "[x]" if checked else "[ ]"
                text = f" {mark} {label}"
                is_focused = self.in_list and self.active and idx == selected_idx
                attr = selected_attr if is_focused else body_attr
                safe_addstr(stdscr, list_y + row, list_x, text.ljust(list_w)[:list_w], attr)
            else:
                safe_addstr(stdscr, list_y + row, list_x, " " * list_w, body_attr)

        if len(items) > list_h:
            sb_x = list_x + list_w - 1
            thumb = int(offset / max(1, len(items) - list_h) * (list_h - 1))
            for row in range(list_h):
                ch = "█" if row == thumb else "░"
                safe_addstr(stdscr, list_y + row, sb_x, ch, theme_attr("scrollbar"))

        # Buttons
        btn_y = self.y + self.h - 2
        total_w = sum(len(btn) + 4 for btn in self.buttons) + (len(self.buttons) - 1) * 2
        btn_x = self.x + max(0, (self.w - total_w) // 2)
        self._btn_ranges = []
        for idx, text in enumerate(self.buttons):
            label = f"[ {text} ]"
            attr = theme_attr("button_selected") if (self.active and not self.in_list and idx == self.selected_button) else theme_attr("button")
            safe_addstr(stdscr, btn_y, btn_x, label, attr)
            self._btn_ranges.append((btn_x, btn_x + len(label), idx))
            btn_x += len(label) + 2

    def handle_click(self, mx, my):
        if my == self.y + 4:
            for start_x, end_x, idx in self._tab_ranges:
                if start_x <= mx < end_x:
                    self.in_list = True
                    self.active_cat_idx = idx
                    return True

        list_x, list_y, list_w, list_h = self._list_rect()
        if list_x <= mx < list_x + list_w and list_y <= my < list_y + list_h:
            category = self._current_category()
            if category is None:
                return True
            click_idx = self.offsets[category] + (my - list_y)
            items = self.choices.get(category, [])
            if click_idx < len(items):
                self.in_list = True
                self.sel_indices[category] = click_idx
                items[click_idx][2] = not items[click_idx][2]
            return True

        if my == self.y + self.h - 2:
            for start_x, end_x, idx in self._btn_ranges:
                if start_x <= mx < end_x:
                    self.in_list = False
                    self.selected_button = idx
                    return self._activate_button()
        return False

    def handle_key(self, key):
        key_code = normalize_key_code(key)
        if key_code == 27:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)

        if key_code == 9:  # Tab
            self.in_list = not self.in_list
            return None

        if self.in_list and key_code in (curses.KEY_LEFT, curses.KEY_RIGHT):
            if key_code == curses.KEY_LEFT:
                self.active_cat_idx = max(0, self.active_cat_idx - 1)
            else:
                self.active_cat_idx = min(len(self.categories) - 1, self.active_cat_idx + 1)
            return None

        if not self.in_list and key_code in (curses.KEY_LEFT, curses.KEY_RIGHT):
            if key_code == curses.KEY_LEFT:
                self.selected_button = max(0, self.selected_button - 1)
            else:
                self.selected_button = min(len(self.buttons) - 1, self.selected_button + 1)
            return None

        if key_code == curses.KEY_UP:
            if not self.in_list:
                self.in_list = True
                return None
            self._move_selection(-1)
            return None

        if key_code == curses.KEY_DOWN:
            if not self.in_list:
                self.in_list = True
                return None
            self._move_selection(1)
            return None

        if key_code in (32, 10, 13, curses.KEY_ENTER):
            if self.in_list:
                self._toggle_current_item()
                return None
            return self._activate_button()
        return None


class DesktopIconManagerWindow(_BaseSelectionEditorWindow):
    """Desktop icon visibility editor (apps, games, plugins)."""

    def __init__(self, x, y, w, h, app):
        super().__init__("Desktop Icons", x, y, w, h, app)
        self._help_text = "Choose what appears on desktop icons."
        self._status_text = "Includes apps, games and plugins."

    def _iter_catalog_entries(self):
        if hasattr(self.app, "_build_desktop_icon_catalog"):
            icons = self.app._build_desktop_icon_catalog()
        else:
            icons = ICONS if getattr(self.app, "use_unicode", True) else ICONS_ASCII
        entries = []
        for icon in icons:
            label = str(icon.get("label", ""))
            category = str(icon.get("category", "Apps"))
            if hasattr(self.app, "_icon_visibility_key"):
                value = self.app._icon_visibility_key(icon)
            else:
                value = label.strip().lower()
            entries.append({"category": category, "label": label, "value": value})
        return entries

    def _current_hidden_set(self):
        if hasattr(self.app, "_get_hidden_icon_labels"):
            return set(self.app._get_hidden_icon_labels())
        raw = str(getattr(self.app.config, "hidden_icons", "") or "")
        return {token.strip().lower() for token in raw.split(",") if token.strip()}

    def _save_hidden_values(self, hidden_values):
        self._set_config_field("hidden_icons", ",".join(hidden_values))
        self.app.persist_config()
        self.app.refresh_icons()


class IconsWindow(DesktopIconManagerWindow):
    """Standalone Icons app: icon style + desktop icon visibility."""

    STYLE_OPTIONS = (
        ("default", "Classic"),
        ("mini", "Mini"),
        ("braille", "Braille"),
        ("codex", "Codex"),
    )

    def __init__(self, x, y, w, h, app):
        super().__init__(x, y, w, h, app)
        self.title = "Icons"
        self._help_text = "Choose icon style and which desktop icons are visible."
        self._status_text = "Tip: F2 or S toggles icon style."
        current = str(getattr(app, "icon_style", "default") or "default").strip().lower()
        self._style_index = 0
        for idx, (key, _) in enumerate(self.STYLE_OPTIONS):
            if key == current:
                self._style_index = idx
                break

    def _cycle_style(self, delta=1):
        self._style_index = (self._style_index + delta) % len(self.STYLE_OPTIONS)

    def _apply_selected_style(self):
        style_key = self.STYLE_OPTIONS[self._style_index][0]
        setter = getattr(self.app, "set_icon_style", None)
        if callable(setter):
            setter(style_key)
        else:
            self.app.icon_style = style_key
            refresher = getattr(self.app, "refresh_icons", None)
            if callable(refresher):
                refresher()

    def _list_rect(self):
        """Leave room for style preview above the checkbox list."""
        list_x = self.x + 2
        list_y = self.y + 11
        list_w = max(12, self.w - self.LIST_PADDING)
        list_h = max(4, self.h - 15)
        return list_x, list_y, list_w, list_h

    def _preview_symbol(self, style_key):
        getter = getattr(self.app, "icon_style_preview_symbol", None)
        if callable(getter):
            return str(getter(style_key))
        fallback = {
            "default": "📁",
            "mini": ":D",
            "braille": "⠋⠊",
            "codex": "⟠F",
        }
        return fallback.get(style_key, "[]")

    def _icon_list_symbol(self, action):
        style_key = self.STYLE_OPTIONS[self._style_index][0]
        getter = getattr(self.app, "icon_style_preview_symbol", None)
        action_key = getattr(action, "value", action)
        if callable(getter):
            return str(getter(style_key, action_key))
        return "[]"

    def draw(self, stdscr):
        if not self.visible:
            return

        Window.draw(self, stdscr)
        body_attr = theme_attr("window_body")
        selected_attr = body_attr | curses.A_REVERSE
        bold_attr = body_attr | curses.A_BOLD
        _key, style_label = self.STYLE_OPTIONS[self._style_index]
        style_text = f" Style: {style_label}  (F2/S: Change)  |  Enter=Save"
        safe_addstr(
            stdscr,
            self.y + 3,
            self.x + 2,
            style_text.ljust(self.w - 4)[: self.w - 4],
            body_attr,
        )

        box_x = self.x + 2
        box_y = self.y + 4
        box_w = max(20, self.w - 4)
        box_h = 5
        draw_box(stdscr, box_y, box_x, box_h, box_w, body_attr, double=False)
        safe_addstr(stdscr, box_y, box_x + 2, "Preview", body_attr | curses.A_BOLD)

        preview_styles = ("default", "mini", self.STYLE_OPTIONS[self._style_index][0])
        preview_labels = ("Classic", "Mini", "Selected")
        col_w = max(10, (box_w - 2) // 3)
        for idx, style_key in enumerate(preview_styles):
            px = box_x + 1 + idx * col_w
            label = preview_labels[idx]
            token = self._preview_symbol(style_key)
            attr = selected_attr if style_key == self.STYLE_OPTIONS[self._style_index][0] else body_attr
            safe_addstr(stdscr, box_y + 1, px, label.ljust(col_w - 1)[: col_w - 1], attr | curses.A_BOLD)
            safe_addstr(stdscr, box_y + 2, px, token.ljust(col_w - 1)[: col_w - 1], attr)
            safe_addstr(stdscr, box_y + 3, px, f"[{style_key}]".ljust(col_w - 1)[: col_w - 1], attr)

        # Tabs
        tab_y = self.y + 9
        tab_x = self.x + 2
        self._tab_ranges = []
        for idx, cat in enumerate(self.categories):
            tab = f" {cat} "
            attr = selected_attr if (self.active and self.in_list and idx == self.active_cat_idx) else bold_attr
            safe_addstr(stdscr, tab_y, tab_x, tab, attr)
            self._tab_ranges.append((tab_x, tab_x + len(tab), idx))
            tab_x += len(tab) + 1

        # Icon list (no checkboxes)
        list_x, list_y, list_w, list_h = self._list_rect()
        draw_box(stdscr, list_y - 1, list_x - 1, list_h + 2, list_w + 2, body_attr, double=False)
        category = self._current_category()
        items = self.choices.get(category, []) if category else []
        offset = self.offsets.get(category, 0) if category else 0
        selected_idx = self.sel_indices.get(category, 0) if category else 0
        catalog = {str(entry.get("label", "")): entry for entry in self._iter_catalog_entries()}

        for row in range(list_h):
            idx = offset + row
            if idx < len(items):
                label, _value, _checked = items[idx]
                entry = catalog.get(label, {})
                symbol = self._icon_list_symbol(entry.get("action"))
                text = f" {symbol:<4} {label}"
                is_focused = self.in_list and self.active and idx == selected_idx
                attr = selected_attr if is_focused else body_attr
                safe_addstr(stdscr, list_y + row, list_x, text.ljust(list_w)[:list_w], attr)
            else:
                safe_addstr(stdscr, list_y + row, list_x, " " * list_w, body_attr)

        if len(items) > list_h:
            sb_x = list_x + list_w - 1
            thumb = int(offset / max(1, len(items) - list_h) * (list_h - 1))
            for row in range(list_h):
                ch = "█" if row == thumb else "░"
                safe_addstr(stdscr, list_y + row, sb_x, ch, theme_attr("scrollbar"))

        # Buttons
        btn_y = self.y + self.h - 2
        total_w = sum(len(btn) + 4 for btn in self.buttons) + (len(self.buttons) - 1) * 2
        btn_x = self.x + max(0, (self.w - total_w) // 2)
        self._btn_ranges = []
        for idx, text in enumerate(self.buttons):
            label = f"[ {text} ]"
            attr = theme_attr("button_selected") if (self.active and not self.in_list and idx == self.selected_button) else theme_attr("button")
            safe_addstr(stdscr, btn_y, btn_x, label, attr)
            self._btn_ranges.append((btn_x, btn_x + len(label), idx))
            btn_x += len(label) + 2

    def handle_key(self, key):
        key_code = normalize_key_code(key)
        if key_code in (getattr(curses, "KEY_F2", -1), ord("s"), ord("S")):
            self._cycle_style(1)
            return None
        if key_code == 27:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        if key_code == 9:  # Tab
            self.in_list = not self.in_list
            return None
        if self.in_list and key_code in (curses.KEY_LEFT, curses.KEY_RIGHT):
            if key_code == curses.KEY_LEFT:
                self.active_cat_idx = max(0, self.active_cat_idx - 1)
            else:
                self.active_cat_idx = min(len(self.categories) - 1, self.active_cat_idx + 1)
            return None
        if not self.in_list and key_code in (curses.KEY_LEFT, curses.KEY_RIGHT):
            if key_code == curses.KEY_LEFT:
                self.selected_button = max(0, self.selected_button - 1)
            else:
                self.selected_button = min(len(self.buttons) - 1, self.selected_button + 1)
            return None
        if key_code == curses.KEY_UP:
            if not self.in_list:
                self.in_list = True
                return None
            self._move_selection(-1)
            return None
        if key_code == curses.KEY_DOWN:
            if not self.in_list:
                self.in_list = True
                return None
            self._move_selection(1)
            return None
        if key_code in (10, 13, curses.KEY_ENTER):
            if not self.in_list:
                return self._activate_button()
            return None
        if key_code == 32 and not self.in_list:
            return self._activate_button()
        return None

    def handle_click(self, mx, my):
        if my == self.y + 9:
            for start_x, end_x, idx in self._tab_ranges:
                if start_x <= mx < end_x:
                    self.in_list = True
                    self.active_cat_idx = idx
                    return True

        list_x, list_y, list_w, list_h = self._list_rect()
        if list_x <= mx < list_x + list_w and list_y <= my < list_y + list_h:
            category = self._current_category()
            if category is None:
                return True
            click_idx = self.offsets[category] + (my - list_y)
            items = self.choices.get(category, [])
            if click_idx < len(items):
                self.in_list = True
                self.sel_indices[category] = click_idx
            return True

        if my == self.y + self.h - 2:
            for start_x, end_x, idx in self._btn_ranges:
                if start_x <= mx < end_x:
                    self.in_list = False
                    self.selected_button = idx
                    return self._activate_button()
        return False

    def _activate_button(self):
        if self.selected_button != 0:
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        self._apply_selected_style()
        self.app.persist_config()
        self.app.refresh_icons()
        return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)


class MenuEditorWindow(_BaseSelectionEditorWindow):
    """Global menu visibility editor (apps, games, plugins)."""

    def __init__(self, x, y, w, h, app):
        super().__init__("Menu Editor", x, y, w, h, app)
        self._help_text = "Choose what appears in global menus."
        self._status_text = "Includes apps, games and plugins."

    def _iter_catalog_entries(self):
        if hasattr(self.app, "_build_menu_editor_catalog"):
            catalog = self.app._build_menu_editor_catalog()
            return [
                {
                    "category": str(item.get("category", "Apps")),
                    "label": str(item.get("label", "")),
                    "value": str(item.get("key", "")).strip().lower(),
                }
                for item in catalog
            ]
        return []

    def _current_hidden_set(self):
        if hasattr(self.app, "_get_hidden_menu_keys"):
            return set(self.app._get_hidden_menu_keys())
        raw = str(getattr(self.app.config, "hidden_menu_items", "") or "")
        return {token.strip().lower() for token in raw.split(",") if token.strip()}

    def _save_hidden_values(self, hidden_values):
        self._set_config_field("hidden_menu_items", ",".join(hidden_values))
        self.app.persist_config()
        rebuilder = getattr(self.app, "_rebuild_global_menu", None)
        if callable(rebuilder):
            rebuilder()


class AppManagerWindow(DesktopIconManagerWindow):
    """Backwards-compatible alias for old action routes/tests."""
