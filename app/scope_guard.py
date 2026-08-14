from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScopeResult:
    passed: bool
    message: str
    changed_paths: tuple[str, ...] = ()


class GitScopeGuard:
    """Verify that a coding task only changes explicitly allowed paths."""

    def _changed_paths(self, repository_path: str) -> tuple[str, ...]:
        repository = Path(repository_path)
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repository),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return ()

        paths: list[str] = []
        for raw_line in completed.stdout.splitlines():
            if len(raw_line) < 4:
                continue
            path = raw_line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            paths.append(path.replace("\\", "/"))
        return tuple(paths)

    def check(self, *, repository_path: str, allowed_paths: tuple[str, ...]) -> ScopeResult:
        if not allowed_paths:
            return ScopeResult(True, "no explicit scope restriction requested")

        allowed = {item.replace("\\", "/").lstrip("./") for item in allowed_paths}
        changed = self._changed_paths(repository_path)
        unauthorized = tuple(
            path for path in changed if path.lstrip("./") not in allowed
        )
        if unauthorized:
            return ScopeResult(
                False,
                "unauthorized repository changes detected: " + ", ".join(unauthorized),
                changed,
            )
        return ScopeResult(True, "repository changes stayed inside allowed scope", changed)
