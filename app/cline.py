from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


Runner = Callable[..., subprocess.CompletedProcess[str]]
Resolver = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class ClineRequest:
    task: str
    repository_path: str
    tests: tuple[str, ...] = ()
    mode: str = "delegate"
    verification_errors: tuple[str, ...] = ()
    allowed_paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClineResponse:
    accepted: bool
    message: str


class ClineTransport(Protocol):
    def send(self, request: ClineRequest) -> ClineResponse: ...


@dataclass(frozen=True, slots=True)
class ClineCliConfig:
    executable: str = "cline"
    timeout_seconds: int = 900
    auto_approve: bool = False
    thinking: str | None = None


class ClineCliTransport:
    """Invoke Cline through its headless CLI boundary."""

    def __init__(
        self,
        config: ClineCliConfig | None = None,
        *,
        runner: Runner = subprocess.run,
        resolver: Resolver | None = None,
        platform_name: str | None = None,
    ) -> None:
        self._config = config or ClineCliConfig()
        self._runner = runner
        self._resolver = resolver or self._resolve_executable
        self._platform_name = platform_name or os.name

    @staticmethod
    def _resolve_executable(executable: str) -> str | None:
        resolved = shutil.which(executable)
        if resolved:
            return resolved
        if os.name != "nt":
            return None
        for directory in os.environ.get("PATH", "").split(os.pathsep):
            directory = directory.strip('" ')
            if not directory:
                continue
            for suffix in (".ps1", ".cmd", ".bat", ".exe"):
                candidate = Path(directory) / f"{executable}{suffix}"
                if candidate.is_file():
                    return str(candidate)
        return None

    @staticmethod
    def _build_prompt(request: ClineRequest) -> str:
        lines = [
            "EXECUTE THIS CODING TASK NOW:",
            request.task.strip(),
            "",
            f"Mode: {request.mode}",
            "Do not ask the user what task to perform; the task is already above.",
            "Do not stop at planning or restating the request.",
            "Use the available coding tools to complete the task now.",
        ]
        if request.allowed_paths:
            lines += [
                "",
                "STRICT CHANGE SCOPE:",
                "You may modify ONLY these repository-relative paths:",
                *[f"- {item}" for item in request.allowed_paths],
                "Do not create, modify, rename, or delete any other file.",
            ]
        if request.tests:
            lines += ["", "Required verification commands/tests:"]
            lines += [f"- {item}" for item in request.tests]
        if request.verification_errors:
            lines += ["", "Previous verification errors to repair:"]
            lines += [f"- {item}" for item in request.verification_errors]
            lines += ["Repair these errors before finishing."]
        lines += [
            "",
            "Stay inside the supplied working directory.",
            "Do not commit, push, merge, or change branches.",
            "Finish only after the requested change is actually made.",
        ]
        return "\n".join(lines).strip()

    def _build_cli_args(self, request: ClineRequest) -> list[str]:
        args = [
            "--json",
            "--auto-approve",
            "true" if self._config.auto_approve else "false",
            "--timeout",
            str(self._config.timeout_seconds),
            "--cwd",
            str(Path(request.repository_path)),
        ]
        if self._config.thinking:
            args += ["--thinking", self._config.thinking]
        args.append(self._build_prompt(request))
        return args

    def _build_command(self, request: ClineRequest) -> list[str]:
        return [self._config.executable, *self._build_cli_args(request)]

    def _build_launch_command(self, request: ClineRequest) -> list[str]:
        resolved = self._resolver(self._config.executable)
        if not resolved:
            raise FileNotFoundError(self._config.executable)
        args = self._build_cli_args(request)
        if self._platform_name == "nt" and Path(resolved).suffix.lower() == ".ps1":
            return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved, *args]
        return [resolved, *args]

    @staticmethod
    def _extract_message(stdout: str) -> str:
        messages: list[str] = []
        for raw_line in stdout.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            for key in ("text", "message", "content"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    messages.append(value.strip())
                    break
        return messages[-1] if messages else (stdout.strip() or "Cline completed without textual output.")

    def send(self, request: ClineRequest) -> ClineResponse:
        repository = Path(request.repository_path)
        if not repository.exists() or not repository.is_dir():
            return ClineResponse(False, f"Repository path does not exist or is not a directory: {repository}")
        try:
            command = self._build_launch_command(request)
            completed = self._runner(
                command,
                cwd=str(repository),
                capture_output=True,
                text=True,
                timeout=self._config.timeout_seconds + 30,
                check=False,
            )
        except FileNotFoundError:
            return ClineResponse(False, f"Cline executable not found: {self._config.executable}")
        except subprocess.TimeoutExpired:
            return ClineResponse(False, "Cline CLI timed out before completing the task.")
        except OSError as exc:
            return ClineResponse(False, f"Cline CLI could not be started: {exc}")
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip() or f"exit code {completed.returncode}"
            return ClineResponse(False, f"Cline CLI failed: {detail}")
        return ClineResponse(True, self._extract_message(completed.stdout))
