"""termpulse widgets — novel TUI components.

Each widget renders one domain of developer awareness:
- GitPulse: branch status with animated drift meter
- SystemVitals: sparkline resource monitoring
- CommandFlow: semantic command history timeline
- MomentumTracker: flow detection and session metrics
"""

from __future__ import annotations

import re

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from termpulse.collectors import (
    CommandEntry,
    DiffFile,
    GitState,
    HeatmapEntry,
    MomentumState,
    SystemState,
    command_distribution,
)


# =========================================================================
# Sparkline renderer (pure Rich, no external dependency)
# =========================================================================

SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], width: int = 20) -> str:
    """Render a list of float values as a sparkline string."""
    if not values:
        return "▁" * width
    mn, mx = min(values), max(values)
    rng = mx - mn if mx != mn else 1.0
    # Pad or trim to width
    if len(values) > width:
        values = values[-width:]
    elif len(values) < width:
        values = [mn] * (width - len(values)) + values
    return "".join(
        SPARK_CHARS[min(int((v - mn) / rng * 7), 7)] for v in values
    )


def drift_bar(minutes: float, width: int = 20) -> Text:
    """Render a drift meter as a colored progress bar.

    Green (< 15m) -> Yellow (< 30m) -> Orange (< 60m) -> Red (60m+)
    This is the novel "Drift Meter" concept.
    """
    fill = min(minutes / 60.0, 1.0)
    filled = int(fill * width)
    empty = width - filled

    if minutes < 15:
        color = "green"
    elif minutes < 30:
        color = "yellow"
    elif minutes < 60:
        color = "dark_orange"
    else:
        color = "red"

    text = Text()
    text.append("█" * filled, style=color)
    text.append("░" * empty, style="dim")
    return text


def flow_bar(score: float, width: int = 25) -> Text:
    """Render momentum flow score as a gradient bar."""
    filled = int((score / 100.0) * width)
    empty = width - filled

    if score >= 70:
        color = "green"
    elif score >= 40:
        color = "yellow"
    else:
        color = "red"

    text = Text()
    text.append("█" * filled, style=color)
    text.append("░" * empty, style="dim")
    text.append(f" {score:.0f}%", style=f"bold {color}")
    return text


# =========================================================================
# Git Pulse Widget
# =========================================================================

class GitPulse(Static, can_focus=True):
    """Real-time git awareness with drift detection.

    Novel concept: the drift meter fills up over time since last commit,
    shifting from green through yellow/orange to red. A visual reminder
    to commit early and often.
    """

    git_state: reactive[GitState] = reactive(GitState, recompose=True)

    def render(self):
        g = self.git_state

        if not g.is_repo:
            return Panel(
                Text("Not a git repository", style="dim italic"),
                title="[bold]Git Pulse[/]",
                border_style="dim",
            )

        # Branch line with ahead/behind
        branch_text = Text()
        branch_text.append("  ", style="green")
        branch_text.append(g.branch, style="bold cyan")
        if g.ahead or g.behind:
            branch_text.append("  ")
            if g.ahead:
                branch_text.append(f"↑{g.ahead}", style="green")
            if g.behind:
                branch_text.append(f" ↓{g.behind}", style="red")

        # Changes summary
        changes = Text()
        if g.is_clean:
            changes.append("  Clean", style="green")
        else:
            parts = []
            if g.staged:
                parts.append(f"+{g.staged} staged")
            if g.modified:
                parts.append(f"~{g.modified} modified")
            if g.untracked:
                parts.append(f"?{g.untracked} untracked")
            if g.conflicts:
                parts.append(f"!{g.conflicts} conflicts")
            changes.append("  " + "  ".join(parts), style="yellow")

        if g.stash_count:
            changes.append(f"  [{g.stash_count} stashed]", style="dim")

        # Drift meter (novel concept)
        drift_text = Text()
        drift_text.append("  DRIFT  ", style="bold")
        drift_text.append_text(drift_bar(g.drift_minutes, 16))
        mins = g.drift_minutes
        if mins < 60:
            drift_text.append(f"  {mins:.0f}m", style="dim")
        else:
            drift_text.append(f"  {mins / 60:.1f}h", style="bold red")

        # Last commit
        commit_text = Text()
        commit_text.append("  ", style="dim")
        commit_text.append(
            g.last_commit_msg[:50] if g.last_commit_msg else "no commits",
            style="dim italic",
        )

        # Determine border color from drift level
        border_colors = {
            "calm": "green",
            "warm": "yellow",
            "hot": "dark_orange",
            "critical": "red",
        }
        border = border_colors.get(g.drift_level, "blue")

        content = Group(branch_text, changes, Text(""), drift_text, commit_text)
        return Panel(content, title="[bold]Git Pulse[/]", border_style=border)


# =========================================================================
# System Vitals Widget
# =========================================================================

class SystemVitals(Static, can_focus=True):
    """CPU, memory, disk, and network as sparkline visualizations."""

    sys_state: reactive[SystemState] = reactive(SystemState, recompose=True)

    def render(self):
        s = self.sys_state

        def _color(pct: float) -> str:
            if pct < 50:
                return "green"
            elif pct < 80:
                return "yellow"
            return "red"

        table = Table.grid(padding=(0, 1))
        table.add_column(width=4, justify="right")
        table.add_column(width=22)
        table.add_column(width=16, justify="right")

        # CPU with sparkline history
        cpu_spark = sparkline(s.cpu_history, 20)
        table.add_row(
            Text("CPU", style="bold"),
            Text(cpu_spark, style=_color(s.cpu_percent)),
            Text(f"{s.cpu_percent:4.0f}%", style=f"bold {_color(s.cpu_percent)}"),
        )

        # Memory
        mem_fill = int((s.memory_percent / 100) * 20)
        mem_bar = "█" * mem_fill + "░" * (20 - mem_fill)
        mem_detail = Text()
        mem_detail.append(f"{s.memory_percent:4.0f}%", style=f"bold {_color(s.memory_percent)}")
        mem_detail.append(f" {s.memory_used_gb}/{s.memory_total_gb}G", style="dim")
        table.add_row(
            Text("MEM", style="bold"),
            Text(mem_bar, style=_color(s.memory_percent)),
            mem_detail,
        )

        # Disk
        disk_fill = int((s.disk_percent / 100) * 20)
        disk_bar = "█" * disk_fill + "░" * (20 - disk_fill)
        disk_detail = Text()
        disk_detail.append(f"{s.disk_percent:4.0f}%", style=f"bold {_color(s.disk_percent)}")
        disk_detail.append(f" {s.disk_used_gb}/{s.disk_total_gb}G", style="dim")
        table.add_row(
            Text("DSK", style="bold"),
            Text(disk_bar, style=_color(s.disk_percent)),
            disk_detail,
        )

        # Network throughput
        def _fmt_bytes(b: int) -> str:
            if b > 1_000_000:
                return f"{b / 1_000_000:.1f}MB/s"
            elif b > 1_000:
                return f"{b / 1_000:.0f}KB/s"
            return f"{b}B/s"

        net_text = Text(f"↑{_fmt_bytes(s.net_sent_bytes)} ↓{_fmt_bytes(s.net_recv_bytes)}", style="cyan")
        table.add_row(
            Text("NET", style="bold"),
            net_text,
            Text(f"{s.process_count}", style="dim"),
        )

        # Load average
        load_color = _color(s.load_avg_1m * 25)  # Rough scaling
        table.add_row(
            Text("LOAD", style="bold"),
            Text(f"{s.load_avg_1m}", style=load_color),
            Text("1m", style="dim"),
        )

        return Panel(table, title="[bold]System Vitals[/]", border_style="blue")


# =========================================================================
# Command Flow Widget (Novel)
# =========================================================================

# Category display colors
CATEGORY_COLORS = {
    "git": "green",
    "python": "yellow",
    "node": "cyan",
    "build": "magenta",
    "navigate": "blue",
    "edit": "white",
    "docker": "dark_orange",
    "shell": "dim",
    "network": "bright_cyan",
    "claude": "bright_magenta",
    "other": "dim",
}

# Category icons
CATEGORY_ICONS = {
    "git": "●",
    "python": "◆",
    "node": "■",
    "build": "▲",
    "navigate": "→",
    "edit": "✎",
    "docker": "⬡",
    "shell": "○",
    "network": "◎",
    "claude": "◈",
    "other": "·",
}


class CommandFlow(Static, can_focus=True):
    """Command history as a semantic stream.

    Novel concept: instead of a flat history list, commands are grouped
    by category and rendered as a flowing river of colored symbols.
    You can see your work patterns at a glance — heavy git? lots of navigation?
    """

    commands: reactive[list] = reactive(list, recompose=True)

    def render(self):
        entries: list[CommandEntry] = self.commands

        if not entries:
            return Panel(
                Text("No command history found", style="dim italic"),
                title="[bold]Command Flow[/]",
                border_style="blue",
            )

        # Distribution bar
        dist = command_distribution(entries)
        total = sum(dist.values())

        dist_text = Text()
        for cat, count in sorted(dist.items(), key=lambda x: -x[1]):
            if count == 0:
                continue
            icon = CATEGORY_ICONS.get(cat, "·")
            color = CATEGORY_COLORS.get(cat, "dim")
            dist_text.append(f" {icon} {cat}:{count} ", style=color)

        # Flow stream: render last 60 commands as category symbols
        flow_text = Text()
        recent = entries[-60:]
        for e in recent:
            icon = CATEGORY_ICONS.get(e.category, "·")
            color = CATEGORY_COLORS.get(e.category, "dim")
            flow_text.append(icon, style=color)

        # Recent commands (last 5)
        recent_text = Text()
        for e in entries[-5:]:
            color = CATEGORY_COLORS.get(e.category, "dim")
            icon = CATEGORY_ICONS.get(e.category, "·")
            cmd_display = e.raw[:55] if len(e.raw) > 55 else e.raw
            recent_text.append(f"  {icon} ", style=color)
            recent_text.append(f"{cmd_display}\n", style="dim")

        content = Group(
            dist_text,
            Text(""),
            flow_text,
            Text(""),
            recent_text,
        )
        return Panel(content, title="[bold]Command Flow[/]", border_style="blue")


# =========================================================================
# Momentum Tracker Widget (Novel)
# =========================================================================

class MomentumTracker(Static, can_focus=True):
    """Developer momentum and flow detection.

    Novel concept: tracks your command diversity, commit velocity,
    and drift score to compute a "flow score" — are you in the zone
    or spinning your wheels?
    """

    momentum: reactive[MomentumState] = reactive(MomentumState, recompose=True)

    def render(self):
        m = self.momentum

        # Session duration
        hours = int(m.session_duration_minutes // 60)
        mins = int(m.session_duration_minutes % 60)
        duration = f"{hours}h {mins}m" if hours else f"{mins}m"

        table = Table.grid(padding=(0, 2))
        table.add_column(width=12)
        table.add_column(width=30)

        table.add_row(
            Text("Session", style="bold"),
            Text(duration, style="cyan"),
        )
        table.add_row(
            Text("Commits/hr", style="bold"),
            Text(
                f"{m.commit_velocity_per_hour:.1f}",
                style="green" if m.commit_velocity_per_hour >= 1 else "yellow",
            ),
        )
        table.add_row(
            Text("Diversity", style="bold"),
            Text(f"{m.command_diversity:.0%}", style="cyan"),
        )

        # Flow score bar (novel)
        flow_text = Text()
        flow_text.append("Flow  ", style="bold")
        flow_text.append_text(flow_bar(m.flow_score, 20))

        content = Group(table, Text(""), flow_text)
        return Panel(content, title="[bold]Momentum[/]", border_style="magenta")


# =========================================================================
# Diff Explorer Widget (Novel: visual git change review)
# =========================================================================

STATUS_ICONS = {
    "M": ("~", "yellow"),
    "A": ("+", "green"),
    "D": ("-", "red"),
    "R": ("R", "cyan"),
    "?": ("?", "dim"),
}


def change_fingerprint(diff_lines: list[str], width: int = 10) -> Text:
    """Visual fingerprint showing WHERE in a file changes occur.

    Novel concept: each block represents a portion of the file.
    Bright green = changes there, dim = unchanged.
    Gives an instant visual map of change locations without reading the diff.
    """
    if not diff_lines:
        return Text("." * width, style="dim")

    max_line = 1
    change_regions: list[tuple[int, int]] = []

    for line in diff_lines:
        if line.startswith("@@"):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or 1)
                end = start + count
                max_line = max(max_line, end)
                change_regions.append((start, end))

    if not change_regions:
        return Text("." * width, style="dim")

    text = Text()
    for i in range(width):
        block_start = (i / width) * max_line
        block_end = ((i + 1) / width) * max_line
        has_change = any(
            rs < block_end and re_ > block_start
            for rs, re_ in change_regions
        )
        if has_change:
            text.append("\u2593", style="bright_green")
        else:
            text.append("\u2591", style="dim")

    return text


def diff_density(insertions: int, deletions: int, width: int = 10) -> Text:
    """Colored bar: green proportion = adds, red = deletes."""
    total = insertions + deletions
    if total == 0:
        return Text("." * width, style="dim")

    ins_w = max(1, int((insertions / total) * width)) if insertions else 0
    del_w = width - ins_w

    text = Text()
    if ins_w:
        text.append("\u2588" * ins_w, style="green")
    if del_w:
        text.append("\u2588" * del_w, style="red")
    return text


def render_diff_lines(diff_lines: list[str], max_lines: int = 25) -> Text:
    """Render actual diff content with syntax-aware coloring."""
    text = Text()
    shown = 0

    for line in diff_lines:
        if line.startswith(("diff --git", "index ")):
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue

        if line.startswith("@@"):
            text.append(f"  {line}\n", style="cyan dim")
            continue

        if shown >= max_lines:
            remaining = sum(
                1 for l in diff_lines
                if l.startswith("+") or l.startswith("-")
            ) - shown
            if remaining > 0:
                text.append(f"  ... {remaining} more change lines\n", style="dim")
            break

        if line.startswith("+"):
            text.append(f"  {line}\n", style="green")
            shown += 1
        elif line.startswith("-"):
            text.append(f"  {line}\n", style="red")
            shown += 1
        else:
            text.append(f"  {line}\n", style="dim")
            shown += 1

    return text


class DiffExplorer(Static, can_focus=True):
    """Novel git change reviewer with visual fingerprints.

    Navigate files with j/k or arrows, expand diffs with Enter,
    toggle all with a. Each file shows a change fingerprint
    (where changes are) and density bar (add/delete ratio).
    """

    diff_files: reactive[list] = reactive(list, recompose=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._selected_idx = 0
        self._expanded: set[str] = set()

    def on_key(self, event):
        files = self.diff_files
        if not files:
            return

        if event.key in ("j", "down"):
            if self._selected_idx < len(files) - 1:
                self._selected_idx += 1
                self.refresh(layout=True)
                event.stop()
        elif event.key in ("k", "up"):
            if self._selected_idx > 0:
                self._selected_idx -= 1
                self.refresh(layout=True)
                event.stop()
        elif event.key == "enter":
            if 0 <= self._selected_idx < len(files):
                path = files[self._selected_idx].path
                if path in self._expanded:
                    self._expanded.discard(path)
                else:
                    self._expanded.add(path)
                self.refresh(layout=True)
                event.stop()
        elif event.key == "a":
            if len(self._expanded) == len(files):
                self._expanded.clear()
            else:
                self._expanded = {f.path for f in files}
            self.refresh(layout=True)
            event.stop()

    def render(self):
        from pathlib import Path as P

        files: list[DiffFile] = self.diff_files

        # Clamp selection
        if files and self._selected_idx >= len(files):
            self._selected_idx = max(0, len(files) - 1)
        current_paths = {f.path for f in files}
        self._expanded = self._expanded & current_paths

        if not files:
            return Panel(
                Text("Working tree clean \u2014 no changes to review", style="green italic"),
                title="[bold]Diff Explorer[/]",
                subtitle="[dim]f: back to dashboard[/]",
                border_style="green",
            )

        parts: list[Text] = []

        # Group files by directory
        dirs: dict[str, list[tuple[int, DiffFile]]] = {}
        for idx, f in enumerate(files):
            dir_name = str(P(f.path).parent)
            if dir_name == ".":
                dir_name = "."
            dirs.setdefault(dir_name, []).append((idx, f))

        total_ins = sum(f.insertions for f in files)
        total_dels = sum(f.deletions for f in files)

        for dir_name, dir_files in dirs.items():
            if dir_name != ".":
                dir_text = Text()
                dir_text.append(f"  {dir_name}/", style="bold blue")
                parts.append(dir_text)

            for idx, f in dir_files:
                is_selected = idx == self._selected_idx
                is_expanded = f.path in self._expanded

                line = Text()

                # Selection indicator
                if is_selected:
                    arrow = " \u25be " if is_expanded else " \u25b8 "
                    line.append(arrow, style="bold cyan")
                else:
                    line.append("   ", style="dim")

                # Status icon
                icon, color = STATUS_ICONS.get(f.status, ("?", "dim"))
                line.append(f"{icon} ", style=f"bold {color}")

                # File name
                fname = P(f.path).name
                line.append(fname, style="bold white" if is_selected else "white")

                # Stats
                if f.insertions or f.deletions:
                    line.append(f"  +{f.insertions}", style="green")
                    line.append(f" -{f.deletions}", style="red")
                    line.append("  ")
                    line.append_text(diff_density(f.insertions, f.deletions, 8))
                    line.append(" ")
                    line.append_text(change_fingerprint(f.diff_lines, 10))
                elif f.status == "?":
                    line.append("  new file", style="dim italic")

                parts.append(line)

                # Expanded diff
                if is_expanded and f.diff_lines:
                    sep = Text("  " + "\u2500" * 50, style="dim")
                    parts.append(sep)
                    parts.append(render_diff_lines(f.diff_lines))
                    parts.append(sep)

        # Summary footer
        parts.append(Text(""))
        summary = Text()
        summary.append(f"  {len(files)} file{'s' if len(files) != 1 else ''}", style="bold")
        summary.append(f"  +{total_ins}", style="green")
        summary.append(f" -{total_dels}", style="red")
        summary.append("  \u2502  ", style="dim")
        summary.append("j/k", style="bold cyan")
        summary.append(": navigate  ", style="dim")
        summary.append("Enter", style="bold cyan")
        summary.append(": expand  ", style="dim")
        summary.append("a", style="bold cyan")
        summary.append(": all", style="dim")
        parts.append(summary)

        content = Group(*parts)
        return Panel(
            content,
            title="[bold]Diff Explorer[/]",
            subtitle="[dim]f: back to dashboard[/]",
            border_style="cyan",
        )


# =========================================================================
# File Heatmap Widget (Novel: churn frequency visualization)
# =========================================================================

class FileHeatmap(Static, can_focus=True):
    """File churn heatmap \u2014 which files change most often.

    Novel: visual heat bars show relative change frequency,
    color-graded from cool (blue) to hot (red).
    """

    heatmap: reactive[list] = reactive(list, recompose=True)

    def render(self):
        entries: list[HeatmapEntry] = self.heatmap

        if not entries:
            return Panel(
                Text("No commit history", style="dim italic"),
                title="[bold]File Heatmap[/]",
                border_style="blue",
            )

        max_count = max(e.commit_count for e in entries)

        parts: list[Text] = []
        for e in entries:
            line = Text()
            bar_width = 12
            fill = int((e.commit_count / max_count) * bar_width)
            empty = bar_width - fill

            ratio = e.commit_count / max_count
            if ratio > 0.75:
                color = "red"
            elif ratio > 0.5:
                color = "dark_orange"
            elif ratio > 0.25:
                color = "yellow"
            else:
                color = "blue"

            line.append("  ")
            line.append("\u2588" * fill, style=color)
            line.append("\u2591" * empty, style="dim")
            line.append(f" {e.path}", style="white")
            line.append(f" ({e.commit_count})", style="dim")

            parts.append(line)

        parts.append(Text(""))
        footer = Text()
        footer.append(f"  Top {len(entries)} hotspots", style="dim")
        parts.append(footer)

        content = Group(*parts)
        return Panel(
            content,
            title="[bold]File Heatmap[/]",
            subtitle="[dim]Churn frequency[/]",
            border_style="dark_orange",
        )
