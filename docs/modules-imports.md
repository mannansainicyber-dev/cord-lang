# Cord Multi-File Imports & Modular Architecture

As your Discord bot grows, keeping all commands, events, and utilities inside a single `bot.cord` file can become difficult to maintain. Cord provides a first-class module import system that allows splitting functionality across multiple files.

---

## 1. The `import` Statement

To load another Cord file, use the `import` statement followed by the relative file path as a string literal:

```cord
import "./helpers/math.cord"
import "./commands/moderation.cord"
import "./commands/economy.cord"
```

---

## 2. Path Resolution

- Relative paths are resolved **relative to the importing file's directory**.
- If no file extension is specified, Cord will automatically look for `.cord`.
- Both `./module.cord` and `module.cord` are supported.

### Recommended Project Layout

```text
my-production-bot/
├── bot.cord                # Main entry point (bot declaration & config)
├── .env                    # Discord token & credentials
├── config.cord             # Channel IDs, role constants
├── modules/
│   ├── moderation.cord     # Ban, kick, mute, warn commands
│   ├── economy.cord        # Daily rewards, balance, transfer
│   └── tickets.cord        # Support ticket UI components
└── utils/
    ├── embed_builder.cord  # Standardized embeds
    └── math_utils.cord     # Helper functions
```

---

## 3. Scope Sharing & Namespaces

When a module is imported:
- All top-level commands (`command name:`) and event listeners (`when someone joins:`) defined in the module are registered into the active bot runtime.
- Functions declared with `fn <name>():` become callable by the importing file and subsequent modules.
- The global `store` is shared across all modules, allowing cross-module data access.

### Example: Shared Math Utility (`utils/math_utils.cord`)

```cord
# utils/math_utils.cord

fn calculate_level(xp):
    return floor(xp / 100) + 1

fn format_coins(amount):
    return "{amount:,} Gold"
```

### Main Entrypoint (`bot.cord`)

```cord
# bot.cord
bot "ModularBot"

config:
    prefix = "!"

import "./utils/math_utils.cord"
import "./modules/economy.cord"

command profile:
    xp = store.xp.get(author.id, 0)
    level = calculate_level(xp)
    reply "Member: {author.name} | Level: {level}"
```

---

## 4. Circular Dependency Protection

Cord includes built-in cycle detection during module resolution. If file `A.cord` imports `B.cord`, and `B.cord` imports `A.cord`, Cord detects the cycle, prevents infinite loops, and evaluates each file exactly once.
