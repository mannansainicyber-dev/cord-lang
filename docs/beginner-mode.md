# Beginner Mode Guide

Cord was created so anyone can build a Discord bot without getting overwhelmed by asynchronous callbacks, complex decorators, or confusing boilerplate.

## 1. Natural Language Triggers

Instead of remembering API event names, you can use readable English phrases:

```cord
when someone joins:
    send #welcome "Welcome {member.name} to the server!"

when someone leaves:
    send #logs "{member.name} just left."

when a message is sent:
    # message is available automatically
    if message == "hello bot":
        reply "Hello there!"
```

### Supported Beginner Triggers:
- `when someone joins:` — Triggers when a new member joins the server.
- `when someone leaves:` — Triggers when a member leaves or is removed.
- `when a message is sent:` — Triggers on any new message.
- `when a reaction is added:` — Triggers when an emoji reaction is added.
- `when bot starts:` — Triggers once when the bot establishes connection.

---

## 2. Straightforward Commands

Declaring a command only takes two lines:

```cord
command ping:
    reply "Pong!"
```

By default, any `command` you write automatically works as **both a slash command (`/ping`) and a text command (`!ping`)**!

---

## 3. String Formatting & Mentions

Use curly braces `{...}` inside double quotes to insert names, mentions, and variables:

```cord
command whoami:
    reply "Your name is {author.name} and your ID is {author.id}."
```

To mention someone, use `{author.mention}`:
```cord
reply "Hey {author.mention}, thanks for reaching out!"
```

---

## 4. Asking Questions (`ask for`)

Build interactive bots that prompt the user and wait for their answer:

```cord
command quiz:
    reply "Let's play a game!"
    ask for color "What is your favorite color?" timeout=20s

    if color == null:
        reply "You didn't answer in time!"
    else:
        reply "Oh, {color} is a wonderful color!"
```

---

## 5. Helpful Errors

If you forget a colon or mistype a keyword, Cord's error reporter explains what happened:

```text
Error: Expected ':' after command declaration.
  --> Line 4, Column 13
   |
 4 | command ping
   |             ^
💡 Hint: In Cord, all command headers must end with a colon (:).
```
