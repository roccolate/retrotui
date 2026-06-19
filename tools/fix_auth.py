"""Clear cached GitHub credentials from common local credential stores."""
from __future__ import annotations

import shutil
import subprocess


GITHUB_CMDKEY_TARGETS = (
    "git:https://github.com",
    "LegacyGeneric:target=git:https://github.com",
    "gh:github.com",
    "LegacyGeneric:target=gh:github.com",
    "LegacyGeneric:target=GitHub for Visual Studio - https://github.com/",
)

COMMAND_TIMEOUT = 10.0


def _run(args, **kwargs):
    kwargs.setdefault("timeout", COMMAND_TIMEOUT)
    try:
        return subprocess.run(args, check=False, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        return subprocess.CompletedProcess(args=args, returncode=1, stderr=str(exc))


def clear_cmdkey_credentials() -> None:
    """Clear Windows Credential Manager entries when cmdkey is available."""
    if shutil.which("cmdkey") is None:
        print("cmdkey not found; skipping Windows Credential Manager.")
        return

    print("--- Clearing Windows GitHub credentials ---")
    for target in GITHUB_CMDKEY_TARGETS:
        print(f"Deleting: {target}")
        _run(["cmdkey", f"/delete:{target}"])


def reject_git_credentials() -> None:
    """Ask Git credential helpers to forget github.com credentials."""
    if shutil.which("git") is None:
        print("git not found; skipping git credential reject.")
        return

    print("--- Rejecting via git credential helper ---")
    _run(
        ["git", "credential", "reject"],
        input="protocol=https\nhost=github.com\n\n",
        text=True,
    )


def list_remaining_cmdkey_entries() -> None:
    """Print remaining cmdkey entries that mention github, if any."""
    if shutil.which("cmdkey") is None:
        return

    result = _run(["cmdkey", "/list"], capture_output=True, text=True)
    matches = [line for line in (result.stdout or "").splitlines() if "github" in line.lower()]
    if matches:
        print("--- Remaining cmdkey entries mentioning github ---")
        for line in matches:
            print(line)


def main() -> int:
    clear_cmdkey_credentials()
    reject_git_credentials()
    list_remaining_cmdkey_entries()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
