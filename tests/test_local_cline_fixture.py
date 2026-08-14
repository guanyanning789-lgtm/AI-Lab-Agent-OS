import subprocess

from scripts.local_cline_e2e import reset_calculator_fixture


def _git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True
    )


def test_reset_fixture_preserves_git_and_removes_pollution(tmp_path):
    repo = tmp_path / "fixture"
    repo.mkdir()
    _git(repo, "init")

    (repo / "old.py").write_text("old = True\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(
        repo,
        "-c", "user.name=Test",
        "-c", "user.email=test@example.com",
        "commit", "-m", "old fixture",
    )

    (repo / "auth_app.py").write_text("pollution = True\n", encoding="utf-8")
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "junk.pyc").write_bytes(b"junk")

    git_dir = repo / ".git"
    assert git_dir.is_dir()

    reset_calculator_fixture(repo)

    assert git_dir.is_dir()
    assert (repo / "calculator.py").read_text(encoding="utf-8") == (
        "def add(a, b):\n    return a - b\n"
    )
    assert (repo / "test_calculator.py").is_file()
    assert not (repo / "old.py").exists()
    assert not (repo / "auth_app.py").exists()
    assert not (repo / "__pycache__").exists()

    files = {
        path.relative_to(repo).as_posix()
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }
    assert files == {"calculator.py", "test_calculator.py"}
