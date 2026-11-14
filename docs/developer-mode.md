# Developer Mode Guide

For experienced programmers, Cord provides expressive syntax, modular abstractions, typed argument parsing, robust permissions, persistent state, and background tasks.

---

## 1. Explicit Modality

While commands are dual-dispatch by default, you can restrict their modality:

```cord
# Available ONLY as a slash command (e.g. /settings)
slash command settings:
    reply "Server settings panel"

# Available ONLY as a text prefix command (e.g. !help)
prefix command help:
    reply "Text-based help directory"

# Explicit mode parameter
command stats mode=slash:
    reply "Slash stats"
```

---

## 2. Parameter Signatures & Argument Types

Add type conversion hints to automatically parse mentions and arguments:

```cord
command warn(target: Member, count: Int = 1, reason: String = "No reason provided"):
    reply "Warned {target.name} {count} times. Reason: {reason}"
```

Supported type hints:
- `Member` / `User` — Converts `<@123456789>` or numeric ID to a Member object.
- `Int` — Converts string input to an integer.
- `Float` — Converts string input to a floating-point number.
- `String` — Standard string.

---

## 3. Permission Guards & Cooldowns

Protect administrative commands with declarative guards:

```cord
command kick(target: Member, reason = "Rules violation"):
    require permission kick_members
    cooldown 5s per user

    reply "Kicked {target.name}."
```

If a user without `kick_members` runs the command, Cord halts execution and replies with an actionable error.

---

## 4. First-Class Persistent Store

Cord embeds a persistent SQLite storage engine accessible via the `store` object:

```cord
# Nested dictionaries and counter increments
if not store.has("users"):
    store.users = {}

store.users[target.id] = {"xp": 100, "level": 1}
store.users[target.id]["xp"] += 25
```

Data in `store` is automatically saved and persists across bot restarts without manual database connection handling.

---

## 5. Functions & Subroutines

Organize reusable logic with `fn`:

```cord
fn calculate_level(xp):
    if xp < 100:
        return 1
    elif xp < 500:
        return 2
    return 3

command rank:
    xp = store.users.get(author.id, {}).get("xp", 0)
    lvl = calculate_level(xp)
    reply "Your level is: {lvl} ({xp} XP)"
```

---

## 6. Scheduled Periodic Tasks

Run background tasks directly inside the event loop:

```cord
task status_cycle every 15m:
    send #logs "System heartbeat: bot is active."
```
