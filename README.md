<div align="center">

# ⚡ Cord

**An expressive, beginner-friendly programming language designed specifically for building Discord bots.**

[![CI](https://github.com/your-username/cord/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/cord/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: Cord](https://img.shields.io/badge/code%20style-cord-purple.svg)](https://github.com/your-username/cord)

</div>

---

## 🌟 Vision

Cord bridges the gap between beginners and experienced programmers:

- **Beginner Mode:** Readable English-like triggers (`when someone joins:`), clean keywords (`reply`, `ask for`), minimal boilerplate, and helpful diagnostic hints.
- **Developer Mode:** Expressive control flow, functions (`fn`), typed argument signatures (`target: Member`), permissions guards, cooldowns, persistent state (`store`), and background tasks.

Both styles belong to the **same unified grammar and runtime**. You can mix them freely in the same `.cord` file.

---

## 🚀 Key Features

- 🔄 **Hybrid Dual-Command Dispatch:** Declare a command once; Cord registers it as **both a slash command (`/`) and a prefix command (`!`)** automatically (or optionally restrict with `slash command` or `prefix command`).
- 💾 **Built-in Persistent Storage:** An embedded, atomic SQLite store accessible via `store` that survives bot restarts without database setup.
- 🎨 **Declarative Embed Builder:** Clean, indentation-based embed definitions without tedious object hierarchies.
- 🛡️ **Declarative Permissions & Cooldowns:** Protect administrative commands with simple `require permission` and `cooldown` guards.
- 💬 **Interactive Prompts:** Pause execution and await conversational input with `ask for <var> [prompt] timeout=<duration>`.
- 🧪 **Offline & Token-Free Testability:** A decoupled runtime with a `MockDiscordAdapter` that allows full end-to-end bot testing without internet access or real bot credentials.
- 🛠️ **Developer Tooling:** Built-in CLI with `cord run`, `cord check`, `cord fmt`, and `cord init`.

---

## 📦 Installation

Cord requires **Python 3.10+**.

```bash
# Clone the repository
git clone https://github.com/your-username/cord.git
cd cord

# Install editable package
pip install -e .
```

Verify installation:
```bash
cord --version
# Output: Cord 0.1.0 (Python 3.14.4)
```

---

## ⚡ Quickstart

### 1. Initialize a Project
```bash
cord init my-bot
cd my-bot
```

### 2. Configure Token
Copy `.env.example` to `.env` and add your bot token from the [Discord Developer Portal](https://discord.com/developers/applications):
```bash
cp .env.example .env
```

### 3. Check & Run
```bash
# Verify syntax offline
cord check bot.cord

# Start the bot
cord run bot.cord
```

---

## 📝 Syntax Showcase

### Beginner Mode (`bot.cord`)

```cord
bot "Helper"

config:
    prefix = "!"
    activity = "with Cord"

when someone joins:
    send #welcome "Welcome to our server, {member.name}!"

command ping:
    reply "Pong! Latency: {bot.latency}ms"

command greet:
    ask for name "What is your name?" timeout=30s
    if name == null:
        reply "You didn't answer in time!"
    else:
        reply "Hello, {name}!"
```

### Developer Mode (`moderation.cord`)

```cord
bot "Guardian"

config:
    prefix = "!"

command warn(target: Member, reason = "No reason provided"):
    require permission moderate_members
    cooldown 5s per user

    if target.is_bot:
        reply "❌ Bots cannot be warned."
        return

    if not store.has("warns"):
        store.warns = {}

    count = store.warns.get(target.id, 0) + 1
    store.warns[target.id] = count

    reply embed:
        title "⚠️ Member Warned"
        description "{target.mention} received a warning from {author.mention}."
        color "#F59E0B"
        field "Reason" reason inline=false
        field "Total Warnings" count inline=true

    send #mod-logs embed:
        title "Audit Entry"
        description "Action: Warned {target.name}"
        color "#EF4444"
        field "Moderator" author.name inline=true
        field "Reason" reason inline=true
```

---

## 💻 CLI Commands

| Command | Description |
| :--- | :--- |
| `cord run <file.cord>` | Executes the Cord bot file using Discord gateway. |
| `cord check <file.cord>` | Validates syntax, indentation, and structure without running. |
| `cord fmt <file.cord> [-w]` | Formats source code indentation and whitespace. |
| `cord init [name]` | Scaffolds a complete starter project. |
| `cord --version` | Displays version and Python runtime details. |

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│                      CLI: `cord`                       │
│    (cord run, cord check, cord fmt, cord init, etc.)   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    Cord Compiler Core                  │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────┐ │
│  │    Lexer     ├────►│    Parser    ├────►│   AST   │ │
│  │ (Indentation)│     │(Recursive-D.)│     │  Nodes  │ │
│  └──────────────┘     └──────────────┘     └────┬────┘ │
└─────────────────────────────────────────────────┼──────┘
                                                  │
┌─────────────────────────────────────────────────▼──────┐
│                    Execution Engine                    │
│  ┌───────────────────────┐   ┌───────────────────────┐ │
│  │      Interpreter      │   │     Type & Scope      │ │
│  │ (AST-walking runtime) │   │      Environment      │ │
│  └───────────┬───────────┘   └───────────────────────┘ │
│              │                                         │
│  ┌───────────▼───────────┐   ┌───────────────────────┐ │
│  │    Persistent Store   │   │    Security Sandbox   │ │
│  │     (SQLite Layer)    │   │ (Capability Barrier)  │ │
│  └───────────────────────┘   └───────────────────────┘ │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│                 Discord Adapter Layer                  │
│       (discord.py / disnake backend abstraction)       │
│  ┌───────────────────┐               ┌───────────────┐ │
│  │ Dual-Command Reg. │               │ Event Router  │ │
│  │  (Slash + Prefix) │               │   & Hooks     │ │
│  └───────────────────┘               └───────────────┘ │
└────────────────────────────────────────────────────────┘
```

---

## 🔒 Security & Sandboxing

Cord does **not** evaluate scripts using Python's `eval` or `exec`. It runs on a strictly controlled tree-walking interpreter.
- Tokens are loaded exclusively through environment variables or `.env`.
- Secrets are never exposed in traceback logs.
- Standard scripts cannot import arbitrary host OS modules (`os`, `sys`, `subprocess`).

*Note:* While the custom interpreter prevents arbitrary code execution, production multi-tenant deployments should enforce container-level isolation (e.g. Docker).

---

## 📚 Documentation

- [Getting Started](docs/getting-started.md)
- [Installation Guide](docs/installation.md)
- [Beginner Mode Guide](docs/beginner-mode.md)
- [Developer Mode Guide](docs/developer-mode.md)
- [Language Reference](docs/language-reference.md)
- [Discord API Mapping](docs/discord-api.md)

---

## 🧪 Testing

Cord comes with an automated test suite:

```bash
pytest
```

---

## 📄 License

Cord is distributed under the [MIT License](LICENSE).
