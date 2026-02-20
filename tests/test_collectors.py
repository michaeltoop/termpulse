"""Tests for termpulse data collectors."""

import time

from termpulse.collectors import (
    CommandEntry,
    DiffFile,
    GitState,
    HeatmapEntry,
    MomentumState,
    SystemState,
    _categorize_command,
    _run_git,
    collect_commands,
    collect_diff_files,
    collect_file_heatmap,
    collect_git,
    collect_momentum,
    collect_system,
    command_distribution,
)


# === GitState ===

def test_git_state_defaults():
    g = GitState()
    assert g.is_clean
    assert g.total_changes == 0
    assert g.drift_level == "calm"


def test_git_state_dirty():
    g = GitState(staged=2, modified=3, untracked=1)
    assert not g.is_clean
    assert g.total_changes == 6


def test_git_drift_levels():
    assert GitState(last_commit_age_seconds=0).drift_level == "calm"
    assert GitState(last_commit_age_seconds=600).drift_level == "calm"  # 10m
    assert GitState(last_commit_age_seconds=1200).drift_level == "warm"  # 20m
    assert GitState(last_commit_age_seconds=2400).drift_level == "hot"   # 40m
    assert GitState(last_commit_age_seconds=7200).drift_level == "critical"  # 120m


def test_git_drift_minutes():
    g = GitState(last_commit_age_seconds=1800)
    assert g.drift_minutes == 30.0


# === SystemState ===

def test_collect_system():
    s = collect_system()
    assert 0 <= s.cpu_percent <= 100
    assert 0 <= s.memory_percent <= 100
    assert 0 <= s.disk_percent <= 100
    assert s.memory_total_gb > 0
    assert s.process_count > 0


def test_system_state_cpu_history():
    # Call twice to build history
    s1 = collect_system()
    s2 = collect_system()
    assert len(s2.cpu_history) >= 2


# === CommandCollector ===

def test_command_distribution():
    entries = [
        CommandEntry(raw="git status", command="git", category="git"),
        CommandEntry(raw="git commit", command="git", category="git"),
        CommandEntry(raw="python3 test.py", command="python3", category="python"),
        CommandEntry(raw="ls -la", command="ls", category="navigate"),
    ]
    dist = command_distribution(entries)
    assert dist["git"] == 2
    assert dist["python"] == 1
    assert dist["navigate"] == 1


def test_collect_commands():
    cmds = collect_commands(limit=10)
    # May be empty in CI but shouldn't error
    assert isinstance(cmds, list)


# === MomentumCollector ===

def test_momentum_defaults():
    m = MomentumState()
    assert m.flow_score == 0.0
    assert m.commit_velocity_per_hour == 0.0


def test_collect_momentum():
    git = GitState(is_repo=True, last_commit_age_seconds=600)
    commands = [
        CommandEntry(raw="git status", command="git", category="git"),
        CommandEntry(raw="python3 test.py", command="python3", category="python"),
        CommandEntry(raw="ls", command="ls", category="navigate"),
    ]
    m = collect_momentum(git, commands)
    assert 0 <= m.flow_score <= 100
    assert m.session_duration_minutes >= 0
    assert 0 <= m.command_diversity <= 1


# === Widget renderers ===

def test_sparkline():
    from termpulse.widgets import sparkline
    result = sparkline([0, 50, 100], 3)
    assert len(result) == 3
    assert result[0] == "▁"  # Min
    assert result[-1] == "█"  # Max


def test_sparkline_empty():
    from termpulse.widgets import sparkline
    result = sparkline([], 5)
    assert len(result) == 5


def test_drift_bar():
    from termpulse.widgets import drift_bar
    bar = drift_bar(30, 10)
    assert len(bar) > 0  # Rich Text object


def test_flow_bar():
    from termpulse.widgets import flow_bar
    bar = flow_bar(75, 10)
    assert len(bar) > 0


# === Bug fix regression tests ===

def test_git_state_conflicts_not_double_counted():
    """Conflict files should not also count as modified (bug fix)."""
    # Simulate a UU conflict line — conflicts should increment, not modified
    g = GitState(conflicts=2, modified=0)
    assert g.total_changes == 0  # conflicts not in total_changes
    assert g.conflicts == 2
    assert g.modified == 0


def test_categorize_command_full_path():
    """Commands with full paths should be categorized by basename."""
    assert _categorize_command("/usr/bin/git status") == "git"
    assert _categorize_command("/usr/local/bin/python3 test.py") == "python"
    assert _categorize_command("unknown_tool --help") == "other"


def test_categorize_command_empty():
    """Empty string should not crash."""
    assert _categorize_command("") == "other"
    assert _categorize_command("   ") == "other"


def test_momentum_single_category():
    """Single command category should yield 0 diversity."""
    git = GitState(is_repo=True, last_commit_age_seconds=300)
    commands = [
        CommandEntry(raw="git status", command="git", category="git"),
        CommandEntry(raw="git log", command="git", category="git"),
    ]
    m = collect_momentum(git, commands)
    assert m.command_diversity == 0.0


def test_momentum_no_commands():
    """No commands should not crash and yield 0 diversity."""
    git = GitState(is_repo=True, last_commit_age_seconds=300)
    m = collect_momentum(git, [])
    assert m.command_diversity == 0.0
    assert 0 <= m.flow_score <= 100


def test_system_state_has_disk_values():
    """System collector should populate actual GB values."""
    s = collect_system()
    assert s.memory_used_gb > 0
    assert s.disk_total_gb > 0


def test_drift_bar_extremes():
    """Drift bar should handle 0 and very large values."""
    from termpulse.widgets import drift_bar
    bar_zero = drift_bar(0, 10)
    assert len(bar_zero) > 0
    bar_huge = drift_bar(500, 10)
    assert len(bar_huge) > 0


def test_flow_bar_boundaries():
    """Flow bar at 0 and 100."""
    from termpulse.widgets import flow_bar
    bar_zero = flow_bar(0, 10)
    assert len(bar_zero) > 0
    bar_max = flow_bar(100, 10)
    assert len(bar_max) > 0


def test_sparkline_single_value():
    """Sparkline with a single value should not crash."""
    from termpulse.widgets import sparkline
    result = sparkline([42.0], 5)
    assert len(result) == 5


def test_cli_version():
    """CLI --version flag should work."""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "termpulse", "--version"],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0
    assert "termpulse" in result.stdout


def test_cli_bad_cwd():
    """CLI --cwd with nonexistent dir should exit 1."""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "termpulse", "--cwd", "/nonexistent/path/xyz"],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 1
    assert "not found" in result.stderr


def test_collect_git_nonrepo(tmp_path):
    """collect_git in a non-git directory should return empty state."""
    g = collect_git(cwd=str(tmp_path))
    assert not g.is_repo
    assert g.branch == ""
    assert g.is_clean


# === DiffFile ===

def test_diff_file_defaults():
    d = DiffFile(path="test.py")
    assert d.total_changes == 0
    assert d.change_ratio == 0.5
    assert d.status == "M"


def test_diff_file_with_changes():
    d = DiffFile(path="test.py", insertions=10, deletions=5)
    assert d.total_changes == 15
    assert abs(d.change_ratio - 10 / 15) < 0.01


def test_diff_file_all_insertions():
    d = DiffFile(path="new.py", status="A", insertions=20, deletions=0)
    assert d.change_ratio == 1.0


def test_diff_file_all_deletions():
    d = DiffFile(path="old.py", status="D", insertions=0, deletions=15)
    assert d.change_ratio == 0.0


# === HeatmapEntry ===

def test_heatmap_entry_defaults():
    h = HeatmapEntry(path="app.py")
    assert h.commit_count == 0
    assert h.last_author == ""


# === collect_diff_files ===

def test_collect_diff_files_nonrepo(tmp_path):
    """Non-git directory returns empty list."""
    files = collect_diff_files(cwd=str(tmp_path))
    assert files == []


def test_collect_diff_files_returns_list():
    """Should return a list (may be empty if tree is clean)."""
    files = collect_diff_files()
    assert isinstance(files, list)


# === collect_file_heatmap ===

def test_collect_file_heatmap_nonrepo(tmp_path):
    """Non-git directory returns empty list."""
    entries = collect_file_heatmap(cwd=str(tmp_path))
    assert entries == []


def test_collect_file_heatmap_returns_list():
    """Should return a list of HeatmapEntry objects."""
    entries = collect_file_heatmap()
    assert isinstance(entries, list)
    for e in entries:
        assert isinstance(e, HeatmapEntry)
        assert e.commit_count > 0


# === Novel widget renderers ===

def test_change_fingerprint():
    from termpulse.widgets import change_fingerprint
    # With diff lines containing hunk headers
    diff = [
        "@@ -1,5 +1,8 @@",
        "+new line",
        " context",
        "@@ -20,3 +23,5 @@",
        "+another",
    ]
    fp = change_fingerprint(diff, 10)
    assert len(fp) > 0


def test_change_fingerprint_empty():
    from termpulse.widgets import change_fingerprint
    fp = change_fingerprint([], 10)
    assert len(fp) == 10


def test_diff_density():
    from termpulse.widgets import diff_density
    bar = diff_density(10, 5, 10)
    assert len(bar) > 0


def test_diff_density_zero():
    from termpulse.widgets import diff_density
    bar = diff_density(0, 0, 10)
    assert len(bar) == 10


def test_render_diff_lines():
    from termpulse.widgets import render_diff_lines
    lines = [
        "diff --git a/f b/f",
        "--- a/f",
        "+++ b/f",
        "@@ -1,3 +1,4 @@",
        " context",
        "+added",
        "-removed",
    ]
    text = render_diff_lines(lines)
    assert len(text) > 0


# === Shared git helper ===

def test_run_git_in_repo():
    """_run_git should return output in a valid git repo."""
    result = _run_git(["rev-parse", "--is-inside-work-tree"])
    assert result == "true"


def test_run_git_nonrepo(tmp_path):
    """_run_git returns None for invalid git commands in non-repo."""
    result = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=str(tmp_path))
    assert result is None


def test_run_git_bad_command():
    """_run_git returns None for invalid git subcommands."""
    result = _run_git(["not-a-real-command-xyz"])
    assert result is None
