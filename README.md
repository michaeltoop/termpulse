# termpulse

The convergent terminal dashboard. Ambient developer intelligence that adapts to your workflow.

```
┌──────────────────────────────────────────────────────────────────┐
│  termpulse        myproject        main ↑2                14:23 │
├─────────────────────────┬────────────────────────────────────────┤
│  Git Pulse              │  System Vitals                        │
│                         │                                        │
│  ● main  ↑2 ↓0         │  CPU  ▁▂▃▅▇▅▃▂▁▂▃▅▇▅▃▂▁▁  23%      │
│  +3 staged  ~1 modified │  MEM  ████████████████░░░░  81%      │
│                         │  DSK  ████░░░░░░░░░░░░░░░░   4%      │
│  DRIFT  ████████░░░░░░  │  NET  ↑12KB/s ↓340KB/s               │
│         23m             │  LOAD 2.41                             │
├─────────────────────────┴────────────────────────────────────────┤
│  Command Flow                                                    │
│  ● git:9  ◆ python:12  → navigate:13  ◈ claude:3  ⬡ docker:3  │
│  ●●◆◆→→→◆●→→◆◆●→→→●◆◆→◈◈→→◆◆◆●→→→●◆→→◆◆●●→→→◆●◆→          │
├──────────────────────────────────────────────────────────────────┤
│  Momentum         Session: 2h 15m   Commits/hr: 1.8            │
│  Flow  █████████████████░░░░░░░░ 68%                            │
└──────────────────────────────────────────────────────────────────┘
```

## Novel Concepts

### Drift Meter

Time since your last commit, visualized as a filling bar that shifts color:

- **Green** (< 15m) — You're committing regularly
- **Yellow** (< 30m) — Getting long, consider a checkpoint
- **Orange** (< 60m) — Drift detected, commit something
- **Red** (60m+) — Danger zone, you'll lose context

### Flow Score

A composite momentum metric combining:

- **Commit velocity** (40%) — commits per hour
- **Command diversity** (30%) — Shannon entropy of your command categories
- **Freshness** (30%) — inverse of drift time

High flow = you're productive. Low flow = you might be stuck.

### Command Archaeology

Your shell history rendered as a stream of colored symbols, grouped by category:

```
● git   ◆ python   ■ node   ▲ build   → navigate
✎ edit  ⬡ docker   ◎ network  ◈ claude  ○ shell
```

See your work patterns at a glance. Heavy git symbols? You're in a merge flow.
All navigation? You might be lost.

### Contextual Theming

The dashboard border colors shift based on your git state:

- Clean repo = calm blue borders
- Dirty with low drift = green/yellow
- High drift = orange/red borders

The dashboard *breathes* with your workflow.

## Install

```bash
pip install termpulse
```

Or from source:

```bash
git clone https://github.com/CodeTonight-SA/termpulse.git
cd termpulse
pip install -e .
```

## Usage

```bash
termpulse     # Launch the dashboard
tp            # Short alias
```

### Keybindings

| Key | Action |
|-----|--------|
| `q` | Quit |
| `r` | Refresh all panels |
| `g` | Focus git panel |
| `s` | Focus system panel |
| `c` | Focus commands panel |
| `m` | Focus momentum panel |
| `d` | Toggle dark/light theme |

## Requirements

- Python 3.10+
- A terminal with 256-color support (iTerm2, Ghostty, Warp, Kitty, etc.)

## How It Works

termpulse is built on four data collectors that run on convergence timers:

| Collector | Refresh | Data |
|-----------|---------|------|
| Git | 5s | Branch, changes, drift, commits |
| System | 2s | CPU, memory, disk, network |
| Commands | 10s | Shell history, categorization |
| Momentum | 5s | Flow score, velocity, diversity |

Each collector feeds a Textual widget that renders in real-time. The dashboard
adapts its appearance based on the data — borders, colors, and urgency all
shift with your workflow context.

## Architecture

```
termpulse/
├── __main__.py      # CLI entry point
├── app.py           # Textual app with convergence timers
├── app.tcss         # Textual CSS for layout and theming
├── collectors.py    # Data collection (git, system, commands, momentum)
└── widgets.py       # Rich/Textual widget renderers
```

Built with [Textual](https://textual.textualize.io) by Textualize.

## License

MIT
