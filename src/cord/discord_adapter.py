"""
Discord Adapter for Cord.
Provides both a live discord.py integration and an offline MockDiscordAdapter
for rigorous, token-free unit and integration testing.
"""

import asyncio
import inspect
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

from cord.ast_nodes import CommandDecl, EventDecl, TaskDecl, Literal, DurationLiteral, ASTNode
from cord.interpreter import Interpreter
from cord.runtime import (
    ExecutionContext, CordMember, CordChannel, CordRole, CordEmbed, CordRuntimeError
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

    @property
    def latency(self) -> int:
        return 0

    @property
    def user(self) -> CordMember:
        return CordMember(member_id=999, name=self.bot_name, is_bot=True, bot_adapter=self)

    @property
    def id(self) -> str:
        return self.user.id

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

    @property
    def latency(self) -> int:
        return 15

    @property
    def user(self) -> CordMember:
        return self.mock_members.get("999") or CordMember(member_id=999, name=self.bot_name, is_bot=True, bot_adapter=self)

    @property
    def id(self) -> str:
        return self.user.id

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
                match = re.search(r"\d+", token_val)
                user_id = match.group(0) if match else token_val
                member = self.mock_members.get(user_id) or CordMember(member_id=int(user_id) if user_id.isdigit() else 888, name=f"User_{user_id}")
                args.append(member)
            elif type_hint in ("int", "integer"):
                try: args.append(int(token_val))
                except ValueError: args.append(0)
            elif type_hint in ("float", "number"):
                try: args.append(float(token_val))
                except ValueError: args.append(0.0)
            elif type_hint in ("bool", "boolean"):
                args.append(token_val.lower() in ("true", "yes", "1"))
            elif type_hint in ("role",):
                match = re.search(r"\d+", token_val)
                role_id = match.group(0) if match else "1"
                args.append(CordRole(role_id=int(role_id) if role_id.isdigit() else 1, name=token_val))
            elif type_hint in ("channel", "textchannel"):
                match = re.search(r"\d+", token_val)
                ch_id = match.group(0) if match else "1"
                args.append(CordChannel(channel_id=int(ch_id) if ch_id.isdigit() else 1, name=token_val.lstrip("#")))
            else:
                args.append(token_val)

        return args

    def record_action(self, action: str, **kwargs):
        self.sent_messages.append({
            "action": action,
            **kwargs
        })

    async def run_task(self, task_name: str):
        if task_name in self.registered_tasks:
            task = self.registered_tasks[task_name]
            ctx = ExecutionContext(bot_adapter=self, author=None, channel=None)
            await self.interpreter.execute_block(task.body, self.interpreter.global_env, ctx)


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

        self.token = token if token is not None else os.getenv("DISCORD_TOKEN")
        self._validate_token()

        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.client = discord_commands.Bot(
            command_prefix=self.prefix,
            intents=intents,
            help_command=None
        )
        self._active_tasks: Dict[str, asyncio.Task] = {}
        self._synced: bool = False
        self._setup_listeners()

    def apply_config(self, key: str, value: Any):
        super().apply_config(key, value)
        if key == "prefix" and hasattr(self, "client") and self.client:
            self.client.command_prefix = self.prefix

    @property
    def latency(self) -> int:
        """Returns bot websocket latency in milliseconds."""
        if hasattr(self, "client") and self.client and hasattr(self.client, "latency"):
            return int(round(self.client.latency * 1000))
        return 0

    @property
    def user(self) -> CordMember:
        """Returns bot user as a CordMember."""
        if hasattr(self, "client") and self.client and self.client.user:
            return self._to_cord_member(self.client.user)
        return CordMember(member_id=0, name=self.bot_name, is_bot=True, bot_adapter=self)

    @property
    def id(self) -> str:
        return self.user.id

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
            status_map = {
                "online": discord.Status.online,
                "idle": discord.Status.idle,
                "dnd": discord.Status.dnd,
                "do_not_disturb": discord.Status.dnd,
                "invisible": discord.Status.invisible,
                "offline": discord.Status.offline,
            }
            disc_status = status_map.get(str(self.status).lower(), discord.Status.online)
            await self.client.change_presence(
                activity=discord.Game(name=self.activity) if self.activity else None,
                status=disc_status
            )

            # Sync slash commands (only once per bot lifecycle)
            if not self._synced:
                await self._sync_slash_commands()
                self._synced = True

            # Start registered background tasks
            for task in self.registered_tasks.values():
                self._start_task(task)

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
            sys_ch = member.guild.system_channel
            if not sys_ch and member.guild.text_channels:
                sys_ch = member.guild.text_channels[0]
            channel_proxy = self._to_cord_channel(sys_ch) if sys_ch else None
            ctx = ExecutionContext(bot_adapter=self, author=member_proxy, channel=channel_proxy)
            await self.interpreter.execute_event("member_join", ctx, {"member": member_proxy})

        @self.client.event
        async def on_member_remove(member: discord.Member):
            member_proxy = self._to_cord_member(member)
            sys_ch = member.guild.system_channel
            if not sys_ch and member.guild.text_channels:
                sys_ch = member.guild.text_channels[0]
            channel_proxy = self._to_cord_channel(sys_ch) if sys_ch else None
            ctx = ExecutionContext(bot_adapter=self, author=member_proxy, channel=channel_proxy)
            await self.interpreter.execute_event("member_leave", ctx, {"member": member_proxy})

    def _start_task(self, task: TaskDecl):
        """Starts a background task loop without duplicating across reconnects."""
        if task.name in self._active_tasks and not self._active_tasks[task.name].done():
            return

        async def task_loop():
            interval = task.interval.seconds if task.interval else 60.0
            while not self.client.is_closed():
                try:
                    await asyncio.sleep(interval)
                    ctx = ExecutionContext(bot_adapter=self, author=None, channel=None)
                    await self.interpreter.execute_block(task.body, self.interpreter.global_env, ctx)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"Error in task '{task.name}': {e}")

        self._active_tasks[task.name] = asyncio.create_task(task_loop())

    async def _sync_slash_commands(self):
        """Registers all declared slash commands onto discord.py's CommandTree and syncs with Discord."""
        tree = self.client.tree

        TYPE_MAPPING = {
            "member": discord.Member,
            "user": discord.User,
            "channel": discord.TextChannel,
            "role": discord.Role,
            "int": int,
            "integer": int,
            "float": float,
            "number": float,
            "bool": bool,
            "boolean": bool,
            "str": str,
            "string": str,
        }

        for cmd_name, cmd in self.registered_commands.items():
            if cmd.mode == "prefix":
                continue

            desc = (cmd.description or f"Cord command: {cmd_name}").strip()
            if not desc:
                desc = f"Cord command: {cmd_name}"
            if len(desc) > 100:
                desc = desc[:97] + "..."

            slash_name = cmd_name.lower()
            if len(slash_name) > 32:
                slash_name = slash_name[:32]

            def make_slash_callback(command_decl: CommandDecl):
                sig_params = [
                    inspect.Parameter("interaction", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=discord.Interaction)
                ]

                for param in command_decl.params:
                    p_name = param.name.lower()
                    hint = (param.type_hint or "str").lower()
                    base_type = TYPE_MAPPING.get(hint, str)

                    default_node = param.default_value
                    if default_node is not None:
                        if isinstance(default_node, Literal):
                            def_val = default_node.value
                        elif isinstance(default_node, DurationLiteral):
                            def_val = default_node.seconds
                        else:
                            def_val = None

                        if def_val is None:
                            ann = Optional[base_type]
                            def_val = None
                        else:
                            ann = base_type
                        sig_params.append(
                            inspect.Parameter(p_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=ann, default=def_val)
                        )
                    else:
                        sig_params.append(
                            inspect.Parameter(p_name, inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=base_type)
                        )

                async def slash_callback(interaction: discord.Interaction, *args, **kwargs):
                    if not interaction.response.is_done():
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

                    converted_kwargs = {}
                    for param in command_decl.params:
                        val = kwargs.get(param.name.lower(), kwargs.get(param.name))
                        if val is None:
                            converted_kwargs[param.name] = None
                        elif isinstance(val, (discord.Member, discord.User)):
                            converted_kwargs[param.name] = self._to_cord_member(val)
                        elif isinstance(val, discord.abc.GuildChannel):
                            converted_kwargs[param.name] = self._to_cord_channel(val)
                        elif isinstance(val, discord.Role):
                            converted_kwargs[param.name] = CordRole(role_id=val.id, name=val.name)
                        else:
                            converted_kwargs[param.name] = val

                    await self.interpreter.execute_command(command_decl, ctx, kwargs=converted_kwargs)

                slash_callback.__name__ = slash_name
                slash_callback.__signature__ = inspect.Signature(parameters=sig_params)
                return slash_callback

            # Remove previous command if already in tree to avoid duplicate registration error
            if tree.get_command(slash_name):
                tree.remove_command(slash_name)

            app_cmd = app_commands.Command(
                name=slash_name,
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

        cmd = self.registered_commands.get(cmd_name) or self.registered_commands.get(cmd_name.lower())
        if not cmd:
            return

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
                if not discord_member and hasattr(self, "client") and user_id:
                    discord_member = self.client.get_user(user_id)
                if discord_member:
                    args.append(self._to_cord_member(discord_member))
                else:
                    args.append(CordMember(member_id=user_id, name=f"User_{user_id}", bot_adapter=self))
            elif type_hint in ("int", "integer"):
                try: args.append(int(token_val))
                except ValueError: args.append(0)
            elif type_hint in ("float", "number"):
                try: args.append(float(token_val))
                except ValueError: args.append(0.0)
            elif type_hint in ("bool", "boolean"):
                args.append(token_val.lower() in ("true", "yes", "1"))
            elif type_hint in ("role",):
                match = re.search(r"\d+", token_val)
                role_id = int(match.group(0)) if match else 0
                discord_role = guild.get_role(role_id) if guild else None
                if discord_role:
                    args.append(CordRole(role_id=discord_role.id, name=discord_role.name))
                else:
                    args.append(CordRole(role_id=role_id, name=f"role_{role_id}"))
            elif type_hint in ("channel", "textchannel"):
                match = re.search(r"\d+", token_val)
                ch_id = int(match.group(0)) if match else 0
                ch = guild.get_channel(ch_id) if guild else None
                if ch:
                    args.append(self._to_cord_channel(ch))
                else:
                    args.append(CordChannel(channel_id=ch_id, name=token_val.lstrip("#")))
            else:
                args.append(token_val)

        return args

    def _to_cord_member(self, user: Union[discord.Member, discord.User]) -> Optional[CordMember]:
        if user is None:
            return None
        perms = []
        if isinstance(user, discord.Member):
            perms = [perm for perm, val in user.guild_permissions if val]
        return CordMember(
            member_id=user.id,
            name=user.name,
            discriminator=getattr(user, "discriminator", "0"),
            is_bot=user.bot,
            permissions=perms,
            avatar_url=str(user.display_avatar.url) if hasattr(user, "display_avatar") else "",
            raw_user=user,
            bot_adapter=self
        )

    def _to_cord_channel(self, channel: Any) -> Optional[CordChannel]:
        if channel is None:
            return None
        return CordChannel(channel_id=getattr(channel, "id", 0), name=getattr(channel, "name", "channel"))

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

    def resolve_channel(self, name: str) -> Optional[CordChannel]:
        clean = name.lstrip("#").strip().lower()
        if hasattr(self, "client") and self.client:
            # 1. Look for exact match with send permissions
            for guild in self.client.guilds:
                for ch in guild.text_channels:
                    perms = ch.permissions_for(guild.me) if guild.me else None
                    if ch.name.lower() == clean and (perms is None or (perms.send_messages and perms.view_channel)):
                        return self._to_cord_channel(ch)
            # 2. Look for fuzzy/alnum match with send permissions (e.g. #general matching #💬・general)
            import re
            alnum = re.sub(r"[^a-z0-9]", "", clean)
            if alnum:
                for guild in self.client.guilds:
                    for ch in guild.text_channels:
                        perms = ch.permissions_for(guild.me) if guild.me else None
                        ch_alnum = re.sub(r"[^a-z0-9]", "", ch.name.lower())
                        if (alnum == ch_alnum or alnum in ch_alnum or alnum in ch.name.lower()) and (perms is None or (perms.send_messages and perms.view_channel)):
                            return self._to_cord_channel(ch)
            # 3. Fallback to any exact match
            for guild in self.client.guilds:
                for ch in guild.text_channels:
                    if ch.name.lower() == clean:
                        return self._to_cord_channel(ch)
        return CordChannel(channel_id=0, name=clean)

    async def send_reply(self, ctx: ExecutionContext, content: Optional[str] = None, embed: Optional[CordEmbed] = None):
        discord_embed = self._to_discord_embed(embed) if embed else None
        if content is None and discord_embed is None:
            content = " "

        try:
            if ctx.is_interaction and isinstance(ctx.raw_event, discord.Interaction):
                if ctx.raw_event.response.is_done():
                    await ctx.raw_event.followup.send(content=content, embed=discord_embed)
                else:
                    await ctx.raw_event.response.send_message(content=content, embed=discord_embed)
            elif isinstance(ctx.raw_event, discord.Message):
                await ctx.raw_event.reply(content=content, embed=discord_embed)
            elif ctx.channel:
                # Fallback to channel send
                ch = self.client.get_channel(int(ctx.channel.id))
                if ch:
                    await ch.send(content=content, embed=discord_embed)
        except discord.errors.Forbidden as e:
            print(f"Warning: Failed to reply: Missing Permissions (403 Forbidden): {e}")
        except discord.errors.HTTPException as e:
            print(f"Warning: Failed to reply: {e}")

    async def send_channel_message(self, channel_ref: Any, content: Optional[str] = None, embed: Optional[CordEmbed] = None):
        discord_embed = self._to_discord_embed(embed) if embed else None
        if content is None and discord_embed is None:
            content = " "

        # 1. Target with numeric channel ID
        if hasattr(channel_ref, "id") and str(channel_ref.id) != "0":
            try:
                ch = self.client.get_channel(int(channel_ref.id))
                if ch:
                    perms = ch.permissions_for(ch.guild.me) if hasattr(ch, "guild") and ch.guild and ch.guild.me else None
                    if perms and (not perms.send_messages or not perms.view_channel):
                        print(f"Warning: Cannot send to #{ch.name}: Bot lacks 'Send Messages' or 'View Channel' permissions in this channel.")
                        return
                    try:
                        await ch.send(content=content, embed=discord_embed)
                        return
                    except discord.errors.Forbidden as e:
                        print(f"Warning: Cannot send to #{ch.name}: 403 Forbidden (Missing Access): {e}")
                        return
                    except discord.errors.HTTPException as e:
                        print(f"Warning: Failed to send to #{ch.name}: {e}")
                        return
            except (ValueError, TypeError):
                pass

        target = getattr(channel_ref, "name", str(channel_ref)).lstrip("#").strip()
        if target.isdigit():
            ch = self.client.get_channel(int(target))
            if ch:
                try:
                    await ch.send(content=content, embed=discord_embed)
                    return
                except discord.errors.Forbidden as e:
                    print(f"Warning: Cannot send to channel ID {target}: 403 Forbidden (Missing Access): {e}")
                    return
                except discord.errors.HTTPException as e:
                    print(f"Warning: Failed to send to channel ID {target}: {e}")
                    return

        # 2. Search for channel in guilds
        clean_target = target.lower()

        # Pass 1: exact match with send_messages permission
        for guild in self.client.guilds:
            for ch in guild.text_channels:
                perms = ch.permissions_for(guild.me) if guild.me else None
                if ch.name.lower() == clean_target:
                    if perms is None or (perms.send_messages and perms.view_channel):
                        try:
                            await ch.send(content=content, embed=discord_embed)
                            return
                        except (discord.errors.Forbidden, discord.errors.HTTPException) as e:
                            print(f"Warning: Cannot send to #{ch.name}: {e}")
                            return

        # Pass 2: normalized/fuzzy match with send_messages permission (e.g. #general matches #💬・general)
        import re
        clean_alnum = re.sub(r"[^a-z0-9]", "", clean_target)
        if clean_alnum:
            for guild in self.client.guilds:
                for ch in guild.text_channels:
                    perms = ch.permissions_for(guild.me) if guild.me else None
                    if perms is None or (perms.send_messages and perms.view_channel):
                        ch_alnum = re.sub(r"[^a-z0-9]", "", ch.name.lower())
                        if clean_alnum == ch_alnum or clean_alnum in ch_alnum or clean_alnum in ch.name.lower():
                            try:
                                await ch.send(content=content, embed=discord_embed)
                                return
                            except (discord.errors.Forbidden, discord.errors.HTTPException) as e:
                                print(f"Warning: Cannot send to #{ch.name}: {e}")
                                return

        # Pass 3: Channel was found by name, but bot lacks permissions
        for guild in self.client.guilds:
            for ch in guild.text_channels:
                if ch.name.lower() == clean_target:
                    print(f"Warning: Found #{ch.name} in guild '{guild.name}', but bot lacks 'Send Messages' or 'View Channel' permissions (Missing Access).")
                    return

        print(f"Warning: Channel '#{target}' was not found in any connected guild or is not accessible.")

    async def delete_message(self, ctx: ExecutionContext):
        if isinstance(ctx.raw_event, discord.Message):
            try:
                await ctx.raw_event.delete()
            except (discord.errors.Forbidden, discord.errors.HTTPException) as e:
                print(f"Warning: Could not delete message: {e}")

    async def wait_for_input(self, ctx: ExecutionContext, timeout: float = 60.0) -> Optional[str]:
        def check(m: discord.Message):
            if ctx.author and str(m.author.id) != str(ctx.author.id):
                return False
            if ctx.channel and str(m.channel.id) != str(ctx.channel.id):
                return False
            return True

        try:
            msg = await self.client.wait_for("message", check=check, timeout=timeout)
            return msg.content
        except asyncio.TimeoutError:
            return None

    def start(self):
        """Starts the discord client."""
        try:
            self.client.run(self.token)
        except KeyboardInterrupt:
            pass
