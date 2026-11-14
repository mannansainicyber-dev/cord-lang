"""
Runtime environment, scopes, built-in types, and Discord entity proxies for Cord.
"""

from typing import Any, Dict, List, Optional, Callable


class CordRuntimeError(Exception):
    def __init__(self, message: str, line: int = 1, col: int = 1):
        super().__init__(f"Runtime Error at line {line}, col {col}: {message}")
        self.message = message
        self.line = line
        self.col = col


class ReturnSignal(Exception):
    """Internal signal used to unwind the call stack on 'return' statements."""
    def __init__(self, value: Any):
        self.value = value


class Environment:
    """
    Lexical scope environment supporting nested blocks and closures.
    """

    def __init__(self, parent: Optional["Environment"] = None):
        self.parent = parent
        self.values: Dict[str, Any] = {}

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent:
            return self.parent.get(name)
        raise NameError(f"Undefined variable '{name}'")

    def has(self, name: str) -> bool:
        if name in self.values:
            return True
        if self.parent:
            return self.parent.has(name)
        return False

    def define(self, name: str, value: Any):
        """Define a new variable in current scope."""
        self.values[name] = value

    def assign(self, name: str, value: Any):
        """Assign to an existing variable in the scope chain, or current if not found."""
        if name in self.values:
            self.values[name] = value
            return
        if self.parent and self.parent.has(name):
            self.parent.assign(name, value)
            return
        self.values[name] = value


class CordFunction:
    """User-defined function with lexical closure."""

    def __init__(self, name: str, params: List[Any], body: Any, closure: Environment):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure

    def __repr__(self) -> str:
        return f"<function {self.name}>"


class CordEmbed:
    """Discord Embed data container."""

    def __init__(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[Any] = None,
        thumbnail: Optional[str] = None,
        image: Optional[str] = None,
        footer: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None
    ):
        self.title = title
        self.description = description
        self.color = color
        self.thumbnail = thumbnail
        self.image = image
        self.footer = footer
        self.fields = fields or []

    def add_field(self, name: str, value: str, inline: bool = False):
        self.fields.append({"name": name, "value": value, "inline": inline})

    def to_dict(self) -> Dict[str, Any]:
        d = {}
        if self.title: d["title"] = self.title
        if self.description: d["description"] = self.description
        if self.color: d["color"] = self.color
        if self.thumbnail: d["thumbnail"] = {"url": self.thumbnail}
        if self.image: d["image"] = {"url": self.image}
        if self.footer: d["footer"] = {"text": self.footer}
        if self.fields: d["fields"] = self.fields
        return d

    def __repr__(self) -> str:
        return f"CordEmbed(title={repr(self.title)}, description={repr(self.description)})"


class CordMember:
    """Discord Member representation."""

    def __init__(
        self,
        member_id: int,
        name: str,
        discriminator: str = "0",
        is_bot: bool = False,
        permissions: Optional[List[str]] = None,
        avatar_url: str = ""
    ):
        self.id = str(member_id)
        self.name = name
        self.mention = f"<@{member_id}>"
        self.discriminator = discriminator
        self.is_bot = is_bot
        self.permissions = set(permissions or ["send_messages", "read_messages"])
        self.avatar_url = avatar_url or f"https://cdn.discordapp.com/embed/avatars/{int(member_id) % 5}.png"

    def has_permission(self, perm: str) -> bool:
        if "administrator" in self.permissions:
            return True
        return perm.lower() in self.permissions

    def __repr__(self) -> str:
        return f"<Member id={self.id} name={repr(self.name)}>"


class CordChannel:
    """Discord Channel representation."""

    def __init__(self, channel_id: int, name: str):
        self.id = str(channel_id)
        self.name = name
        self.mention = f"<#{channel_id}>"

    def __repr__(self) -> str:
        return f"<Channel #{self.name}>"


class ExecutionContext:
    """
    Context passed to commands and events during execution.
    Provides reply, send, delete, and access to author, channel, and guild.
    """

    def __init__(
        self,
        bot_adapter: Any,
        author: Optional[CordMember] = None,
        channel: Optional[CordChannel] = None,
        guild_id: Optional[str] = None,
        is_interaction: bool = False,
        raw_event: Any = None
    ):
        self.bot = bot_adapter
        self.author = author
        self.sender = author  # Alias for beginner readability
        self.member = author  # Alias for member_join events
        self.channel = channel
        self.guild_id = guild_id
        self.is_interaction = is_interaction
        self.raw_event = raw_event
        self.replies: List[Dict[str, Any]] = []

    async def reply(self, content: Optional[str] = None, embed: Optional[CordEmbed] = None):
        """Reply to the triggering command or event."""
        self.replies.append({"type": "reply", "content": content, "embed": embed})
        if self.bot:
            await self.bot.send_reply(self, content=content, embed=embed)

    async def send(self, channel_ref: Any, content: Optional[str] = None, embed: Optional[CordEmbed] = None):
        """Send a message to a specific channel."""
        self.replies.append({"type": "send", "channel": channel_ref, "content": content, "embed": embed})
        if self.bot:
            await self.bot.send_channel_message(channel_ref, content=content, embed=embed)

    async def delete_trigger(self):
        """Delete the triggering message."""
        if self.bot:
            await self.bot.delete_message(self)

    async def ask(self, prompt: Optional[str] = None, timeout: float = 60.0) -> Optional[str]:
        """Interactive input: prompt the user and await their response."""
        if prompt:
            await self.reply(content=prompt)
        if self.bot:
            return await self.bot.wait_for_input(self, timeout=timeout)
        return None


def get_standard_environment() -> Environment:
    """Creates the root global scope with standard built-in functions."""
    env = Environment()

    env.define("print", lambda *args: print(*args))
    env.define("len", lambda obj: len(obj))
    env.define("str", lambda val: str(val) if val is not None else "")
    env.define("int", lambda val: int(val) if val is not None else 0)
    env.define("float", lambda val: float(val) if val is not None else 0.0)
    env.define("bool", lambda val: bool(val))
    env.define("type", lambda val: type(val).__name__)
    env.define("range", lambda *args: list(range(*args)))

    return env
