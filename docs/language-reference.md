# Cord Language Reference Specification

A comprehensive specification of Cord's grammar, keywords, literals, type system, expressions, and runtime semantics.

---

## 1. Lexical Grammar

- **Indentation & Block Scoping:** Cord uses off-side indentation scoping with 4 spaces per block level. Tab characters are normalized to 4 spaces.
- **Comments:** Begin with `#` and extend to the end of the line.
- **Identifiers:** Match `[a-zA-Z_][a-zA-Z0-9_]*`.
- **Channel References:** `#name` (e.g. `#general`, `#mod-logs`).

### Literals

| Literal Type | Syntax & Examples | Description |
| :--- | :--- | :--- |
| **Integer** | `0`, `42`, `-10`, `1_000_000` | Signed 64-bit integers. Underscores permitted for readability. |
| **Float** | `3.14`, `-0.001`, `1e-4` | Double-precision IEEE 754 floating point numbers. |
| **Duration** | `500ms`, `5s`, `30m`, `2h`, `7d` | Time units: `ms` (milliseconds), `s` (seconds), `m` (minutes), `h` (hours), `d` (days). |
| **String** | `"Hello"`, `'world'`, `"Formatted {x + 1}"` | Single or double-quoted UTF-8 strings. Expressions inside `{...}` are evaluated in-scope. |
| **Boolean** | `true`, `false` | Boolean truth values. |
| **Null** | `null` | Absence of value or empty reference. |
| **List** | `[1, 2, "three", true]` | Dynamic array of heterogeneous elements. |
| **Map** | `{"key": "value", "count": 10}` | Key-value associative dictionary. |

---

## 2. Keywords

```text
bot          config       command      slash        prefix       both
mode         when         event        task         every        fn
if           elif         else         while        for          in
return       pass         reply        send         delete       require
permission   cooldown     per          ask          timeout      embed
title        description  color        thumbnail    image        footer
field        inline       and          or           not          true
false        null         ban          unban        kick         import
with         button       select       option       label        style
emoji        url          placeholder  min_values   max_values   default
is           clicked      chosen
```

---

## 3. Top-Level Declarations

### `bot <name>`
Sets the display identifier and name for the bot:
```cord
bot "Greeter"
```

### `config:`
Declares global bot configuration parameters:
```cord
config:
    prefix = "!"
    status = "online"
    activity = "with Cord"
```

### `command <name>[(args...)] [mode=slash|prefix|both]:`
Registers a command. By default, Cord registers commands under **Dual Modality** (callable via `/name` and `!name`).
```cord
command ping:
    reply "Pong!"

slash command banish(target: Member):
    ban target
```

### `when <event_phrase>:`
Declares an event trigger:
- `when someone joins:` (Member join event)
- `when someone leaves:` (Member leave event)
- `when someone sends a message:` (Message event)
- `when button "<id>" is clicked:` (Interactive button click)
- `when select "<id>" is chosen:` (Interactive select menu choice)

### `task <name> every <duration>:`
Registers a non-blocking background task running at the specified interval.
```cord
task audit_log every 1h:
    send #logs "Audit running."
```

### `fn <name>(args...):`
Declares a reusable user function:
```cord
fn square(x):
    return x * x
```

### `import "<path>"`
Imports another Cord source file:
```cord
import "./modules/moderation.cord"
```

---

## 4. Statements & Control Flow

### Assignments
- `var = expr`
- `var += expr`, `var -= expr`, `var *= expr`, `var /= expr`

### Conditionals
```cord
if condition:
    # body
elif other_condition:
    # body
else:
    # body
```

### Loops
```cord
for item in [1, 2, 3]:
    # body

while count > 0:
    count -= 1
```

### Actions & Discord Primitives
- `reply <expr> [with: <components>]`: Responds to the current command or event.
- `send <channel_ref> <expr> [with: <components>]`: Sends message to a named channel (`#welcome`).
- `delete [message]`: Deletes the target or triggering message.
- `ask for <var> [prompt] timeout=<duration>`: Suspends execution and awaits user reply.
- `ban <target> [reason=<string>]`: Bans target user from guild.
- `unban <target> [reason=<string>]`: Unbans target user from guild.
- `kick <target> [reason=<string>]`: Kicks target member from guild.
- `timeout <target> for <duration> [reason=<string>]`: Disables communication for member.
- `require permission <permission_name>`: Security guard; requires caller to hold permission.
- `cooldown <duration> per user|guild|channel`: Rate-limiting guard.

---

## 5. UI Components

### Inside `with:` block on `reply` or `send`:
```cord
reply "Choose:" with:
    button "btn_id":
        label "Click Me"
        style "primary" # primary | secondary | success | danger | link
        emoji "⚡"
    select "menu_id":
        placeholder "Choose option"
        min_values 1
        max_values 1
        option "opt1":
            label "Option 1"
            description "First option"
            emoji "1️⃣"
```

---

## 6. Built-in Runtime Functions

- `fetch(url, [options])`: Performs HTTP GET request.
- `http.get(url, [headers], [params])`: HTTP GET with custom headers/params.
- `http.post(url, [json], [headers])`: HTTP POST with JSON body.
- `http.delete(url, [headers])`: HTTP DELETE request.
- `store`: Embedded persistent SQLite dictionary store.
- `time.now()`: Current UNIX timestamp in seconds.
- `len(sequence)`: Length of string, list, or map.
- `random(min, max)`: Random integer in range `[min, max]`.
- `floor(number)` / `ceil(number)`: Math rounding functions.
- `env(name, [default])`: Read host environment variable.
