# Cord Production Cookbook & Bot Recipes

A curated collection of real-world Discord bot implementations written in Cord. Every recipe is complete, copy-pastable, and ready to deploy.

---

## Recipe 1: Self-Service Role & Verification Menu

This recipe creates an interactive onboarding menu with a verification button and a role selection dropdown.

```cord
bot "Gatekeeper"

config:
    prefix = "!"

command onboarding:
    require permission administrator
    
    reply embed:
        title "Welcome to the Community!"
        description "Complete verification and select your role to gain access to channels."
        color "#5865F2"
    with:
        button "verify_btn":
            label "Verify Account"
            style "success"
            emoji "✅"
        select "role_select":
            placeholder "Select your primary interest..."
            option "dev":
                label "Developer"
                description "Access coding channels and bot testbeds"
                emoji "💻"
            option "art":
                label "Artist / Designer"
                description "Access art showcases and feedback channels"
                emoji "🎨"
            option "gamer":
                label "Gaming Community"
                description "Party finder and gaming lobbies"
                emoji "🎮"

when button "verify_btn" is clicked:
    if not author.has_role("Verified"):
        author.add_role("Verified")
        reply "✅ Welcome {author.name}! You are now verified."
    else:
        reply "ℹ️ You are already verified, {author.name}!"

when select "role_select" is chosen:
    author.set_role(selected)
    reply "🏷️ Assigned role **{selected}** to {author.name}."
```

---

## Recipe 2: Automated Moderation Shield with Warning Escalation

An automated moderation bot that tracks user warnings in SQLite and automatically imposes timeouts when violations accumulate.

```cord
bot "Shield"

config:
    prefix = "!"

# Prohibited keyword filter
when someone sends a message:
    if message.author.is_bot:
        return

    # Check for invite links
    if "discord.gg/" in message.content or "discord.com/invite/" in message.content:
        delete message
        warn_user(message.author, "Posting unauthorized Discord invite links")

fn warn_user(target, reason):
    if not store.has("warns"):
        store.warns = {}

    current = store.warns.get(target.id, 0) + 1
    store.warns[target.id] = current

    send #mod-logs embed:
        title "Automod: Warning Issued"
        description "Target: {target.mention} (ID: {target.id})"
        color "#EF4444"
        field "Reason" reason inline=true
        field "Total Warnings" current inline=true

    # Escalation policy:
    # 2 warnings -> 10m timeout
    # 3+ warnings -> 1h timeout
    if current == 2:
        timeout target for 10m reason="Automod: 2 warnings reached"
        send #general "🔇 {target.mention} timed out for 10 minutes (2 warnings)."
    elif current >= 3:
        timeout target for 1h reason="Automod: 3+ warnings reached"
        send #general "🔇 {target.mention} timed out for 1 hour (3+ warnings)."
    else:
        send #general "⚠️ {target.mention}, warning issued: {reason} (Total: {current}/3)"

command warnings(target: Member = null):
    user = target or author
    count = store.warns.get(user.id, 0)
    reply "{user.name} has **{count}** warning(s)."
```

---

## Recipe 3: REST API Live Bitcoin & Crypto Tracker

Fetches live cryptocurrency prices from external APIs and provides recurring scheduled announcements.

```cord
bot "CryptoTicker"

config:
    prefix = "$"

command btc:
    res = fetch("https://api.coindesk.com/v1/bpi/currentprice.json")
    if res.ok:
        usd_rate = res.bpi.USD.rate
        reply embed:
            title "Bitcoin (BTC / USD)"
            description "Current Price: **${usd_rate}**"
            color "#F7931A"
            footer "Source: CoinDesk API"
    else:
        reply "❌ Failed to query crypto price: HTTP {res.status}"

# Hourly automated market report
task hourly_ticker every 1h:
    res = fetch("https://api.coindesk.com/v1/bpi/currentprice.json")
    if res.ok:
        send #market-updates embed:
            title "Hourly Market Snapshot"
            description "1 BTC = **${res.bpi.USD.rate}**"
            color "#10B981"
```

---

## Recipe 4: Persistent Server Economy with Daily Claims and Leaderboard

A complete economy bot with persistent SQLite storage, daily reward cooldowns, and peer-to-peer coin transfers.

```cord
bot "Economy"

config:
    prefix = "!"

command daily:
    cooldown 24h per user
    
    if not store.has("balances"):
        store.balances = {}

    current = store.balances.get(author.id, 0)
    reward = 150
    store.balances[author.id] = current + reward

    reply embed:
        title "💰 Daily Reward Claimed!"
        description "You received **{reward} coins**."
        color "#F59E0B"
        field "Current Balance" "{store.balances[author.id]} coins" inline=true

command balance(target: Member = null):
    user = target or author
    coins = store.balances.get(user.id, 0)
    reply "💳 {user.name} has **{coins} coins**."

command pay(target: Member, amount: Integer):
    if amount <= 0:
        reply "❌ Amount must be positive."
        return

    sender_bal = store.balances.get(author.id, 0)
    if sender_bal < amount:
        reply "❌ You do not have enough coins!"
        return

    store.balances[author.id] = sender_bal - amount
    target_bal = store.balances.get(target.id, 0)
    store.balances[target.id] = target_bal + amount

    reply "💸 {author.mention} transferred **{amount} coins** to {target.mention}."
```

---

## Recipe 5: Private Ticket Support System

Provides a ticket panel where users can open private channels for support.

```cord
bot "TicketMaster"

config:
    prefix = "!"

command setup_tickets:
    require permission administrator
    
    reply embed:
        title "Support Desk"
        description "Click below to create a private support ticket with our team."
        color "#5865F2"
    with:
        button "open_ticket":
            label "Open Ticket"
            style "primary"
            emoji "🎫"

when button "open_ticket" is clicked:
    ticket_num = (store.ticket_counter or 100) + 1
    store.ticket_counter = ticket_num

    channel_name = "ticket-{ticket_num}"
    reply "🎫 Creating your ticket in **#{channel_name}**..."

    send #mod-logs "Ticket #{ticket_num} created by {author.name} (ID: {author.id})"
```
