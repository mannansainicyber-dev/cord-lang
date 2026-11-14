# Contributing to Cord

Thank you for your interest in contributing to Cord! We welcome contributions from developers, language designers, and Discord bot creators of all backgrounds.

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/cord.git
   cd cord
   ```

2. **Create a virtual environment (optional but recommended):**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies and editable package:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify installation:**
   ```bash
   cord --version
   pytest
   ```

## Running Tests

Cord maintains a comprehensive, offline test suite. All tests execute without requiring a real Discord bot token or internet connection:

```bash
pytest
```

To run with verbose output:
```bash
pytest -v
```

## Code Guidelines

- **Architecture:** Keep the language parser (`lexer.py`, `parser.py`, `ast_nodes.py`) and execution engine (`interpreter.py`, `runtime.py`) cleanly separated from the Discord integration layer (`discord_adapter.py`).
- **Tests First:** Any new syntax, keyword, or runtime capability must include unit tests verifying both success cases and beginner-friendly error messages.
- **Error Messages:** When adding syntax checks or runtime constraints, always provide an actionable error message and a suggested hint (`💡 Hint: ...`).

## Pull Request Process

1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Ensure all tests pass: `pytest`.
3. Format your changes: `cord fmt` on any `.cord` examples.
4. Commit with clear, descriptive commit messages.
5. Open a Pull Request on GitHub describing your changes and motivation.
