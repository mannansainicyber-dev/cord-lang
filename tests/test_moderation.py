import asyncio
import pytest
from cord.lexer import Lexer, TokenType
from cord.parser import Parser
from cord.interpreter import Interpreter
from cord.discord_adapter import MockDiscordAdapter
from cord.ast_nodes import BanStmt, KickStmt, TimeoutStmt, UnbanStmt


def test_parser_moderation_statements():
    code = (
        'command mod_actions(target: Member):\n'
        '    ban target reason="Severe violation"\n'
        '    kick target reason="Warning limit"\n'
        '    timeout target for 10m reason="Muted"\n'
        '    unban target reason="Pardoned"\n'
    )
    tokens = Lexer(code).tokenize()
    program = Parser(tokens).parse()
    cmd = program.statements[0]
    stmts = cmd.body.statements

    assert isinstance(stmts[0], BanStmt)
    assert stmts[0].target.name == "target"
    assert stmts[0].reason.value == "Severe violation"

    assert isinstance(stmts[1], KickStmt)
    assert stmts[1].target.name == "target"
    assert stmts[1].reason.value == "Warning limit"

    assert isinstance(stmts[2], TimeoutStmt)
    assert stmts[2].target.name == "target"
    assert stmts[2].duration.seconds == 600
    assert stmts[2].reason.value == "Muted"

    assert isinstance(stmts[3], UnbanStmt)
    assert stmts[3].target.name == "target"
    assert stmts[3].reason.value == "Pardoned"


def test_moderation_execution_mock():
    async def _run():
        code = (
            'command banish(target: Member):\n'
            '    require permission moderate_members\n'
            '    ban target reason="Excessive spam"\n'
            '    reply "Banned {target.name}."\n'
            '\n'
            'command mute(target: Member):\n'
            '    timeout target for 5m reason="Take a break"\n'
            '    reply "Timed out {target.name}."\n'
            '\n'
            'command kick_user(target: Member):\n'
            '    kick target reason="Inactivity"\n'
            '    reply "Kicked {target.name}."\n'
        )
        interpreter = Interpreter()
        adapter = MockDiscordAdapter(interpreter)
        tokens = Lexer(code).tokenize()
        program = Parser(tokens).parse()

        await interpreter.execute_program(program, ctx=adapter)

        # 1. Ban action
        await adapter.dispatch_prefix_command("!banish <@100>")
        actions = [m for m in adapter.sent_messages if m.get("action") == "ban"]
        assert len(actions) == 1
        assert actions[0]["reason"] == "Excessive spam"

        # 2. Timeout action
        await adapter.dispatch_prefix_command("!mute <@100>")
        timeouts = [m for m in adapter.sent_messages if m.get("action") == "timeout"]
        assert len(timeouts) == 1
        assert timeouts[0]["duration"] == 300
        assert timeouts[0]["reason"] == "Take a break"

        # 3. Kick action
        await adapter.dispatch_prefix_command("!kick_user <@100>")
        kicks = [m for m in adapter.sent_messages if m.get("action") == "kick"]
        assert len(kicks) == 1
        assert kicks[0]["reason"] == "Inactivity"

    asyncio.run(_run())
