"""Manual signal stress runner for RetroTUI on Linux TTY sessions.

This script is intended for manual validation in real terminals.
It repeatedly launches RetroTUI, injects signals, and checks expected behavior:

- SIGINT: process should keep running (queued as in-app Ctrl+C).
- SIGTERM/SIGHUP: process should exit cleanly.
"""

from __future__ import annotations

import argparse
import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass


DEFAULT_COMMAND = f"{sys.executable} -m retrotui"
VALID_SIGNALS = ("SIGINT", "SIGTERM", "SIGHUP")


@dataclass
class ProbeResult:
    signal_name: str
    iteration: int
    ok: bool
    detail: str
    return_code: int | None


def _parse_signal_name(name: str) -> int:
    value = getattr(signal, name, None)
    if value is None:
        raise ValueError(f"signal not supported on this platform: {name}")
    return int(value)


def _kill_process_group(proc: subprocess.Popen, sig: int) -> None:
    os.killpg(proc.pid, sig)


def _wait_for_exit(proc: subprocess.Popen, timeout_s: float) -> int | None:
    try:
        return proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        return None


def _run_one(
    command: list[str],
    signal_name: str,
    iteration: int,
    startup_wait_s: float,
    settle_wait_s: float,
    shutdown_timeout_s: float,
) -> ProbeResult:
    probe_signal = _parse_signal_name(signal_name)
    proc = subprocess.Popen(command, start_new_session=True)
    try:
        time.sleep(startup_wait_s)
        _kill_process_group(proc, probe_signal)
        time.sleep(settle_wait_s)

        if signal_name == "SIGINT":
            # SIGINT should be mapped to in-app Ctrl+C and not terminate session.
            if proc.poll() is not None:
                return ProbeResult(
                    signal_name=signal_name,
                    iteration=iteration,
                    ok=False,
                    detail="process exited after SIGINT; expected to remain running",
                    return_code=proc.returncode,
                )
            _kill_process_group(proc, _parse_signal_name("SIGTERM"))
            code = _wait_for_exit(proc, shutdown_timeout_s)
            if code is None:
                return ProbeResult(
                    signal_name=signal_name,
                    iteration=iteration,
                    ok=False,
                    detail="process did not exit after follow-up SIGTERM",
                    return_code=None,
                )
            return ProbeResult(
                signal_name=signal_name,
                iteration=iteration,
                ok=True,
                detail="SIGINT kept process alive; follow-up SIGTERM exited cleanly",
                return_code=code,
            )

        # SIGTERM/SIGHUP should terminate quickly.
        code = _wait_for_exit(proc, shutdown_timeout_s)
        if code is None:
            return ProbeResult(
                signal_name=signal_name,
                iteration=iteration,
                ok=False,
                detail=f"process did not exit after {signal_name}",
                return_code=None,
            )
        return ProbeResult(
            signal_name=signal_name,
            iteration=iteration,
            ok=True,
            detail=f"process exited after {signal_name}",
            return_code=code,
        )
    finally:
        if proc.poll() is None:
            try:
                _kill_process_group(proc, _parse_signal_name("SIGKILL"))
            except (OSError, ValueError, AttributeError):
                pass
            _wait_for_exit(proc, 1.0)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manual signal stress runner for RetroTUI in Linux TTY."
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="How many iterations to run per signal (default: 3).",
    )
    parser.add_argument(
        "--signals",
        default="SIGINT,SIGTERM,SIGHUP",
        help="Comma-separated signal names (default: SIGINT,SIGTERM,SIGHUP).",
    )
    parser.add_argument(
        "--startup-wait",
        type=float,
        default=0.8,
        help="Seconds to wait before injecting probe signal (default: 0.8).",
    )
    parser.add_argument(
        "--settle-wait",
        type=float,
        default=0.4,
        help="Seconds to wait after sending probe signal (default: 0.4).",
    )
    parser.add_argument(
        "--shutdown-timeout",
        type=float,
        default=5.0,
        help="Seconds to wait for process exit after shutdown signal (default: 5.0).",
    )
    parser.add_argument(
        "--command",
        default=DEFAULT_COMMAND,
        help=f"Command used to launch RetroTUI (default: {DEFAULT_COMMAND!r}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if os.name != "posix":
        print("This tool requires a POSIX environment (Linux/macOS).")
        return 2
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("Run this tool from an interactive TTY terminal session.")
        return 2
    if args.iterations < 1:
        print("--iterations must be >= 1")
        return 2

    signal_names = [part.strip().upper() for part in args.signals.split(",") if part.strip()]
    if not signal_names:
        print("No valid signals requested.")
        return 2
    invalid = [name for name in signal_names if name not in VALID_SIGNALS]
    if invalid:
        print(f"Unsupported signal names: {', '.join(invalid)}")
        print(f"Supported: {', '.join(VALID_SIGNALS)}")
        return 2

    command = shlex.split(args.command)
    if not command:
        print("Empty --command.")
        return 2

    print(f"Command: {' '.join(command)}")
    print(f"Signals: {', '.join(signal_names)}")
    print(f"Iterations per signal: {args.iterations}")

    failures = 0
    for signal_name in signal_names:
        for iteration in range(1, args.iterations + 1):
            result = _run_one(
                command=command,
                signal_name=signal_name,
                iteration=iteration,
                startup_wait_s=args.startup_wait,
                settle_wait_s=args.settle_wait,
                shutdown_timeout_s=args.shutdown_timeout,
            )
            status = "OK" if result.ok else "FAIL"
            print(
                f"[{status}] {result.signal_name} iter={result.iteration} "
                f"rc={result.return_code} detail={result.detail}"
            )
            if not result.ok:
                failures += 1

    if failures:
        print(f"Signal stress finished with {failures} failure(s).")
        return 1
    print("Signal stress finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
