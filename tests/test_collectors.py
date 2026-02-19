"""Tests for termpulse data collectors."""

import time

from termpulse.collectors import (
    CommandEntry,
    GitState,
    MomentumState,
    SystemState,
    collect_commands,
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
