"""
Runtime environment, scopes, built-in types, and Discord entity proxies for Cord.
"""

import asyncio
import json
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


import re

class CordMember:
    """Discord Member representation."""

    def __init__(
        self,
        member_id: Any,
        name: str,
        discriminator: str = "0",
        is_bot: bool = False,
        permissions: Optional[List[str]] = None,
        avatar_url: str = "",
        raw_user: Any = None,
        bot_adapter: Any = None
    ):
        self.id = str(member_id)
        self.name = name
        self.mention = f"<@{member_id}>"
        self.discriminator = discriminator
        self.is_bot = is_bot
        self.permissions = set(permissions or ["send_messages", "read_messages"])
        try:
            numeric_id = int(member_id)
        except (ValueError, TypeError):
            numeric_id = 0
        self.avatar_url = avatar_url or f"https://cdn.discordapp.com/embed/avatars/{numeric_id % 5}.png"
        self.raw_user = raw_user
        self.bot_adapter = bot_adapter
        self._adapter = bot_adapter

    @property
    def bot(self) -> bool:
        """Alias for is_bot, matching Discord.py user.bot boolean attribute."""
        return self.is_bot

    def has_permission(self, perm: str) -> bool:
        if "administrator" in self.permissions:
            return True
        norm_perm = re.sub(r"(?<!^)(?=[A-Z])", "_", perm).lower()
        return norm_perm in self.permissions or perm.lower() in self.permissions

    async def ban(self, reason: Optional[str] = None):
        if self.raw_user and hasattr(self.raw_user, "ban"):
            await self.raw_user.ban(reason=reason)
        elif self.bot_adapter and hasattr(self.bot_adapter, "record_action"):
            self.bot_adapter.record_action("ban", member=self, reason=reason)

    async def kick(self, reason: Optional[str] = None):
        if self.raw_user and hasattr(self.raw_user, "kick"):
            await self.raw_user.kick(reason=reason)
        elif self.bot_adapter and hasattr(self.bot_adapter, "record_action"):
            self.bot_adapter.record_action("kick", member=self, reason=reason)

    async def unban(self, reason: Optional[str] = None):
        if self.raw_user and hasattr(self.raw_user, "unban"):
            await self.raw_user.unban(reason=reason)
        elif self.bot_adapter and hasattr(self.bot_adapter, "record_action"):
            self.bot_adapter.record_action("unban", member=self, reason=reason)

    async def send(self, content: Optional[str] = None):
        if self.raw_user and hasattr(self.raw_user, "send"):
            await self.raw_user.send(content)
        elif self.bot_adapter and hasattr(self.bot_adapter, "record_action"):
            self.bot_adapter.record_action("send", member=self, content=content)

    async def timeout(self, duration: Any = None, reason: Optional[str] = None):
        if self.raw_user and hasattr(self.raw_user, "timeout"):
            import datetime
            td = None
            if isinstance(duration, (int, float)):
                td = datetime.timedelta(seconds=duration)
            elif isinstance(duration, datetime.timedelta):
                td = duration
            await self.raw_user.timeout(td, reason=reason)
        elif self.bot_adapter and hasattr(self.bot_adapter, "record_action"):
            self.bot_adapter.record_action("timeout", member=self, duration=duration, reason=reason)

    def __repr__(self) -> str:
        return f"<Member id={self.id} name={repr(self.name)}>"

    def __str__(self) -> str:
        return self.name


class CordRole:
    """Discord Role representation."""

    def __init__(self, role_id: int, name: str):
        self.id = str(role_id)
        self.name = name
        self.mention = f"<@&{role_id}>"

    def __repr__(self) -> str:
        return f"<Role @{self.name}>"

    def __str__(self) -> str:
        return self.name


class CordChannel:
    """Discord Channel representation."""

    def __init__(self, channel_id: int, name: str):
        self.id = str(channel_id)
        self.name = name
        self.mention = f"<#{channel_id}>"

    def __repr__(self) -> str:
        return f"<Channel #{self.name}>"

    def __str__(self) -> str:
        return self.name


class CordButton:
    """Discord Button component representation."""

    def __init__(
        self,
        custom_id: str,
        label: Optional[str] = None,
        style: str = "primary",
        emoji: Optional[str] = None,
        url: Optional[str] = None,
        disabled: bool = False
    ):
        self.id = custom_id
        self.custom_id = custom_id
        self.label = label
        self.style = style
        self.emoji = emoji
        self.url = url
        self.disabled = disabled

    def __repr__(self) -> str:
        return f"<Button id={repr(self.id)} label={repr(self.label)} style={repr(self.style)}>"


class CordSelectOption:
    """Discord Select Option representation."""

    def __init__(
        self,
        value: str,
        label: Optional[str] = None,
        description: Optional[str] = None,
        emoji: Optional[str] = None,
        default: bool = False
    ):
        self.value = value
        self.label = label or value
        self.description = description
        self.emoji = emoji
        self.default = default

    def __repr__(self) -> str:
        return f"<SelectOption value={repr(self.value)} label={repr(self.label)}>"


class CordSelect:
    """Discord Select Menu component representation."""

    def __init__(
        self,
        custom_id: str,
        placeholder: Optional[str] = None,
        min_values: int = 1,
        max_values: int = 1,
        disabled: bool = False,
        options: Optional[List[CordSelectOption]] = None
    ):
        self.id = custom_id
        self.custom_id = custom_id
        self.placeholder = placeholder
        self.min_values = min_values
        self.max_values = max_values
        self.disabled = disabled
        self.options: List[CordSelectOption] = options or []

    def __repr__(self) -> str:
        return f"<Select id={repr(self.id)} options={len(self.options)}>"


class CordView:
    """Discord View / Component Container."""

    def __init__(self, items: Optional[List[Any]] = None):
        self.items: List[Any] = items or []

    def add_item(self, item: Any):
        self.items.append(item)

    def __repr__(self) -> str:
        return f"<View items={self.items}>"


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

    async def reply(
        self,
        content: Optional[str] = None,
        embed: Optional[CordEmbed] = None,
        view: Optional[CordView] = None
    ):
        """Reply to the triggering command or event."""
        self.replies.append({"type": "reply", "content": content, "embed": embed, "view": view})
        if self.bot:
            await self.bot.send_reply(self, content=content, embed=embed, view=view)

    async def send(
        self,
        channel_ref: Any,
        content: Optional[str] = None,
        embed: Optional[CordEmbed] = None,
        view: Optional[CordView] = None
    ):
        """Send a message to a specific channel."""
        self.replies.append({"type": "send", "channel": channel_ref, "content": content, "embed": embed, "view": view})
        if self.bot:
            await self.bot.send_channel_message(channel_ref, content=content, embed=embed, view=view)

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


class CordHttpResponse:
    """HTTP response wrapper for native fetch / http operations."""

    def __init__(self, status: int, text: str, headers: Dict[str, str], url: str):
        self.status = status
        self.ok = 200 <= status < 300
        self.text = text
        self.headers = headers
        self.url = url
        self._parsed_json = None
        self._has_parsed = False

    @property
    def data(self) -> Any:
        if not self._has_parsed:
            try:
                self._parsed_json = json.loads(self.text)
            except Exception:
                self._parsed_json = None
            self._has_parsed = True
        return self._parsed_json

    def json(self) -> Any:
        return self.data

    def __getitem__(self, item: Any) -> Any:
        d = self.data
        if isinstance(d, (dict, list)):
            return d[item]
        raise KeyError(item)

    def __getattr__(self, name: str) -> Any:
        d = self.data
        if isinstance(d, dict) and name in d:
            return d[name]
        raise AttributeError(f"'CordHttpResponse' object has no attribute '{name}'")

    def __repr__(self) -> str:
        return f"<HttpResponse status={self.status} ok={self.ok}>"

    def __str__(self) -> str:
        return self.text


def _sync_http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[bytes] = None,
    timeout: float = 30.0
) -> CordHttpResponse:
    import urllib.request
    import urllib.error

    req_headers = {
        "User-Agent": "Cord-Lang/0.2.0 (Discord Bot Language)"
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, data=body, headers=req_headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            resp_headers = dict(resp.headers)
            resp_body = resp.read().decode("utf-8", errors="replace")
            return CordHttpResponse(status=status, text=resp_body, headers=resp_headers, url=url)
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
        resp_headers = dict(e.headers) if hasattr(e, "headers") else {}
        return CordHttpResponse(status=e.code, text=resp_body, headers=resp_headers, url=url)
    except Exception as e:
        return CordHttpResponse(status=0, text=str(e), headers={}, url=url)


async def cord_fetch(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    json_data: Any = None,
    timeout: float = 30.0,
    **kwargs
) -> CordHttpResponse:
    """Native non-blocking HTTP fetch function."""
    body_bytes = None
    hdrs = dict(headers) if headers else {}
    if json_data is not None:
        body_bytes = json.dumps(json_data).encode("utf-8")
        if "Content-Type" not in hdrs and "content-type" not in hdrs:
            hdrs["Content-Type"] = "application/json"
    elif "json" in kwargs:
        body_bytes = json.dumps(kwargs["json"]).encode("utf-8")
        if "Content-Type" not in hdrs and "content-type" not in hdrs:
            hdrs["Content-Type"] = "application/json"
    elif "data" in kwargs:
        raw_data = kwargs["data"]
        body_bytes = raw_data.encode("utf-8") if isinstance(raw_data, str) else bytes(raw_data)

    return await asyncio.to_thread(_sync_http_request, url, method=method, headers=hdrs, body=body_bytes, timeout=timeout)


class CordHttpModule:
    """Namespace for HTTP methods: http.get, http.post, etc."""

    async def get(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 30.0, **kwargs) -> CordHttpResponse:
        return await cord_fetch(url, method="GET", headers=headers, timeout=timeout, **kwargs)

    async def post(self, url: str, json: Any = None, data: Any = None, headers: Optional[Dict[str, str]] = None, timeout: float = 30.0, **kwargs) -> CordHttpResponse:
        return await cord_fetch(url, method="POST", headers=headers, json_data=json, timeout=timeout, data=data, **kwargs)

    async def put(self, url: str, json: Any = None, data: Any = None, headers: Optional[Dict[str, str]] = None, timeout: float = 30.0, **kwargs) -> CordHttpResponse:
        return await cord_fetch(url, method="PUT", headers=headers, json_data=json, timeout=timeout, data=data, **kwargs)

    async def delete(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 30.0, **kwargs) -> CordHttpResponse:
        return await cord_fetch(url, method="DELETE", headers=headers, timeout=timeout, **kwargs)

    async def patch(self, url: str, json: Any = None, data: Any = None, headers: Optional[Dict[str, str]] = None, timeout: float = 30.0, **kwargs) -> CordHttpResponse:
        return await cord_fetch(url, method="PATCH", headers=headers, json_data=json, timeout=timeout, data=data, **kwargs)

    def __repr__(self) -> str:
        return "<Module 'http'>"


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

    # HTTP & JSON Utilities
    env.define("fetch", cord_fetch)
    env.define("http", CordHttpModule())
    env.define("json_parse", lambda text: json.loads(text))
    env.define("json_stringify", lambda obj: json.dumps(obj))

    return env
