# Cord Language Reference

A complete reference of Cord's grammar, keywords, expressions, and runtime semantics.

---

## 1. Lexical Structure

- **Indentation:** Off-side rule using 4 spaces per block level. Tabs are normalized to 4 spaces.
- **Comments:** Start with `#` and extend to the end of the line.
- **Identifiers:** Start with `[a-zA-Z_]` followed by alphanumeric characters or underscores.
- **Channel References:** `#name` (e.g. `#welcome`, `#bot-logs`).

### Literals

| Literal Type | Examples |
| :--- | :--- |
| **Integer** | `0`, `42`, `-10` |
| **Float** | `3.14`, `0.001` |
| **Duration** | `500ms`, `5s`, `30m`, `2h`, `7d` |
| **String** | `"Hello"`, `'world'`, `"Formatted {x + 1}"` |
| **Boolean** | `true`, `false` |
| **Null** | `null` |
| **List** | `[1, 2, "three"]` |
| **Map** | `{"key": "value", "count": 10}` |

---

## 2. Keywords

```text
bot        config     command    slash      prefix     both       mode
when       event      task       every      fn         if         elif
else       while      for        in         return     pass       reply
send       delete     require    permission cooldown   per        ask
timeout    embed      title      description color     thumbnail  image
footer     field      inline     and        or         not        true
false      null
```

---

## 3. Top-Level Declarations

### `bot <name>`
Sets the display name of the bot:
```cord
bot "GuardianBot"
```

### `config:`
Declares global bot settings:
```cord
config:
    prefix = "!"
    status = "online"
    activity = "with code"
```

### `command <name>[(args...)] [mode=slash|prefix|both]:`
Registers a command.
```cord
command ping:
    reply "Pong!"

slash command ban(target: Member):
    reply "Banned {target.name}"
```

### `when <event_phrase>:` / `event <name>(args...):`
Declares an event handler.
```cord
when someone joins:
    send #welcome "Welcome {member.name}!"
```

### `task <name> every <duration>:`
Declares a periodic background job.
```cord
task cleaner every 1h:
    send #logs "Hourly audit run complete."
```

### `fn <name>(args...):`
Declares a user function.
```cord
fn add(a, b):
    return a + b
```

---

## 4. Statements

- **Assignment:** `x = 10`, `x += 5`, `x -= 1`, `x *= 2`, `x /= 2`
- **Conditionals:**
  ```cord
  if condition:
      ...
  elif other:
      ...
  else:
      ...
  ```
- **Loops:**
  ```cord
  for item in list:
      ...
  while condition:
      ...
  ```
- **Actions:**
  - `reply <expression>`: Replies to trigger.
  - `reply embed:`: Builds and replies with a rich embed.
  - `send <channel> <expression>`: Sends to a channel.
  - `delete [message]`: Deletes message.
  - `require permission <perm_name>`: Guards command.
  - `cooldown <duration> per user|guild|channel`: Rate limits command.
  - `ask for <var> [prompt] timeout=<duration>`: Awaits user reply.
  - `return [expression]`: Returns from function.
  - `pass`: No-op.

---

## 5. Embed Block Syntax

```cord
reply embed:
    title "Title"
    description "Description"
    color "#5865F2"
    thumbnail "https://example.com/icon.png"
    image "https://example.com/banner.png"
    field "Field 1" "Value 1" inline=true
    field "Field 2" "Value 2" inline=false
    footer "Footer text"
```
