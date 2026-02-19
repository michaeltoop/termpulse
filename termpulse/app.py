"""termpulse — The convergent terminal dashboard.

A real-time TUI that provides ambient developer intelligence.
Every panel updates on a convergence timer, adapting to your workflow.

Novel concepts:
1. Drift Meter — time since last commit as escalating urgency bar
2. Momentum/Flow Score — composite metric of commit velocity + command diversity
3. Command Archaeology — shell history as a semantic stream of colored symbols
4. Contextual Theming — dashboard colors shift based on repository state

Built with Textual (https://textual.textualize.io).
"""

from __future__ import annotations

import os
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from termpulse.collectors import (
    collect_commands,
    collect_git,
    collect_momentum,
    collect_system,
)
from termpulse.widgets import (
    CommandFlow,
    GitPulse,
    MomentumTracker,
    SystemVitals,
)


class TermPulseHeader(Static):
    """Custom header showing project context."""

    def render(self):
        cwd = os.getcwd()
        project = Path(cwd).name
        text = Text()
        text.append(" termpulse ", style="bold white on dark_blue")
        text.append("  ", style="dim")
        text.append(f" {project} ", style="bold cyan")
        text.append("  ", style="dim")
        text.append(cwd, style="dim")
        return text


class TermPulseApp(App):
    """The convergent terminal dashboard."""

    TITLE = "termpulse"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("g", "focus_git", "Git"),
        ("s", "focus_system", "System"),
        ("c", "focus_commands", "Commands"),
        ("m", "focus_momentum", "Momentum"),
        ("d", "toggle_dark", "Theme"),
    ]

    def compose(self) -> ComposeResult:
        yield TermPulseHeader(id="header")
        with Horizontal():
            yield GitPulse(id="git-pulse")
            yield SystemVitals(id="system-vitals")
        yield CommandFlow(id="command-flow")
        yield MomentumTracker(id="momentum")
        yield Footer()

    def on_mount(self) -> None:
        """Start the convergence timers."""
        # Cached state for cross-widget sharing
        self._last_git = None
        self._last_commands = None

        # Git: refresh every 5 seconds
        self.set_interval(5.0, self._refresh_git)
        # System: refresh every 2 seconds
        self.set_interval(2.0, self._refresh_system)
        # Commands: refresh every 10 seconds
        self.set_interval(10.0, self._refresh_commands)
        # Momentum: refresh every 5 seconds
        self.set_interval(5.0, self._refresh_momentum)

        # Initial data load
        self._refresh_git()
        self._refresh_system()
        self._refresh_commands()
        self._refresh_momentum()

    def _refresh_git(self) -> None:
        """Collect and update git state."""
        state = collect_git()
        self._last_git = state
        widget = self.query_one("#git-pulse", GitPulse)
        widget.git_state = state

        # Contextual theming: update app classes based on drift
        self.remove_class("drift-calm", "drift-warm", "drift-hot", "drift-critical")
        if state.is_repo:
            self.add_class(f"drift-{state.drift_level}")

    def _refresh_system(self) -> None:
        """Collect and update system vitals."""
        state = collect_system()
        widget = self.query_one("#system-vitals", SystemVitals)
        widget.sys_state = state

    def _refresh_commands(self) -> None:
        """Collect and update command flow."""
        entries = collect_commands(limit=100)
        self._last_commands = entries
        widget = self.query_one("#command-flow", CommandFlow)
        widget.commands = entries

    def _refresh_momentum(self) -> None:
        """Collect and update momentum metrics, reusing cached git/command data."""
        git = self._last_git if self._last_git is not None else collect_git()
        commands = self._last_commands if self._last_commands is not None else collect_commands(limit=100)
        momentum = collect_momentum(git, commands)
        widget = self.query_one("#momentum", MomentumTracker)
        widget.momentum = momentum

    # Keybindings
    def action_refresh(self) -> None:
        """Manual refresh all panels."""
        self._refresh_git()
        self._refresh_system()
        self._refresh_commands()
        self._refresh_momentum()

    def action_focus_git(self) -> None:
        self.query_one("#git-pulse").focus()

    def action_focus_system(self) -> None:
        self.query_one("#system-vitals").focus()

    def action_focus_commands(self) -> None:
        self.query_one("#command-flow").focus()

    def action_focus_momentum(self) -> None:
        self.query_one("#momentum").focus()
