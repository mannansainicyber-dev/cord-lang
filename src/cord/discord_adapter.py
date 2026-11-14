"""
Discord Adapter for Cord.
Provides both a live discord.py integration and an offline MockDiscordAdapter
for rigorous, token-free unit and integration testing.
"""

import asyncio
import os
import re
from typing import Any, Dict, List, Optional, Callable, Union

try:
    import discord
    from discord import app_commands
    from discord.ext import commands as discord_commands
    HAS_DISCORD = True
except ImportError:
    HAS_DISCORD = False

from cord.ast_nodes import CommandDecl, EventDecl, TaskDecl
from cord.interpreter import Interpreter
from cord.runtime import (
    ExecutionContext, CordMember, CordChannel, CordEmbed, CordRuntimeError
)


class BaseDiscordAdapter:
    """Abstract base class for Cord Discord adapters."""

    def __init__(self, interpreter: Interpreter):
        self.interpreter = interpreter
        self.bot_name: str = "CordBot"
        self.prefix: str = "!"
        self.activity: Optional[str] = None
        self.status: str = "online"
        self.registered_commands: Dict[str, CommandDecl] = {}
        self.registered_events: Dict[str, List[EventDecl]] = {}
        self.registered_tasks: Dict[str, TaskDecl] = {}

    def apply_config(self, key: str, value: Any):
        if key == "prefix":
            self.prefix = str(value)
        elif key == "status":
            self.status = str(value)
        elif key == "activity":
            self.activity = str(value)

    def register_command(self, cmd: CommandDecl):
        self.registered_commands[cmd.name] = cmd

    def register_event(self, evt: EventDecl):
        if evt.event_name not in self.registered_events:
            self.registered_events[evt.event_name] = []
        self.registered_events[evt.event_name].append(evt)

    def register_task(self, task: TaskDecl):
        self.registered_tasks[task.name] = task

    def resolve_channel(self, name: str) -> Optional[Any]:
        return CordChannel(channel_id=1001, name=name)


class MockDiscordAdapter(BaseDiscordAdapter):
    """
    Offline mock adapter for testing without a Discord connection or token.
    Records sent messages, replies, and allows synthetic dispatch of commands/events.
    """

    def __init__(self, interpreter: Interpreter):
        super().__init__(interpreter)
        self.sent_messages: List[Dict[str, Any]] = []
        self.mock_members: Dict[str, CordMember] = {}
        self.mock_channels: Dict[str, CordChannel] = {}
        self.input_queue: asyncio.Queue = asyncio.Queue()

        # Default fallback test members & channels
        default_bot = CordMember(member_id=999, name="CordBot", is_bot=True)
        default_author = CordMember(member_id=100, name="TestUser", permissions=["moderate_members", "send_messages"])
        default_channel = CordChannel(channel_id=101, name="general")
        self.mock_members["100"] = default_author
        self.mock_members["testuser"] = default_author
        self.mock_channels["general"] = default_channel
        self.mock_channels["welcome"] = CordChannel(channel_id=102, name="welcome")

    async def send_reply(self, ctx: ExecutionContext, content: Optional[str] = None, embed: Optional[CordEmbed] = None):
        self.sent_messages.append({
            "action": "reply",
            "content": content,
            "embed": embed,
            "channel": ctx.channel.name if ctx.channel else None,
            "target_user": ctx.author.name if ctx.author else None
        })

    async def send_channel_message(self, channel_ref: Any, content: Optional[str] = None, embed: Optional[CordEmbed] = None):
        channel_name = channel_ref.name if hasattr(channel_ref, "name") else str(channel_ref)
        self.sent_messages.append({
            "action": "send",
            "channel": channel_name,
            "content": content,
            "embed": embed
        })

    async def delete_message(self, ctx: ExecutionContext):
        self.sent_messages.append({
            "action": "delete",
            "channel": ctx.channel.name if ctx.channel else None
        })

    async def wait_for_input(self, ctx: ExecutionContext, timeout: float = 60.0) -> Optional[str]:
        try:
            return await asyncio.wait_for(self.input_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    def push_input(self, text: str):
        """Feed input for interactive prompts in tests."""
        self.input_queue.put_nowait(text)

    def resolve_channel(self, name: str) -> Optional[CordChannel]:
        clean = name.lstrip("#")
        return self.mock_channels.get(clean, CordChannel(channel_id=9999, name=clean))

    async def dispatch_prefix_command(
        self,
        command_line: str,
        author: Optional[CordMember] = None,
        channel: Optional[CordChannel] = None
    ):
        """Simulates an incoming chat prefix command, e.g. '!warn @user spamming'."""
        if not command_line.startswith(self.prefix):
            return

        text = command_line[len(self.prefix):].strip()
        parts = text.split(maxsplit=1)
        if not parts:
            return
        cmd_name = parts[0]
        raw_args = parts[1] if len(parts) > 1 else ""

        if cmd_name not in self.registered_commands:
            return

        cmd = self.registered_commands[cmd_name]
        if cmd.mode == "slash":
            # Prefix execution not permitted for slash-only commands
            return

        author = author or self.mock_members["100"]
        channel = channel or self.mock_channels["general"]

        ctx = ExecutionContext(
            bot_adapter=self,
            author=author,
            channel=channel,
            guild_id="12345",
            is_interaction=False
        )
        setattr(ctx, "command_name", cmd_name)

        # Parse arguments according to signature
        parsed_args = self._parse_prefix_args(cmd, raw_args)
        await self.interpreter.execute_command(cmd, ctx, args=parsed_args)

    async def dispatch_slash_command(
        self,
        cmd_name: str,
        kwargs: Dict[str, Any],
        author: Optional[CordMember] = None,
        channel: Optional[CordChannel] = None
    ):
        """Simulates an incoming Discord Slash Command interaction."""
        if cmd_name not in self.registered_commands:
            return

        cmd = self.registered_commands[cmd_name]
        if cmd.mode == "prefix":
            # Slash execution not permitted for prefix-only commands
            return

        author = author or self.mock_members["100"]
        channel = channel or self.mock_channels["general"]

        ctx = ExecutionContext(
            bot_adapter=self,
            author=author,
            channel=channel,
            guild_id="12345",
            is_interaction=True
        )
        setattr(ctx, "command_name", cmd_name)

        await self.interpreter.execute_command(cmd, ctx, kwargs=kwargs)

    async def dispatch_event(self, event_name: str, **kwargs):
        """Simulates a Discord event (e.g., member_join, message)."""
        author = kwargs.get("member") or self.mock_members["100"]
        channel = kwargs.get("channel") or self.mock_channels["general"]
        ctx = ExecutionContext(bot_adapter=self, author=author, channel=channel)
        await self.interpreter.execute_event(event_name, ctx, event_args=kwargs)

    def _parse_prefix_args(self, cmd: CommandDecl, raw_args: str) -> List[Any]:
        """Convert whitespace-separated prefix args into typed parameter values."""
        if not cmd.params or not raw_args:
            return []

        tokens = raw_args.split()
        args: List[Any] = []

        for i, param in enumerate(cmd.params):
            if i >= len(tokens):
                break

            # If this is the last parameter, collect all remaining tokens as a single string
            if i == len(cmd.params) - 1:
                token_val = " ".join(tokens[i:])
            else:
                token_val = tokens[i]

            type_hint = (param.type_hint or "").lower()
            if type_hint in ("member", "user"):
                # Handle mentions: <@12345> or numeric ID
                match = re.search(r"\d+", token_val)
                user_id = match.group(0) if match else token_val
                member = self.mock_members.get(user_id) or CordMember(member_id=int(user_id) if user_id.isdigit() else 888, name=f"User_{user_id}")
                args.append(member)
            elif type_hint == "int":
                try: args.append(int(token_val))
                except ValueError: args.append(0)
            elif type_hint == "float":
                try: args.append(float(token_val))
                except ValueError: args.append(0.0)
            else:
                args.append(token_val)

        return args


class DiscordAdapter(BaseDiscordAdapter):
    """
    Production adapter using discord.py.
    Provides dual-command registration (prefix via message router, slash via CommandTree),
    event listeners, and background tasks.
    """

    def __init__(self, interpreter: Interpreter, token: Optional[str] = None):
        super().__init__(interpreter)
        if not HAS_DISCORD:
            raise RuntimeError("discord.py is not installed. Please install discord.py to run live bots.")

        self.token = token or os.getenv("DISCORD_TOKEN")
        self._validate_token()

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.client = discord_commands.Bot(
            command_prefix=self.prefix,
            intents=intents,
            help_command=None
        )
        self._setup_listeners()

    def _validate_token(self):
        if not self.token or self.token.strip() in ("", "YOUR_BOT_TOKEN_HERE", "your_discord_bot_token_here"):
            raise ValueError(
                "Missing or invalid Discord bot token! Please set the DISCORD_TOKEN environment "
                "variable or configure it in a .env file."
            )

    def _setup_listeners(self):
        @self.client.event
        async def on_ready():
            print(f"Logged in as {self.client.user} (ID: {self.client.user.id})")
            
            # Update presence
            if self.activity:
                await self.client.change_presence(
                    activity=discord.Game(name=self.activity),
                    status=discord.Status.online
                )

            # Sync slash commands
            await self._sync_slash_commands()

            # Trigger Cord ready events
            ctx = ExecutionContext(bot_adapter=self, author=None, channel=None)
            await self.interpreter.execute_event("ready", ctx)

        @self.client.event
        async def on_message(message: discord.Message):
            # Ignore messages from self or other bots
            if message.author.bot:
                return

            # Check for prefix command
            if message.content.startswith(self.prefix):
                await self._handle_prefix_message(message)

            # Trigger on_message event in Cord
            author_proxy = self._to_cord_member(message.author)
            channel_proxy = self._to_cord_channel(message.channel)
            ctx = ExecutionContext(
                bot_adapter=self,
                author=author_proxy,
                channel=channel_proxy,
                guild_id=str(message.guild.id) if message.guild else None,
                raw_event=message
            )
            await self.interpreter.execute_event("message", ctx, {"message": message.content})

        @self.client.event
        async def on_member_join(member: discord.Member):
            member_proxy = self._to_cord_member(member)
            channel_proxy = self._to_cord_channel(member.guild.system_channel or member.guild.text_channels[0])
            ctx = ExecutionContext(bot_adapter=self, author=member_proxy, channel=channel_proxy)
            await self.interpreter.execute_event("member_join", ctx, {"member": member_proxy})

        @self.client.event
        async def on_member_remove(member: discord.Member):
            member_proxy = self._to_cord_member(member)
            channel_proxy = self._to_cord_channel(member.guild.system_channel or member.guild.text_channels[0])
            ctx = ExecutionContext(bot_adapter=self, author=member_proxy, channel=channel_proxy)
            await self.interpreter.execute_event("member_leave", ctx, {"member": member_proxy})

    async def _sync_slash_commands(self):
        """Registers all declared slash commands onto discord.py's CommandTree and syncs with Discord."""
        tree = self.client.tree

        for cmd_name, cmd in self.registered_commands.items():
            if cmd.mode == "prefix":
                continue

            # Build slash command callback dynamically
            desc = cmd.description or f"Cord command: {cmd_name}"

            def make_slash_callback(command_decl: CommandDecl):
                async def slash_callback(interaction: discord.Interaction, **kwargs):
                    await interaction.response.defer()
                    author_proxy = self._to_cord_member(interaction.user)
                    channel_proxy = self._to_cord_channel(interaction.channel)
                    ctx = ExecutionContext(
                        bot_adapter=self,
                        author=author_proxy,
                        channel=channel_proxy,
                        guild_id=str(interaction.guild_id) if interaction.guild_id else None,
                        is_interaction=True,
                        raw_event=interaction
                    )
                    setattr(ctx, "command_name", command_decl.name)
                    await self.interpreter.execute_command(command_decl, ctx, kwargs=kwargs)

                return slash_callback

            app_cmd = app_commands.Command(
                name=cmd_name,
                description=desc,
                callback=make_slash_callback(cmd)
            )
            tree.add_command(app_cmd)

        try:
            await tree.sync()
            print("Successfully synchronized slash commands with Discord.")
        except Exception as e:
            print(f"Warning: Failed to sync slash commands with Discord: {e}")

    async def _handle_prefix_message(self, message: discord.Message):
        content = message.content[len(self.prefix):].strip()
        parts = content.split(maxsplit=1)
        if not parts:
            return
        cmd_name = parts[0]
        raw_args = parts[1] if len(parts) > 1 else ""

        if cmd_name not in self.registered_commands:
            return

        cmd = self.registered_commands[cmd_name]
        if cmd.mode == "slash":
            return

        author_proxy = self._to_cord_member(message.author)
        channel_proxy = self._to_cord_channel(message.channel)
        ctx = ExecutionContext(
            bot_adapter=self,
            author=author_proxy,
            channel=channel_proxy,
            guild_id=str(message.guild.id) if message.guild else None,
            is_interaction=False,
            raw_event=message
        )
        setattr(ctx, "command_name", cmd_name)

        parsed_args = self._parse_prefix_args(cmd, raw_args, message.guild)
        await self.interpreter.execute_command(cmd, ctx, args=parsed_args)

    def _parse_prefix_args(self, cmd: CommandDecl, raw_args: str, guild: Optional[discord.Guild]) -> List[Any]:
        if not cmd.params or not raw_args:
            return []
        tokens = raw_args.split()
        args: List[Any] = []

        for i, param in enumerate(cmd.params):
            if i >= len(tokens):
                break
            token_val = " ".join(tokens[i:]) if i == len(cmd.params) - 1 else tokens[i]
            type_hint = (param.type_hint or "").lower()

            if type_hint in ("member", "user"):
                match = re.search(r"\d+", token_val)
                user_id = int(match.group(0)) if match else 0
                discord_member = guild.get_member(user_id) if guild else None
                if discord_member:
                    args.append(self._to_cord_member(discord_member))
                else:
                    args.append(CordMember(member_id=user_id, name=f"User_{user_id}"))
            elif type_hint == "int":
                try: args.append(int(token_val))
                except ValueError: args.append(0)
            elif type_hint == "float":
                try: args.append(float(token_val))
                except ValueError: args.append(0.0)
            else:
                args.append(token_val)

        return args

    def _to_cord_member(self, user: Union[discord.Member, discord.User]) -> CordMember:
        perms = []
        if isinstance(user, discord.Member):
            perms = [perm for perm, val in user.guild_permissions if val]
        return CordMember(
            member_id=user.id,
            name=user.name,
            discriminator=user.discriminator,
            is_bot=user.bot,
            permissions=perms,
            avatar_url=str(user.display_avatar.url)
        )

    def _to_cord_channel(self, channel: Any) -> CordChannel:
        return CordChannel(channel_id=channel.id, name=getattr(channel, "name", "channel"))

    def _to_discord_embed(self, cord_embed: CordEmbed) -> discord.Embed:
        color_val = None
        if cord_embed.color:
            if isinstance(cord_embed.color, str) and cord_embed.color.startswith("#"):
                color_val = int(cord_embed.color.lstrip("#"), 16)
            elif isinstance(cord_embed.color, int):
                color_val = cord_embed.color

        embed = discord.Embed(
            title=cord_embed.title,
            description=cord_embed.description,
            color=color_val
        )
        if cord_embed.thumbnail:
            embed.set_thumbnail(url=cord_embed.thumbnail)
        if cord_embed.image:
            embed.set_image(url=cord_embed.image)
        if cord_embed.footer:
            embed.set_footer(text=cord_embed.footer)
        for f in cord_embed.fields:
            embed.add_field(name=f["name"], value=f["value"], inline=f.get("inline", False))
        return embed

    async def send_reply(self, ctx: ExecutionContext, content: Optional[str] = None, embed: Optional[CordEmbed] = None):
        discord_embed = self._to_discord_embed(embed) if embed else None
        if ctx.is_interaction and isinstance(ctx.raw_event, discord.Interaction):
            await ctx.raw_event.followup.send(content=content, embed=discord_embed)
        elif isinstance(ctx.raw_event, discord.Message):
            await ctx.raw_event.reply(content=content, embed=discord_embed)
        elif ctx.channel:
            # Fallback to channel send
            ch = self.client.get_channel(int(ctx.channel.id))
            if ch:
                await ch.send(content=content, embed=discord_embed)

    async def send_channel_message(self, channel_ref: Any, content: Optional[str] = None, embed: Optional[CordEmbed] = None):
        discord_embed = self._to_discord_embed(embed) if embed else None
        channel_name = channel_ref.name if hasattr(channel_ref, "name") else str(channel_ref).lstrip("#")
        for guild in self.client.guilds:
            for ch in guild.text_channels:
                if ch.name == channel_name:
                    await ch.send(content=content, embed=discord_embed)
                    return

    async def delete_message(self, ctx: ExecutionContext):
        if isinstance(ctx.raw_event, discord.Message):
            await ctx.raw_event.delete()

    async def wait_for_input(self, ctx: ExecutionContext, timeout: float = 60.0) -> Optional[str]:
        def check(m: discord.Message):
            return m.author.id == int(ctx.author.id) and m.channel.id == int(ctx.channel.id)

        try:
            msg = await self.client.wait_for("message", check=check, timeout=timeout)
            return msg.content
        except asyncio.TimeoutError:
            return None

    def start(self):
        """Starts the discord client."""
        self.client.run(self.token)
