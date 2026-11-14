# Cord Developer Tooling & CLI Ecosystem

Cord provides an end-to-end suite of developer tools designed to boost productivity, ensure code correctness before deployment, and simplify production operations.

---

## 1. The `cord` CLI Overview

Run `cord --help` to view all available commands:

```text
Usage: cord [OPTIONS] COMMAND [ARGS]...

Commands:
  run      Launch your Discord bot with live execution
  check    Perform offline static syntax and type validation
  repl     Start an interactive read-eval-print loop
  docker   Generate production Dockerfile and compose configs
  init     Scaffold a new production-ready Cord bot project
  test     Run automated unit tests on bot commands
```

---

## 2. Interactive Shell: `cord repl`

The built-in REPL lets you test expressions, inspect the AST, test HTTP requests, and explore built-ins without running a live Discord bot.

```bash
cord repl
```

```text
Cord Language Interactive Shell v0.2.0 (Python 3.12.3)
Type expressions to evaluate, or 'help' for built-in commands.

cord > 5 + 3 * 2
11

cord > format_coins = fn(x): return "${x:,}"
Defined function 'format_coins'

cord > format_coins(1000000)
"$1,000,000"

cord > res = fetch("https://dummyjson.com/quotes/1")
cord > res.quote
"Life isn’t about getting and having, it’s about giving and being."
```

### Multiline Statements in REPL
You can declare multi-line commands or functions in the REPL; simply indent four spaces on continuation lines, and press Return on an empty line to evaluate.

---

## 3. Static Code Linter: `cord check`

Before connecting to the Discord gateway, validate your `.cord` scripts offline:

```bash
cord check bot.cord
```

If any errors exist, Cord provides high-accuracy diagnostic reports:

```text
Error in bot.cord at Line 14, Column 5:
    14 |     reply "Hello"
                     ^
SyntaxError: Indentation level does not match expected block depth (expected 4 spaces, found 8).
```

---

## 4. Production Deployment: `cord docker`

Deploying to production with Docker is a single command in Cord:

```bash
cord docker --compose
```

This generates two production-hardened files:
1. `Dockerfile`: A lean, multi-stage container build based on `python:3.12-slim`.
2. `docker-compose.yml`: With automatic container restart policies, environment variable injection, and persistent volume mounts for `.cord_store.db`.

To launch:
```bash
docker compose up -d
```

---

## 5. Offline Testing: `cord test`

Cord bots are designed to be tested offline without Discord tokens using the decoupled `MockDiscordAdapter`:

```bash
cord test
```

You can write automated tests in Python with `pytest` using Cord's mock adapter:

```python
import pytest
from cord.interpreter import Interpreter
from cord.discord_adapter import MockDiscordAdapter

@pytest.mark.asyncio
async def test_ping_command():
    source = '''
    bot "TestBot"
    command ping:
        reply "Pong!"
    '''
    interpreter = Interpreter()
    ast = interpreter.parse(source)
    adapter = MockDiscordAdapter(interpreter)
    await interpreter.execute_ast(ast, adapter)
    
    response = await adapter.dispatch_command("ping", author="tester#0001")
    assert response.content == "Pong!"
```

---

## 6. VS Code Extension & Syntax Highlighting

Cord includes a TextMate grammar extension for Visual Studio Code located in `editors/vscode`:

- Accurate syntax coloring for keywords, durations, strings, channels, and components.
- Automatic 4-space indentation and colon completion.
- Comment toggling (`Ctrl+/` or `Cmd+/`).

To install into VS Code:
```bash
cp -r editors/vscode ~/.vscode/extensions/cord-lang
```
Or symlink it directly.
