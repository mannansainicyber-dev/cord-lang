# Getting Started with Cord

This tutorial walks you through creating, testing, and running your very first Discord bot written in **Cord**.

---

## 1. Creating a New Project

Cord includes a project scaffolding tool. Run:

```bash
cord init my-first-bot
cd my-first-bot
```

This creates a clean workspace:
```text
my-first-bot/
├── bot.cord       # Your bot's source code
├── .env.example   # Configuration template
├── .gitignore     # Recommended git ignore rules
└── README.md      # Project overview
```

---

## 2. Setting Up Your Discord Bot

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application**, give it a name, and navigate to the **Bot** tab.
3. Click **Reset Token** to copy your bot token.
4. Under **Privileged Gateway Intents**, enable:
   - **Message Content Intent** (required for prefix commands)
   - **Server Members Intent** (required for welcome events)
5. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
6. Open `.env` and paste your bot token:
   ```env
   DISCORD_TOKEN=your_copied_token_here
   ```

---

## 3. Writing Your First Bot (`bot.cord`)

Open `bot.cord` in your favorite editor:

```cord
bot "Greeter"

config:
    prefix = "!"
    status = "online"
    activity = "with Cord"

# When a user joins your server
when someone joins:
    send #welcome "Welcome to our community, {member.name}!"

# A command that works as both !ping and /ping
command ping:
    reply "Pong! Latency is {bot.latency}ms"

# A command with a typed argument
command greet(target: Member = null):
    user = target or author
    reply "Hello, {user.mention}!"
```

---

## 4. Validating Your Code

Before starting the bot, you can validate your syntax offline:

```bash
cord check bot.cord
```

If any colons, indentations, or expressions are malformed, Cord pinpoints the exact line and column with a helpful fix suggestion.

---

## 5. Running Your Bot

Start your bot with:

```bash
cord run bot.cord
```

Once running:
- Type `!ping` in your Discord server.
- Or type `/ping` to use the slash command.
- Your bot will respond instantly!
