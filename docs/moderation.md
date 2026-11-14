# Cord Native Moderation Engine

Cord provides first-class statements for server moderation actions. Instead of writing verbose API calls to fetch guild members, verify hierarchy, check bot permissions, and format audit logs, Cord handles these directly at the language level.

---

## 1. Moderation Statements

Cord introduces four dedicated statements:
1. `ban <target> [reason=<string>]`
2. `kick <target> [reason=<string>]`
3. `timeout <target> for <duration> [reason=<string>]`
4. `unban <target> [reason=<string>]`

All moderation statements automatically attach the specified `reason` to the server's Discord Audit Log.

---

## 2. The `timeout` Statement

The `timeout` statement applies Discord's Communication Disabled timeout to a guild member for a specified duration.

### Syntax
```cord
timeout <target> for <duration> [reason=<string>]
```

- `<target>`: A `Member` reference (e.g. passed as a command argument or retrieved from an event).
- `<duration>`: A Cord Duration literal such as `10m`, `1h`, `24h`, `7d` (Discord limits timeouts to a maximum of 28 days).
- `reason`: (Optional) String attached to the server audit log.

### Example
```cord
command mute(target: Member, duration: Duration = 10m, reason: String = "Rule violation"):
    require permission moderate_members
    timeout target for duration reason=reason
    reply "🔇 {target.mention} has been timed out for {duration}. Reason: {reason}"
```

---

## 3. The `ban` and `unban` Statements

### Syntax
```cord
ban <target> [reason=<string>]
unban <target> [reason=<string>]
```

- `<target>`: A `Member` or `User` instance.
- `reason`: (Optional) String description written to the guild audit log.

### Example
```cord
command banish(target: Member, reason: String = "Violation of server rules"):
    require permission ban_members
    
    if target.id == author.id:
        reply "❌ You cannot ban yourself."
        return

    ban target reason=reason
    reply "🔨 Successfully banned **{target.name}**. (Audit reason: {reason})"
    
    send #mod-logs embed:
        title "Audit: Member Banned"
        description "Target: {target.name} ({target.id})"
        color "#EF4444"
        field "Moderator" author.name inline=true
        field "Reason" reason inline=true
```

To unban a user by their ID or user object:

```cord
command pardon(user_id: String, reason: String = "Appeal granted"):
    require permission ban_members
    unban user_id reason=reason
    reply "🕊️ Unbanned user ID {user_id}."
```

---

## 4. The `kick` Statement

### Syntax
```cord
kick <target> [reason=<string>]
```

### Example
```cord
command eject(target: Member, reason: String = "Inappropriate behavior"):
    require permission kick_members
    kick target reason=reason
    reply "👢 Kicked **{target.name}** from the server."
```

---

## 5. Security: Declarative Permissions & Cooldowns

### `require permission <perm>`

Prevents unauthorized users from invoking sensitive moderation commands. If the author lacks the required permission, Cord halts execution and replies with an informative error message.

Available permissions:
- `administrator`
- `manage_guild`
- `manage_channels`
- `manage_messages`
- `moderate_members` (required for timeouts)
- `kick_members`
- `ban_members`
- `manage_roles`

### `cooldown <duration> per user|guild|channel`

Prevents command abuse by imposing an execution cooldown:

```cord
command warn(target: Member, reason = "Spam"):
    require permission moderate_members
    cooldown 5s per user
    # Command body
```

---

## 6. Complete Moderation Guard Bot (`moderation.cord`)

```cord
bot "ModShield"

config:
    prefix = "!"
    activity = "guarding servers"

when someone joins:
    send #welcome "Welcome {member.mention}! Please read the rules."

command warn(target: Member, reason: String = "No reason provided"):
    require permission moderate_members
    cooldown 3s per user

    if target.is_bot:
        reply "❌ You cannot warn a bot."
        return

    store.warns[target.id] = (store.warns[target.id] or 0) + 1
    total = store.warns[target.id]

    reply embed:
        title "⚠️ Member Warned"
        description "{target.mention} received a warning from {author.mention}."
        color "#F59E0B"
        field "Reason" reason inline=false
        field "Total Warnings" total inline=true

    # Auto-escalation: timeout at 3 warnings
    if total >= 3:
        timeout target for 1h reason="Exceeded warning threshold (3+ warnings)"
        send #mod-logs "🚨 {target.name} automatically timed out for 1 hour after reaching 3 warnings."

command mute(target: Member, duration: Duration = 10m, reason: String = "Rule violation"):
    require permission moderate_members
    timeout target for duration reason=reason
    reply "🔇 Timed out {target.name} for {duration}."

command banish(target: Member, reason: String = "Severe violation"):
    require permission ban_members
    ban target reason=reason
    reply "🔨 Successfully banned {target.name}."
```
