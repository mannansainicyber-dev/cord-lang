# Discord API & Entity Proxies

This document covers how Cord represents Discord entities (`author`, `member`, `channel`, `guild`) and maps them to Discord's interaction and event pipeline.

---

## 1. Context Objects

Inside commands and events, several contextual objects are automatically populated:

| Object | Type | Description |
| :--- | :--- | :--- |
| `author` / `sender` | `CordMember` | The user who triggered the command or sent the message. |
| `member` | `CordMember` | The joining or leaving member in member events. |
| `channel` | `CordChannel` | The channel in which the action took place. |
| `bot` | `DiscordAdapter` | The bot instance (`bot.latency`, `bot.bot_name`, etc.). |
| `store` | `Store` | Global persistent SQLite storage. |

---

## 2. Member & User Attributes

The `CordMember` object exposes:

- `member.id`: String ID of the user (e.g. `"123456789012345678"`).
- `member.name`: Username.
- `member.mention`: Formatted mention tag (e.g. `<@123456789012345678>`).
- `member.is_bot`: Boolean flag indicating if the user is a bot account.
- `member.avatar_url`: CDN link to the user's avatar.
- `member.has_permission(name)`: Method returning boolean check for a specific Discord permission.

---

## 3. Supported Permissions for `require permission`

Permissions match Discord's standard permission strings:

- `administrator`
- `manage_guild`
- `manage_roles`
- `manage_channels`
- `kick_members`
- `ban_members`
- `moderate_members` (Timeout permission)
- `manage_messages`
- `embed_links`
- `attach_files`
- `view_audit_log`

---

## 4. Rate Limiting & Gateway Intent Requirements

### Gateway Intents
Cord's `discord.py` backend enables `message_content` and `members` intents by default. Ensure both Privileged Gateway Intents are checked in your Discord Developer Application settings.

### Slash Command Syncing
Discord synchronizes application commands globally across the gateway. On initial startup, `cord run` registers slash commands and executes `tree.sync()`. Note that global commands may take a few minutes to propagate across all Discord clusters for large servers.
