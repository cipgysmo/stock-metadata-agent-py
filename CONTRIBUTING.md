# Contributing

## Development Setup

```bash
# Clone and set up
git clone https://github.com/cipgysmo/stock-metadata-agent-py.git
cd stock-metadata-agent-py
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run directly (no build required)
python main.py
```

## Running Tests

```bash
.venv/bin/python -m pytest tests/ -v
# On Windows: .venv\Scripts\python -m pytest tests/ -v
```

## Project Conventions

- **Python 3.10+** required
- **Type hints** on all function signatures
- **Dataclasses** for structured data (`FileResult`, `VisionAnalysis`, `GeneratedMetadata`)
- **Logging** via `logging.getLogger(__name__)`, no print statements
- **Thread safety**: All UI updates from worker threads go through Qt signals (`QueuedConnection`)
- **Settings**: Persisted to `~/.stock-metadata-agent/settings.json` via `config/settings.py`
- **Constants**: Centralized in `config/constants.py` — no magic numbers in code

## Adding a New Module

1. Create the module under the appropriate package (`core/`, `ai/`, `export/`, etc.)
2. Add `__init__.py` if creating a new package
3. Import in `main.py` if needed for initialization
4. Add tests to `tests/test_all.py`

## Code Style

- 4-space indentation
- Docstrings on all public classes and methods
- Constants in UPPER_SNAKE_CASE in `config/constants.py`
- Private methods prefixed with `_`
- Max line length: 120 characters

## Build Process

```bash
# macOS
./build.sh

# Windows
build.bat

# Or manually
.venv/bin/pyinstaller --clean stock-metadata-agent.spec
```

The `.spec` file bundles the Python interpreter, all dependencies, and platform-specific exiftool binaries into a single distributable.

## Pull Request Process

1. Fork the repository
2. Create a feature branch from `master`
3. Make changes, add tests
4. Run tests locally: `python -m pytest tests/`
5. Verify the app launches: `python main.py`
6. Submit PR with description of changes

## Reporting Issues

Include:
- Platform (macOS/Windows/Linux) and version
- Steps to reproduce
- Error messages or screenshots
- Sample files that trigger the issue (if applicable)
