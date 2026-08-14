from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class VerificationResult:
    passed: bool
    message: str


class TestCommandVerifier:
    """Run explicit verification commands without invoking a shell.

    V0.1 intentionally allows only Python/pytest commands. This keeps the
    verification boundary useful for autonomous coding while avoiding a
    generic arbitrary-shell execution surface.
    """

    __test__ = False

    allowed_programs = {
        "python",
        "python.exe",
        "python3",
        "python3.exe",
        "pytest",
        "pytest.exe",
        "py",
        "py.exe",
    }

    def __init__(self, *, runner: Runner = subprocess.run, timeout_seconds: int = 600) -> None:
        self._runner = runner
        self._timeout_seconds = timeout_seconds

    @staticmethod
    def _split(command: str) -> list[str]:
        return shlex.split(command, posix=os.name != "nt")

    def _validate(self, command: str) -> tuple[bool, list[str], str]:
        try:
            args = self._split(command)
        except ValueError as exc:
            return False, [], f"invalid verification command: {exc}"
        if not args:
            return False, [], "verification command is empty"

        program = Path(args[0].strip('"')).name.lower()
        if program not in self.allowed_programs:
            return False, args, f"verification program is not allowed: {program}"
        return True, args, "allowed"

    def run(self, *, repository_path: str, commands: tuple[str, ...]) -> VerificationResult:
        repository = Path(repository_path)
        if not repository.exists() or not repository.is_dir():
            return VerificationResult(False, f"verification repository does not exist: {repository}")
        if not commands:
            return VerificationResult(True, "no explicit verification commands requested")

        evidence: list[str] = []
        for command in commands:
            allowed, args, reason = self._validate(command)
            if not allowed:
                return VerificationResult(False, reason)

            try:
                completed = self._runner(
                    args,
                    cwd=str(repository),
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return VerificationResult(False, f"verification timed out: {command}")
            except OSError as exc:
                return VerificationResult(False, f"verification could not start: {exc}")

            stdout = completed.stdout.strip()
            stderr = completed.stderr.strip()
            detail = stdout or stderr or f"exit code {completed.returncode}"
            evidence.append(f"$ {command}\n{detail}")
            if completed.returncode != 0:
                return VerificationResult(
                    False,
                    "verification command failed:\n" + "\n\n".join(evidence),
                )

        return VerificationResult(True, "verification passed:\n" + "\n\n".join(evidence))
