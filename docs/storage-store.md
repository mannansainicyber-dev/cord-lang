# Cord Persistent Storage & SQLite Store

Every Cord bot includes an embedded, zero-configuration SQLite document and key-value store accessible via the `store` keyword. You do not need database servers, ORMs, connection pools, or schema migrations.

---

## 1. Overview

Variables defined inside commands or events are ephemeral and reset when the command finishes. The `store` object persists data directly to an embedded SQLite database (`.cord_store.db` in your bot's directory).

```cord
command level:
    current_xp = store.xp.get(author.id, 0)
    reply "{author.name}, you have **{current_xp} XP**!"
```

When you stop and restart the bot, or reboot the server, all values inside `store` remain intact.

---

## 2. Reading and Writing to the Store

### Direct Property Access
```cord
# Storing a simple string, number, or boolean
store.bot_version = "1.0.0"
store.maintenance_mode = false
store.total_messages = (store.total_messages or 0) + 1
```

### Working with Nested Maps (Dictionaries)
```cord
# Storing per-user economy balances
if not store.has("balances"):
    store.balances = {}

# Updating a user balance
store.balances[author.id] = 500
```

### Retrieving with Default Fallbacks: `.get(key, default)`
Use `.get()` to safely read keys that might not exist yet:
```cord
coins = store.balances.get(author.id, 0)
```

### Checking Existence: `.has(key)`
```cord
if store.has("config_role"):
    role_id = store.config_role
```

### Deleting Keys
```cord
store.delete("temporary_session_id")
```

---

## 3. Atomic Transactions & Thread Safety

Every write to `store` is committed via an atomic SQLite transaction with file-locking enabled. Even under heavy concurrency with hundreds of simultaneous Discord interactions, data corruption is prevented.

---

## 4. Complete Example: Economy & Daily Rewards Bot

```cord
bot "GoldRush"

config:
    prefix = "!"

command daily:
    cooldown 24h per user
    
    if not store.has("wallet"):
        store.wallet = {}

    current_gold = store.wallet.get(author.id, 0)
    new_gold = current_gold + 250
    store.wallet[author.id] = new_gold

    reply embed:
        title "💰 Daily Reward Claimed!"
        description "Added **250 Gold** to your vault."
        color "#F59E0B"
        field "New Balance" "{new_gold} Gold" inline=true

command balance(target: Member = null):
    user = target or author
    gold = store.wallet.get(user.id, 0)
    reply "💳 {user.mention} currently holds **{gold} Gold**."

command pay(target: Member, amount: Integer):
    if amount <= 0:
        reply "❌ Amount must be positive."
        return

    sender_gold = store.wallet.get(author.id, 0)
    if sender_gold < amount:
        reply "❌ Insufficient gold! You only have {sender_gold} Gold."
        return

    # Atomic transfer
    store.wallet[author.id] = sender_gold - amount
    target_gold = store.wallet.get(target.id, 0)
    store.wallet[target.id] = target_gold + amount

    reply "💸 Transferred **{amount} Gold** from {author.mention} to {target.mention}."
```
