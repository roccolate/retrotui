# RetroTUI Icon Styles

RetroTUI intentionally keeps the user-facing desktop icon styles small and readable. The Icons app should expose only these three choices:

| UI label | Config key | Purpose |
|---|---|---|
| Classic | `default` | Current clean 3-line boxes with simple letter tokens. This is the safest default for general terminals. |
| Win31 Art | `win31_art` | Expressive 3-line per-app artwork inspired by the v0.2.2 icon redesign. Use this when there is enough screen space and visual personality matters. |
| Retro 0.1 | `retro_01` | Tiny symbolic boxes for very small screens. This preserves the old mini/retro feel without making it the default. |

## Visual examples

### Classic

```text
┌──┐
│FL│
└──┘
Files

┌──┐
│NP│
└──┘
Notepad
```

### Win31 Art

```text
┌──┐
│▒▒│
└──┘
Files

╔══╗
║≡≡║
╚══╝
Notepad

┌──┐
│>_│
└──┘
Terminal

╭──╮
│⚙ │
╰──╯
Settings
```

### Retro 0.1

```text
╭──╮
│:D│
╰──╯
Files

╭──╮
│>:│
╰──╯
Terminal
```

## Deprecated historical styles

Older configs may still contain historical style keys. They should normalize as follows:

| Old key | Runtime behavior |
|---|---|
| `mini` | Alias for `retro_01` |
| `braille` | Falls back to `default` |
| `codex` | Falls back to `default` |

`braille` and `codex` should not appear in the Icons app UI. They were experimental, visually noisy in practice, and are kept only as safe legacy inputs so old config files do not break startup.

## Implementation notes

- User-facing style selection lives in `retrotui/apps/app_manager.py` (`IconsWindow.STYLE_OPTIONS`).
- Style normalization and per-style art live in `retrotui/core/icon_styles.py`.
- Config normalization lives in `retrotui/core/config.py`; it accepts aliases but serializes the normalized style key.
- Plugin icons continue to use their `[plugin.icon]` token for compact rendering; `Win31 Art` uses the same compact token box for plugins unless custom artwork is added later.

## Design rule

Do not add a new visible icon style unless it has a clear production use case. The intended long-term set is:

```text
Classic
Win31 Art
Retro 0.1
```
