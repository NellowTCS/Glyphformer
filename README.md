# Glyphformer

[![Python >=3.12](https://img.shields.io/badge/python-%3E%3D3.12-blue?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub](https://img.shields.io/badge/GitHub-NellowTCS%2FpyComputer-181717?logo=github)](https://github.com/NellowTCS/pyComputer)
[![PyPI - SDK](https://img.shields.io/badge/PyPI-pycomputersdk-blue?logo=pypi)](https://pypi.org/project/pycomputersdk/)

A 2D text-based platformer built with pyComputerSDK. Jump, collect coins, reach the flag, and don't die.

## Play It

The easiest way to play is inside [pyComputer](https://github.com/NellowTCS/pyComputer). Open the shell and run:

```bash
pkg install glyphformer
run glyphformer
```

Or try the [live demo](https://nellowtcs.me/pyComputer) in your browser, install glyphformer from inside the OS, and play it there.

You can also run it standalone on your machine:

```bash
pip install pycomputersdk
python main.py
```

## Gameplay

Navigate a character through scrolling levels rendered entirely in terminal characters. Collect coins, dodge spikes, avoid pits, and reach the flag to advance.

- **5 levels** with increasing difficulty
- **Physics**: gravity, variable-height jumps, coyote time, jump buffering, fast-fall
- **AABB collision** with per-axis resolution and sub-stepping (4 sub-steps/frame)
- **Scrolling camera** (36x20 viewport)
- **HUD**: level name, coin counter, timer, lives
- **3 lives** - lose them all and it's game over

### Controls

| Key          | Action            |
|--------------|-------------------|
| WASD/Arrows  | Move / Jump       |
| S / Down     | Fast-fall         |
| R            | Restart level     |
| P / Esc      | Pause             |

## Running Inside pyComputer

Glyphformer is distributed as a `.pycapp` bundle. From the pyComputer shell:

```bash
pkg install glyphformer   # install from path
run glyphformer           # launch the game
```

## Architecture

Single-file game loop in `main.py` with level data in `levels/`. Uses `pycomputersdk` for terminal rendering, raw input, and web platform detection.

- Level tiles are defined as string grids in `levels/level_XX.py`
- The physics engine handles collision response, velocity, and state updates
- Rendering is frame-delta-based with a 30 FPS target

## Built With

- [pyComputer](https://github.com/NellowTCS/pyComputer) - Virtual computer environment
- [pyComputerSDK](https://pypi.org/project/pycomputersdk/) - SDK for building pyComputer apps

## License

MIT
