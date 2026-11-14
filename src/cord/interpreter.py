"""
Tree-walking Interpreter for the Cord programming language.
Executes AST nodes within an asynchronous execution loop, safely sandboxed from host OS internals.
"""

import asyncio
import inspect
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from cord.ast_nodes import (
    ASTNode, Program, Block, Statement,
    BotDecl, ConfigDecl, Parameter, CommandDecl, EventDecl, TaskDecl, FunctionDecl,
    VarAssign, CompoundAssign, IfStmt, WhileStmt, ForStmt, ReturnStmt, PassStmt,
    ReplyStmt, SendStmt, DeleteStmt, RequireStmt, CooldownStmt, AskStmt, ModeStmt,
    ExprStmt, Literal, DurationLiteral, InterpolatedString, Identifier, ChannelRef,
    BinaryOp, UnaryOp, ListLiteral, MapLiteral, IndexAccess, MemberAccess, CallExpr,
    EmbedBlock, EmbedField, ButtonItem, SelectOption, SelectItem, ComponentBlock,
    BanStmt, KickStmt, TimeoutStmt, UnbanStmt
)
from cord.runtime import (
    Environment, CordRuntimeError, ReturnSignal, CordFunction, CordEmbed,
    CordMember, CordChannel, ExecutionContext, get_standard_environment,
    CordButton, CordSelectOption, CordSelect, CordView
)
from cord.storage import Store


class CooldownManager:
    """Tracks command cooldowns per user, guild, or channel."""
    def __init__(self):
        # Key: (cmd_name, per_type, entity_id) -> expiry_timestamp
        self._cooldowns: Dict[Tuple[str, str, str], float] = {}

    def check_and_set(self, cmd_name: str, per: str, entity_id: str, duration_sec: float) -> Optional[float]:
        """
        Returns None if allowed (and sets the cooldown), or remaining seconds if cooling down.
        """
        now = time.time()
        key = (cmd_name, per, entity_id)
        expiry = self._cooldowns.get(key, 0.0)
        if now < expiry:
            return expiry - now

        self._cooldowns[key] = now + duration_sec
        return None


class Interpreter:
    """
    Cord language execution engine.
    """

    def __init__(self, store: Optional[Store] = None):
        self.global_env = get_standard_environment()
        self.store = store or Store(db_path=":memory:")
        self.global_env.define("store", self.store)

        self.bot_name: str = "CordBot"
        self.config: Dict[str, Any] = {
            "prefix": "!",
            "status": "online",
            "activity": "powered by Cord"
        }
        self.commands: Dict[str, CommandDecl] = {}
        self.events: Dict[str, List[EventDecl]] = {}
        self.tasks: Dict[str, TaskDecl] = {}
        self.cooldowns = CooldownManager()

    async def execute_program(self, program: Program, ctx: Optional[ExecutionContext] = None):
        """Executes top-level program statements to configure the bot, register handlers, etc."""
        for stmt in program.statements:
            await self.execute_statement(stmt, self.global_env, ctx)

    async def execute_command(
        self,
        cmd: CommandDecl,
        ctx: ExecutionContext,
        args: Optional[List[Any]] = None,
        kwargs: Optional[Dict[str, Any]] = None
    ):
        """Executes a command handler with parameter binding and signal handling."""
        cmd_env = Environment(parent=self.global_env)
        args = args or []
        kwargs = kwargs or {}

        for i, param in enumerate(cmd.params):
            if i < len(args):
                cmd_env.define(param.name, args[i])
            elif param.name in kwargs:
                cmd_env.define(param.name, kwargs[param.name])
            elif param.default_value:
                val = await self.eval_expr(param.default_value, self.global_env, ctx)
                cmd_env.define(param.name, val)
            else:
                cmd_env.define(param.name, None)

        try:
            await self.execute_block(cmd.body, cmd_env, ctx)
        except ReturnSignal:
            pass

    async def execute_event(
        self,
        event_name: str,
        ctx: ExecutionContext,
        event_args: Optional[Dict[str, Any]] = None
    ):
        """Executes all registered event handlers for an event."""
        event_args = event_args or {}
        handlers = self.events.get(event_name, [])
        for handler in handlers:
            evt_env = Environment(parent=self.global_env)
            for param in handler.params:
                if param.name in event_args:
                    evt_env.define(param.name, event_args[param.name])
                elif param.name in ("member", "author", "user"):
                    evt_env.define(param.name, getattr(ctx, "member", ctx.author))
                elif param.name == "button":
                    evt_env.define(param.name, getattr(ctx, "button", None))
                elif param.name == "select":
                    evt_env.define(param.name, getattr(ctx, "select", None))
                elif param.name in ("selected", "value"):
                    evt_env.define(param.name, getattr(ctx, "selected", None))
                elif param.name == "values":
                    evt_env.define(param.name, getattr(ctx, "values", None))
                elif param.name == "message":
                    evt_env.define("message", getattr(ctx, "raw_event", None))
                else:
                    evt_env.define(param.name, None)
            try:
                await self.execute_block(handler.body, evt_env, ctx)
            except ReturnSignal:
                pass

    async def execute_statement(self, stmt: Statement, env: Environment, ctx: Optional[ExecutionContext] = None):
        bot_adapter = getattr(ctx, "bot", ctx) if ctx else None

        if isinstance(stmt, BotDecl):
            self.bot_name = stmt.name
            if bot_adapter and hasattr(bot_adapter, "bot_name"):
                bot_adapter.bot_name = stmt.name

        elif isinstance(stmt, ConfigDecl):
            for k, expr in stmt.settings.items():
                val = await self.eval_expr(expr, env, ctx)
                self.config[k] = val
                if bot_adapter and hasattr(bot_adapter, "apply_config"):
                    bot_adapter.apply_config(k, val)

        elif isinstance(stmt, CommandDecl):
            self.commands[stmt.name] = stmt
            if bot_adapter and hasattr(bot_adapter, "register_command"):
                bot_adapter.register_command(stmt)

        elif isinstance(stmt, EventDecl):
            if stmt.event_name not in self.events:
                self.events[stmt.event_name] = []
            self.events[stmt.event_name].append(stmt)
            if bot_adapter and hasattr(bot_adapter, "register_event"):
                bot_adapter.register_event(stmt)

        elif isinstance(stmt, TaskDecl):
            self.tasks[stmt.name] = stmt
            if bot_adapter and hasattr(bot_adapter, "register_task"):
                bot_adapter.register_task(stmt)

        elif isinstance(stmt, FunctionDecl):
            fn = CordFunction(
                name=stmt.name,
                params=stmt.params,
                body=stmt.body,
                closure=env
            )
            env.define(stmt.name, fn)

        elif isinstance(stmt, VarAssign):
            val = await self.eval_expr(stmt.value, env, ctx)
            await self.assign_target(stmt.target, val, env, ctx)

        elif isinstance(stmt, CompoundAssign):
            old_val = await self.eval_expr(stmt.target, env, ctx)
            delta = await self.eval_expr(stmt.value, env, ctx)
            if stmt.op == "+": new_val = old_val + delta
            elif stmt.op == "-": new_val = old_val - delta
            elif stmt.op == "*": new_val = old_val * delta
            elif stmt.op == "/": new_val = old_val / delta
            else:
                raise CordRuntimeError(f"Unsupported compound assignment operator '{stmt.op}'", stmt.line, stmt.col)
            await self.assign_target(stmt.target, new_val, env, ctx)

        elif isinstance(stmt, IfStmt):
            cond_val = await self.eval_expr(stmt.condition, env, ctx)
            if cond_val:
                await self.execute_block(stmt.then_body, env, ctx)
                return

            handled = False
            for elif_cond, elif_body in stmt.elif_branches:
                elif_val = await self.eval_expr(elif_cond, env, ctx)
                if elif_val:
                    await self.execute_block(elif_body, env, ctx)
                    handled = True
                    break

            if not handled and stmt.else_body:
                await self.execute_block(stmt.else_body, env, ctx)

        elif isinstance(stmt, WhileStmt):
            while await self.eval_expr(stmt.condition, env, ctx):
                await self.execute_block(stmt.body, env, ctx)

        elif isinstance(stmt, ForStmt):
            iterable = await self.eval_expr(stmt.iterable, env, ctx)
            try:
                iter_items = list(iterable)
            except Exception:
                raise CordRuntimeError(f"'{type(iterable).__name__}' object is not iterable", stmt.line, stmt.col)

            for item in iter_items:
                env.assign(stmt.var_name, item)
                await self.execute_block(stmt.body, env, ctx)

        elif isinstance(stmt, ReturnStmt):
            ret_val = await self.eval_expr(stmt.value, env, ctx) if stmt.value else None
            raise ReturnSignal(ret_val)

        elif isinstance(stmt, PassStmt):
            pass

        elif isinstance(stmt, ReplyStmt):
            if not ctx:
                raise CordRuntimeError("'reply' can only be used inside a command or event handler", stmt.line, stmt.col)
            embed_obj = await self.build_embed(stmt.embed, env, ctx) if stmt.embed else None
            view_obj = await self.build_view(stmt.components, env, ctx) if stmt.components else None
            msg_val = await self.eval_expr(stmt.expr, env, ctx) if stmt.expr else None
            await ctx.reply(content=str(msg_val) if msg_val is not None else None, embed=embed_obj, view=view_obj)

        elif isinstance(stmt, SendStmt):
            if not ctx:
                raise CordRuntimeError("'send' can only be used when bot runtime context is active", stmt.line, stmt.col)
            target = await self.eval_expr(stmt.target, env, ctx)
            embed_obj = await self.build_embed(stmt.embed, env, ctx) if stmt.embed else None
            view_obj = await self.build_view(stmt.components, env, ctx) if stmt.components else None
            msg_val = await self.eval_expr(stmt.expr, env, ctx) if stmt.expr else None
            await ctx.send(channel_ref=target, content=str(msg_val) if msg_val is not None else None, embed=embed_obj, view=view_obj)

        elif isinstance(stmt, DeleteStmt):
            if not ctx:
                raise CordRuntimeError("'delete' requires an active command/event context", stmt.line, stmt.col)
            if stmt.target:
                target_msg = await self.eval_expr(stmt.target, env, ctx)
                if hasattr(target_msg, "delete") and callable(target_msg.delete):
                    if inspect.iscoroutinefunction(target_msg.delete):
                        await target_msg.delete()
                    else:
                        target_msg.delete()
            else:
                await ctx.delete_trigger()

        elif isinstance(stmt, BanStmt):
            target_obj = await self.eval_expr(stmt.target, env, ctx)
            reason_val = await self.eval_expr(stmt.reason, env, ctx) if stmt.reason else None
            reason_str = str(reason_val) if reason_val is not None else None
            if hasattr(target_obj, "ban") and callable(target_obj.ban):
                if bot_adapter and not getattr(target_obj, "bot_adapter", None):
                    target_obj.bot_adapter = bot_adapter
                if inspect.iscoroutinefunction(target_obj.ban):
                    await target_obj.ban(reason=reason_str)
                else:
                    target_obj.ban(reason=reason_str)
            elif bot_adapter and hasattr(bot_adapter, "ban_member"):
                await bot_adapter.ban_member(target_obj, reason=reason_str)

        elif isinstance(stmt, KickStmt):
            target_obj = await self.eval_expr(stmt.target, env, ctx)
            reason_val = await self.eval_expr(stmt.reason, env, ctx) if stmt.reason else None
            reason_str = str(reason_val) if reason_val is not None else None
            if hasattr(target_obj, "kick") and callable(target_obj.kick):
                if bot_adapter and not getattr(target_obj, "bot_adapter", None):
                    target_obj.bot_adapter = bot_adapter
                if inspect.iscoroutinefunction(target_obj.kick):
                    await target_obj.kick(reason=reason_str)
                else:
                    target_obj.kick(reason=reason_str)
            elif bot_adapter and hasattr(bot_adapter, "kick_member"):
                await bot_adapter.kick_member(target_obj, reason=reason_str)

        elif isinstance(stmt, TimeoutStmt):
            target_obj = await self.eval_expr(stmt.target, env, ctx)
            dur_val = await self.eval_expr(stmt.duration, env, ctx)
            reason_val = await self.eval_expr(stmt.reason, env, ctx) if stmt.reason else None
            reason_str = str(reason_val) if reason_val is not None else None
            dur_sec = dur_val if isinstance(dur_val, (int, float)) else getattr(dur_val, "seconds", 60)
            if hasattr(target_obj, "timeout") and callable(target_obj.timeout):
                if bot_adapter and not getattr(target_obj, "bot_adapter", None):
                    target_obj.bot_adapter = bot_adapter
                if inspect.iscoroutinefunction(target_obj.timeout):
                    await target_obj.timeout(duration=dur_sec, reason=reason_str)
                else:
                    target_obj.timeout(duration=dur_sec, reason=reason_str)
            elif bot_adapter and hasattr(bot_adapter, "timeout_member"):
                await bot_adapter.timeout_member(target_obj, duration=dur_sec, reason=reason_str)

        elif isinstance(stmt, UnbanStmt):
            target_obj = await self.eval_expr(stmt.target, env, ctx)
            reason_val = await self.eval_expr(stmt.reason, env, ctx) if stmt.reason else None
            reason_str = str(reason_val) if reason_val is not None else None
            if hasattr(target_obj, "unban") and callable(target_obj.unban):
                if bot_adapter and not getattr(target_obj, "bot_adapter", None):
                    target_obj.bot_adapter = bot_adapter
                if inspect.iscoroutinefunction(target_obj.unban):
                    await target_obj.unban(reason=reason_str)
                else:
                    target_obj.unban(reason=reason_str)
            elif bot_adapter and hasattr(bot_adapter, "unban_member"):
                await bot_adapter.unban_member(target_obj, reason=reason_str)

        elif isinstance(stmt, RequireStmt):
            if not ctx or not ctx.author:
                return
            if stmt.kind == "permission":
                perm_needed = stmt.value
                if not ctx.author.has_permission(perm_needed):
                    await ctx.reply(f"⛔ You do not have the required permission: `{perm_needed}`")
                    raise ReturnSignal(None)

        elif isinstance(stmt, CooldownStmt):
            if not ctx or not ctx.author:
                return
            current_cmd_name = getattr(ctx, "command_name", "unknown")
            entity_id = ctx.author.id
            if stmt.per == "guild" and ctx.guild_id:
                entity_id = str(ctx.guild_id)
            elif stmt.per == "channel" and ctx.channel:
                entity_id = str(ctx.channel.id)

            remaining = self.cooldowns.check_and_set(current_cmd_name, stmt.per, entity_id, stmt.duration.seconds)
            if remaining is not None:
                await ctx.reply(f"⏳ This command is on cooldown. Try again in {remaining:.1f}s.")
                raise ReturnSignal(None)

        elif isinstance(stmt, AskStmt):
            if not ctx:
                raise CordRuntimeError("'ask' can only be used inside a command handler", stmt.line, stmt.col)
            prompt_str = None
            if stmt.prompt:
                prompt_str = str(await self.eval_expr(stmt.prompt, env, ctx))
            timeout_sec = stmt.timeout.seconds if stmt.timeout else 60.0
            response = await ctx.ask(prompt=prompt_str, timeout=timeout_sec)
            env.assign(stmt.var_name, response)

        elif isinstance(stmt, ModeStmt):
            pass

        elif isinstance(stmt, ExprStmt):
            await self.eval_expr(stmt.expr, env, ctx)

        else:
            raise CordRuntimeError(f"Unsupported statement type: {type(stmt).__name__}", stmt.line, stmt.col)

    async def execute_block(self, block: Block, env: Environment, ctx: Optional[ExecutionContext] = None):
        for stmt in block.statements:
            await self.execute_statement(stmt, env, ctx)

    async def assign_target(self, target: ASTNode, value: Any, env: Environment, ctx: Optional[ExecutionContext]):
        if isinstance(target, Identifier):
            env.assign(target.name, value)
        elif isinstance(target, IndexAccess):
            target_obj = await self.eval_expr(target.target, env, ctx)
            idx_val = await self.eval_expr(target.index, env, ctx)
            try:
                target_obj[idx_val] = value
            except Exception as e:
                raise CordRuntimeError(f"Cannot set index '{idx_val}': {e}", target.line, target.col)
        elif isinstance(target, MemberAccess):
            target_obj = await self.eval_expr(target.target, env, ctx)
            member_name = target.member
            if isinstance(target_obj, dict):
                target_obj[member_name] = value
            elif hasattr(target_obj, member_name):
                setattr(target_obj, member_name, value)
            else:
                try:
                    target_obj[member_name] = value
                except Exception:
                    raise CordRuntimeError(f"Cannot set attribute '{member_name}' on {type(target_obj).__name__}", target.line, target.col)
        else:
            raise CordRuntimeError(f"Invalid assignment target: {type(target).__name__}", target.line, target.col)

    async def eval_expr(self, expr: ASTNode, env: Environment, ctx: Optional[ExecutionContext] = None) -> Any:
        if isinstance(expr, Literal):
            return expr.value

        elif isinstance(expr, DurationLiteral):
            return expr.seconds

        elif isinstance(expr, InterpolatedString):
            res_parts = []
            for part in expr.parts:
                if isinstance(part, str):
                    res_parts.append(part)
                else:
                    val = await self.eval_expr(part, env, ctx)
                    res_parts.append(str(val) if val is not None else "")
            return "".join(res_parts)

        elif isinstance(expr, Identifier):
            name = expr.name
            if env.has(name):
                return env.get(name)
            # Check context shortcuts
            if ctx:
                if name in ("author", "sender", "user"):
                    return ctx.author
                elif name == "channel":
                    return ctx.channel
                elif name == "bot":
                    return ctx.bot
                elif name == "member":
                    return getattr(ctx, "member", ctx.author)
                elif name == "button":
                    return getattr(ctx, "button", None)
                elif name == "select":
                    return getattr(ctx, "select", None)
                elif name in ("selected", "value"):
                    return getattr(ctx, "selected", None)
                elif name == "values":
                    return getattr(ctx, "values", None)
            raise CordRuntimeError(f"Undefined variable or name '{name}'", expr.line, expr.col)

        elif isinstance(expr, ChannelRef):
            # Returns channel name or resolved channel from ctx
            if ctx and ctx.bot:
                resolved = ctx.bot.resolve_channel(expr.channel_name)
                if resolved:
                    return resolved
            return expr.channel_name

        elif isinstance(expr, BinaryOp):
            left_val = await self.eval_expr(expr.left, env, ctx)
            # Short-circuit logic for and/or
            if expr.op == "and":
                return left_val and (await self.eval_expr(expr.right, env, ctx))
            if expr.op == "or":
                return left_val or (await self.eval_expr(expr.right, env, ctx))

            right_val = await self.eval_expr(expr.right, env, ctx)
            op = expr.op

            if op == "+":
                if isinstance(left_val, str) and not isinstance(right_val, str):
                    return left_val + str(right_val)
                elif not isinstance(left_val, str) and isinstance(right_val, str):
                    return str(left_val) + right_val
                return left_val + right_val

            if op in ("-", "*", "/", "%"):
                if isinstance(left_val, str) and (left_val.isdigit() or (left_val.startswith("-") and left_val[1:].isdigit())):
                    left_val = int(left_val)
                if isinstance(right_val, str) and (right_val.isdigit() or (right_val.startswith("-") and right_val[1:].isdigit())):
                    right_val = int(right_val)

            if left_val is None or right_val is None:
                if op in ("<", "<=", ">", ">="):
                    raise CordRuntimeError(f"Cannot compare null with a value in comparison '{op}'", expr.line, expr.col)

            if op == "-": return left_val - right_val
            elif op == "*": return left_val * right_val
            elif op == "/": return left_val / right_val
            elif op == "%": return left_val % right_val
            elif op == "==": return left_val == right_val
            elif op == "!=": return left_val != right_val
            elif op == "<": return left_val < right_val
            elif op == "<=": return left_val <= right_val
            elif op == ">": return left_val > right_val
            elif op == ">=": return left_val >= right_val
            else:
                raise CordRuntimeError(f"Unknown binary operator '{op}'", expr.line, expr.col)

        elif isinstance(expr, UnaryOp):
            operand_val = await self.eval_expr(expr.operand, env, ctx)
            if expr.op == "not":
                return not operand_val
            elif expr.op == "-":
                return -operand_val
            elif expr.op == "+":
                return +operand_val
            else:
                raise CordRuntimeError(f"Unknown unary operator '{expr.op}'", expr.line, expr.col)

        elif isinstance(expr, ListLiteral):
            elements = []
            for el in expr.elements:
                elements.append(await self.eval_expr(el, env, ctx))
            return elements

        elif isinstance(expr, MapLiteral):
            mapping = {}
            for k_expr, v_expr in expr.pairs:
                k_val = await self.eval_expr(k_expr, env, ctx)
                v_val = await self.eval_expr(v_expr, env, ctx)
                mapping[k_val] = v_val
            return mapping

        elif isinstance(expr, IndexAccess):
            target_obj = await self.eval_expr(expr.target, env, ctx)
            idx_val = await self.eval_expr(expr.index, env, ctx)
            try:
                return target_obj[idx_val]
            except Exception as e:
                raise CordRuntimeError(f"Subscript error on '{idx_val}': {e}", expr.line, expr.col)

        elif isinstance(expr, MemberAccess):
            target_obj = await self.eval_expr(expr.target, env, ctx)
            if target_obj is None:
                return None
            member = expr.member
            # If target_obj has a callable attribute/method directly, return it
            if hasattr(target_obj, member):
                attr = getattr(target_obj, member)
                if callable(attr):
                    return attr
            # Check mapping keys
            if isinstance(target_obj, dict):
                if member in target_obj:
                    return target_obj[member]
                if hasattr(target_obj, member):
                    return getattr(target_obj, member)
                return None
            if hasattr(target_obj, member):
                return getattr(target_obj, member)
            try:
                return target_obj[member]
            except Exception:
                raise CordRuntimeError(f"'{type(target_obj).__name__}' has no attribute or key '{member}'", expr.line, expr.col)

        elif isinstance(expr, CallExpr):
            callee = await self.eval_expr(expr.callee, env, ctx)
            args = [await self.eval_expr(a, env, ctx) for a in expr.args]
            kwargs = {k: await self.eval_expr(v, env, ctx) for k, v in expr.kwargs.items()}

            if isinstance(callee, CordFunction):
                return await self.invoke_cord_function(callee, args, kwargs, ctx)
            elif callable(callee):
                if inspect.iscoroutinefunction(callee):
                    return await callee(*args, **kwargs)
                return callee(*args, **kwargs)
            else:
                raise CordRuntimeError(f"'{type(callee).__name__}' object is not callable", expr.line, expr.col)

        else:
            raise CordRuntimeError(f"Unsupported expression node: {type(expr).__name__}", expr.line, expr.col)

    async def invoke_cord_function(self, fn: CordFunction, args: List[Any], kwargs: Dict[str, Any], ctx: Optional[ExecutionContext]) -> Any:
        fn_env = Environment(parent=fn.closure)
        for i, param in enumerate(fn.params):
            if i < len(args):
                fn_env.define(param.name, args[i])
            elif param.name in kwargs:
                fn_env.define(param.name, kwargs[param.name])
            elif param.default_value:
                default_val = await self.eval_expr(param.default_value, fn.closure, ctx)
                fn_env.define(param.name, default_val)
            else:
                raise CordRuntimeError(f"Missing required argument '{param.name}' for function '{fn.name}'")

        try:
            await self.execute_block(fn.body, fn_env, ctx)
            return None
        except ReturnSignal as ret:
            return ret.value

    async def build_embed(self, node: EmbedBlock, env: Environment, ctx: Optional[ExecutionContext]) -> CordEmbed:
        embed = CordEmbed()
        if node.title:
            embed.title = str(await self.eval_expr(node.title, env, ctx))
        if node.description:
            embed.description = str(await self.eval_expr(node.description, env, ctx))
        if node.color:
            embed.color = await self.eval_expr(node.color, env, ctx)
        if node.thumbnail:
            embed.thumbnail = str(await self.eval_expr(node.thumbnail, env, ctx))
        if node.image:
            embed.image = str(await self.eval_expr(node.image, env, ctx))
        if node.footer:
            embed.footer = str(await self.eval_expr(node.footer, env, ctx))

        for fld in node.fields:
            name_val = str(await self.eval_expr(fld.name, env, ctx))
            content_val = str(await self.eval_expr(fld.value, env, ctx))
            inline_val = bool(await self.eval_expr(fld.inline, env, ctx))
            embed.add_field(name_val, content_val, inline=inline_val)

        return embed

    async def build_view(self, node: ComponentBlock, env: Environment, ctx: Optional[ExecutionContext]) -> CordView:
        view = CordView()
        for item in node.items:
            if isinstance(item, ButtonItem):
                custom_id = str(await self.eval_expr(item.custom_id, env, ctx))
                label = str(await self.eval_expr(item.label, env, ctx)) if item.label else None
                style = str(await self.eval_expr(item.style, env, ctx)) if item.style else "primary"
                emoji = str(await self.eval_expr(item.emoji, env, ctx)) if item.emoji else None
                url = str(await self.eval_expr(item.url, env, ctx)) if item.url else None
                disabled = bool(await self.eval_expr(item.disabled, env, ctx)) if item.disabled else False
                view.add_item(CordButton(
                    custom_id=custom_id,
                    label=label,
                    style=style,
                    emoji=emoji,
                    url=url,
                    disabled=disabled
                ))
            elif isinstance(item, SelectItem):
                custom_id = str(await self.eval_expr(item.custom_id, env, ctx))
                placeholder = str(await self.eval_expr(item.placeholder, env, ctx)) if item.placeholder else None
                min_vals = int(await self.eval_expr(item.min_values, env, ctx)) if item.min_values else 1
                max_vals = int(await self.eval_expr(item.max_values, env, ctx)) if item.max_values else 1
                disabled = bool(await self.eval_expr(item.disabled, env, ctx)) if item.disabled else False
                options = []
                for opt in item.options:
                    opt_val = str(await self.eval_expr(opt.value, env, ctx))
                    opt_lbl = str(await self.eval_expr(opt.label, env, ctx)) if opt.label else opt_val
                    opt_desc = str(await self.eval_expr(opt.description, env, ctx)) if opt.description else None
                    opt_emoji = str(await self.eval_expr(opt.emoji, env, ctx)) if opt.emoji else None
                    opt_def = bool(await self.eval_expr(opt.default, env, ctx)) if opt.default else False
                    options.append(CordSelectOption(
                        value=opt_val,
                        label=opt_lbl,
                        description=opt_desc,
                        emoji=opt_emoji,
                        default=opt_def
                    ))
                view.add_item(CordSelect(
                    custom_id=custom_id,
                    placeholder=placeholder,
                    min_values=min_vals,
                    max_values=max_vals,
                    disabled=disabled,
                    options=options
                ))
        return view
