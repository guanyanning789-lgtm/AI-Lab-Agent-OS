import subprocess

from app.scope_guard import GitScopeGuard


def _git(repo, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path):
    _git(tmp_path, "init")
    (tmp_path / "calculator.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "test_calculator.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "init")
    return tmp_path


def test_scope_guard_accepts_only_allowed_change(tmp_path):
    repo = _repo(tmp_path)
    (repo / "calculator.py").write_text("x = 2\n", encoding="utf-8")

    result = GitScopeGuard().check(
        repository_path=str(repo),
        allowed_paths=("calculator.py",),
    )

    assert result.passed is True
    assert result.changed_paths == ("calculator.py",)


def test_scope_guard_rejects_unexpected_new_file(tmp_path):
    repo = _repo(tmp_path)
    (repo / "calculator.py").write_text("x = 2\n", encoding="utf-8")
    (repo / "test_auth.py").write_text("def test_bad(): pass\n", encoding="utf-8")

    result = GitScopeGuard().check(
        repository_path=str(repo),
        allowed_paths=("calculator.py",),
    )

    assert result.passed is False
    assert "test_auth.py" in result.message
