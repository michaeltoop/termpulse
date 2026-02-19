"""Data collectors for termpulse widgets.

Each collector gathers one domain of information:
- GitCollector: branch, changes, commits, drift
- SystemCollector: CPU, memory, disk, network
- CommandCollector: shell history parsing and classification
- MomentumCollector: session tracking and flow detection
"""

from __future__ import annotations

import os
import subprocess
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import psutil


# =========================================================================
# Git Collector
# =========================================================================

@dataclass
class GitState:
    """Snapshot of git repository state."""
    is_repo: bool = False
    branch: str = ""
    ahead: int = 0
    behind: int = 0
    staged: int = 0
    modified: int = 0
    untracked: int = 0
    conflicts: int = 0
    last_commit_age_seconds: float = 0.0
    last_commit_msg: str = ""
    recent_commits: list[str] = field(default_factory=list)
    stash_count: int = 0

    @property
    def is_clean(self) -> bool:
        return self.staged == 0 and self.modified == 0 and self.untracked == 0

    @property
    def total_changes(self) -> int:
        return self.staged + self.modified + self.untracked

    @property
    def drift_minutes(self) -> float:
        return self.last_commit_age_seconds / 60.0

    @property
    def drift_level(self) -> str:
        """Drift severity: calm, warm, hot, critical."""
        m = self.drift_minutes
        if m < 15:
            return "calm"
        elif m < 30:
            return "warm"
        elif m < 60:
            return "hot"
        return "critical"


def collect_git(cwd: Optional[str] = None) -> GitState:
    """Collect git state from the current or given directory."""
    cwd = cwd or os.getcwd()
    state = GitState()

    def _run(args: list[str]) -> Optional[str]:
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True, text=True, timeout=5, cwd=cwd,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    # Check if git repo
    if _run(["rev-parse", "--is-inside-work-tree"]) != "true":
        return state
    state.is_repo = True

    # Branch
    state.branch = _run(["branch", "--show-current"]) or _run(["rev-parse", "--short", "HEAD"]) or "?"

    # Ahead/behind
    ab = _run(["rev-list", "--left-right", "--count", f"{state.branch}...@{{u}}"])
    if ab:
        parts = ab.split()
        if len(parts) == 2:
            state.ahead = int(parts[0])
            state.behind = int(parts[1])

    # Status counts
    status = _run(["status", "--porcelain"])
    if status:
        for line in status.splitlines():
            if len(line) < 2:
                continue
            x, y = line[0], line[1]
            if x == "U" or y == "U":
                state.conflicts += 1
            elif x in "MADRC":
                state.staged += 1
            if y in "MD":
                state.modified += 1
            elif y == "?" and x == "?":
                state.untracked += 1

    # Last commit age
    timestamp = _run(["log", "-1", "--format=%ct"])
    if timestamp:
        state.last_commit_age_seconds = time.time() - float(timestamp)

    # Last commit message
    state.last_commit_msg = _run(["log", "-1", "--format=%s"]) or ""

    # Recent commits (last 5)
    log = _run(["log", "--oneline", "-5"])
    if log:
        state.recent_commits = log.splitlines()

    # Stash count
    stash = _run(["stash", "list"])
    if stash:
        state.stash_count = len(stash.splitlines())

    return state


# =========================================================================
# System Collector
# =========================================================================

@dataclass
class SystemState:
    """Snapshot of system resource usage."""
    cpu_percent: float = 0.0
    cpu_history: list[float] = field(default_factory=list)
    memory_percent: float = 0.0
    memory_used_gb: float = 0.0
    memory_total_gb: float = 0.0
    disk_percent: float = 0.0
    disk_used_gb: float = 0.0
    disk_total_gb: float = 0.0
    net_sent_bytes: int = 0
    net_recv_bytes: int = 0
    load_avg_1m: float = 0.0
    process_count: int = 0


# Keep a rolling buffer of CPU samples for sparklines
_cpu_history: list[float] = []
_net_last: dict = {"sent": 0, "recv": 0, "time": 0.0}


def collect_system() -> SystemState:
    """Collect system resource state."""
    global _cpu_history, _net_last

    state = SystemState()

    # CPU
    state.cpu_percent = psutil.cpu_percent(interval=0)
    _cpu_history.append(state.cpu_percent)
    if len(_cpu_history) > 30:
        _cpu_history = _cpu_history[-30:]
    state.cpu_history = list(_cpu_history)

    # Memory
    mem = psutil.virtual_memory()
    state.memory_percent = mem.percent
    state.memory_used_gb = round(mem.used / (1024 ** 3), 1)
    state.memory_total_gb = round(mem.total / (1024 ** 3), 1)

    # Disk
    disk = psutil.disk_usage("/")
    state.disk_percent = disk.percent
    state.disk_used_gb = round(disk.used / (1024 ** 3), 1)
    state.disk_total_gb = round(disk.total / (1024 ** 3), 1)

    # Network (rate since last call)
    net = psutil.net_io_counters()
    now = time.time()
    elapsed = now - _net_last["time"] if _net_last["time"] else 1.0
    if elapsed > 0:
        state.net_sent_bytes = int((net.bytes_sent - _net_last["sent"]) / elapsed)
        state.net_recv_bytes = int((net.bytes_recv - _net_last["recv"]) / elapsed)
    _net_last = {"sent": net.bytes_sent, "recv": net.bytes_recv, "time": now}

    # Load average
    load = os.getloadavg()
    state.load_avg_1m = round(load[0], 2)

    # Process count
    state.process_count = len(psutil.pids())

    return state


# =========================================================================
# Command Collector
# =========================================================================

COMMAND_CATEGORIES = {
    "git": ["git"],
    "python": ["python", "python3", "pip", "pip3", "pytest", "mypy", "ruff"],
    "node": ["node", "npm", "npx", "yarn", "pnpm", "bun", "tsx", "ts-node"],
    "build": ["make", "cargo", "go", "gcc", "cmake", "gradle", "mvn"],
    "navigate": ["cd", "ls", "ll", "lll", "pwd", "fd", "rg", "bat", "cat", "less"],
    "edit": ["vim", "nvim", "nano", "code", "cursor", "emacs"],
    "docker": ["docker", "docker-compose", "podman", "kubectl", "k9s"],
    "shell": ["echo", "export", "source", "alias", "which", "type", "env"],
    "network": ["curl", "wget", "ssh", "scp", "rsync", "httpie"],
    "claude": ["claude", "grip", "gg", "ggr", "ggl", "sesh"],
}


@dataclass
class CommandEntry:
    """A parsed command from shell history."""
    raw: str
    command: str
    category: str
    timestamp: Optional[float] = None


def _categorize_command(cmd: str) -> str:
    """Classify a command into a category."""
    base = cmd.strip().split()[0] if cmd.strip() else ""
    base = base.split("/")[-1]  # Handle full paths
    for cat, cmds in COMMAND_CATEGORIES.items():
        if base in cmds:
            return cat
    return "other"


def collect_commands(limit: int = 50) -> list[CommandEntry]:
    """Parse recent shell history into categorized entries."""
    entries = []

    # Try zsh history (extended format: ': timestamp:0;command')
    histfile = Path.home() / ".zsh_history"
    if not histfile.exists():
        histfile = Path.home() / ".bash_history"

    if not histfile.exists():
        return entries

    try:
        lines = histfile.read_bytes().decode("utf-8", errors="replace").splitlines()
        for line in lines[-limit:]:
            ts = None
            cmd = line

            # Parse zsh extended history format
            if line.startswith(": "):
                parts = line.split(";", 1)
                if len(parts) == 2:
                    try:
                        ts = float(parts[0].split(":")[1].strip())
                    except (ValueError, IndexError):
                        pass
                    cmd = parts[1]

            if cmd.strip():
                entries.append(CommandEntry(
                    raw=cmd.strip(),
                    command=cmd.strip().split()[0] if cmd.strip() else "",
                    category=_categorize_command(cmd),
                    timestamp=ts,
                ))
    except (OSError, UnicodeDecodeError):
        pass

    return entries


def command_distribution(entries: list[CommandEntry]) -> dict[str, int]:
    """Count commands per category."""
    return dict(Counter(e.category for e in entries))


# =========================================================================
# Momentum Collector
# =========================================================================

@dataclass
class MomentumState:
    """Developer momentum metrics."""
    session_start: float = 0.0
    session_duration_minutes: float = 0.0
    commits_this_session: int = 0
    commit_velocity_per_hour: float = 0.0
    command_diversity: float = 0.0  # 0-1, higher = more diverse
    flow_score: float = 0.0  # 0-100, composite momentum metric
    streak_minutes: float = 0.0  # Minutes of continuous activity


_session_start = time.time()


def collect_momentum(git: GitState, commands: list[CommandEntry]) -> MomentumState:
    """Calculate developer momentum from git and command data."""
    state = MomentumState()
    now = time.time()

    # Session duration
    state.session_start = _session_start
    state.session_duration_minutes = (now - _session_start) / 60.0

    # Commits in last hour (from git log timestamps)
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--since=1.hour.ago"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            state.commits_this_session = len(result.stdout.strip().splitlines())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    hours = max(state.session_duration_minutes / 60.0, 0.1)
    state.commit_velocity_per_hour = round(state.commits_this_session / hours, 1)

    # Command diversity (Shannon entropy normalized)
    if commands:
        dist = command_distribution(commands)
        total = sum(dist.values())
        if total > 0 and len(dist) > 1:
            import math
            entropy = -sum(
                (c / total) * math.log2(c / total)
                for c in dist.values() if c > 0
            )
            max_entropy = math.log2(len(dist))
            state.command_diversity = round(entropy / max_entropy, 2) if max_entropy > 0 else 0
        elif len(dist) == 1:
            state.command_diversity = 0.0

    # Flow score: weighted composite
    # High commit velocity + high diversity + low drift = flow
    drift_penalty = min(git.drift_minutes / 60.0, 1.0) if git.is_repo else 0.5
    velocity_signal = min(state.commit_velocity_per_hour / 3.0, 1.0)
    diversity_signal = state.command_diversity

    state.flow_score = round(
        (velocity_signal * 0.4 + diversity_signal * 0.3 + (1 - drift_penalty) * 0.3) * 100,
        0,
    )

    return state
