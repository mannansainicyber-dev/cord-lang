# Cord UI Components & Interactive Views

Cord treats Discord UI components (Buttons, Select Menus, and Action Rows) as first-class language constructs. You do not need to subclass `discord.ui.View`, write custom interaction callbacks, manage custom IDs, or track interaction tokens manually.

---

## 1. Overview

In general-purpose libraries like `discord.py`, creating interactive buttons requires declaring a class inheriting from `discord.ui.View`, defining methods with decorator `@discord.ui.button`, instantiating the view, and passing it to `ctx.send()`.

In Cord, components are declared inside a `with:` block appended to any `reply` or `send` statement:

```cord
command menu:
    reply "Server Member Portal" with:
        button "verify_btn":
            label "Verify Account"
            style "success"
            emoji "✅"
        button "docs_btn":
            label "Documentation"
            style "link"
            url "https://cord-lang.org"
```

Responses to user interactions are written as declarative top-level event handlers:

```cord
when button "verify_btn" is clicked:
    author.add_role("Verified")
    reply "✅ You have been verified, {author.name}!"
```

---

## 2. Button Components

Buttons are declared using the `button "<id>":` syntax inside a `with:` block.

### Button Properties

| Property | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `label` | `String` | The visible text displayed on the button. | `""` |
| `style` | `String` | The button appearance. Options: `"primary"`, `"secondary"`, `"success"`, `"danger"`, `"link"`. | `"primary"` |
| `emoji` | `String` | Unicode emoji or custom Discord emoji displayed before the label. | `null` |
| `disabled`| `Boolean`| Whether the button is disabled / greyed out. | `false` |
| `url` | `String` | Target URL (required and only valid when `style` is `"link"`). | `null` |

### Button Styles

- **`"primary"` / `"blurple"`**: Discord Blurple button (`#5865F2`). Used for standard affirmative actions.
- **`"secondary"` / `"grey"`**: Muted dark grey button. Used for neutral actions or secondary choices.
- **`"success"` / `"green"`**: Emerald green button (`#248046`). Used for confirmations, verifications, or submit actions.
- **`"danger"` / `"red"`**: Red button (`#DA373C`). Used for destructive actions (bans, resets, deletion).
- **`"link"`**: URL button. Clicking opens an external link in the user's browser. Link buttons do not emit a click event.

### Example: Multi-Button Action Row

```cord
command prompt_action:
    reply "Select an action for {target.name}:" with:
        button "approve":
            label "Approve Application"
            style "success"
            emoji "✅"
        button "reject":
            label "Reject"
            style "danger"
            emoji "❌"
        button "review_later":
            label "Postpone"
            style "secondary"
            emoji "⏳"

when button "approve" is clicked:
    send #audit-logs "Approved {target.name} by {author.name}"
    reply "Application approved!"

when button "reject" is clicked:
    reply "Application rejected."
```

---

## 3. Select Menus (Dropdowns)

Select menus let users choose one or more options from a dropdown list. They are declared using `select "<id>":` inside a `with:` block.

### Select Menu Properties

| Property | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `placeholder` | `String` | Placeholder text shown when no options are selected. | `"Choose an option..."` |
| `min_values` | `Integer` | Minimum number of items the user must select. | `1` |
| `max_values` | `Integer` | Maximum number of items the user can select. | `1` |
| `disabled` | `Boolean` | Whether the select menu is disabled. | `false` |

### Select Options

Options are declared inside the `select` body using `option "<value>":`:

| Property | Type | Description | Default |
| :--- | :--- | :--- | :--- |
| `label` | `String` | The primary text shown for this dropdown option. | The option value |
| `description` | `String` | Subtitle text explaining the option. | `null` |
| `emoji` | `String` | Unicode or custom Discord emoji displayed beside the option. | `null` |
| `default` | `Boolean` | Whether this option is selected by default. | `false` |

### Example: Role Selection Dropdown

```cord
command roles:
    reply "Pick your specialization to receive notification pings:" with:
        select "specialization_select":
            placeholder "Choose your primary discipline..."
            min_values 1
            max_values 1
            option "backend":
                label "Backend Engineer"
                description "Python, Rust, databases, and microservices"
                emoji "⚙️"
            option "frontend":
                label "Frontend Engineer"
                description "TypeScript, React, UI design systems"
                emoji "🎨"
            option "devops":
                label "Infrastructure & DevOps"
                description "Docker, Kubernetes, CI/CD pipelines"
                emoji "🚀"

when select "specialization_select" is chosen:
    author.set_role(selected)
    reply "Updated your notification role to **{selected}**!"
```

In the `when select ... is chosen:` handler:
- `selected` contains the value of the chosen option (or list of values if `max_values > 1`).
- `author` refers to the member who interacted with the dropdown.
- `channel` refers to the channel where the interaction took place.

---

## 4. Combining Rich Embeds with UI Components

You can combine rich embeds and interactive components in a single `reply` or `send` statement:

```cord
command portal:
    reply embed:
        title "Community Help Center"
        description "Click a button below to open a ticket or read our FAQ."
        color "#5865F2"
        field "Online Staff" "4 moderators on duty" inline=true
        field "Response Time" "< 5 minutes" inline=true
    with:
        button "ticket_create":
            label "Open Private Ticket"
            style "primary"
            emoji "🎫"
        button "faq_link":
            label "Community FAQ"
            style "link"
            url "https://cord-lang.org/faq"
```

---

## 5. Event Scoping & Context

When a component event fires, Cord provides complete contextual information:

- `author`: The member who clicked or selected.
- `channel`: The channel where the interaction occurred.
- `guild`: The guild / server of the interaction.
- `message`: The parent message containing the component.
- `custom_id`: The ID string assigned to the component.

### Disabling Components After Click

To prevent duplicate submissions, Cord automatically handles component interaction acknowledgment and supports disabling actions when desired:

```cord
when button "lock_channel" is clicked:
    require permission manage_channels
    channel.set_locked(true)
    reply "🔒 Channel locked by {author.mention}."
```
