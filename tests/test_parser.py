"""
Tests for the Cord Parser.
"""

import pytest
from cord.lexer import Lexer
from cord.parser import Parser, ParserError
from cord.ast_nodes import (
    Program, BotDecl, ConfigDecl, CommandDecl, EventDecl, TaskDecl, FunctionDecl,
    ReplyStmt, SendStmt, IfStmt, WhileStmt, ForStmt, ReturnStmt, RequireStmt,
    CooldownStmt, AskStmt, InterpolatedString, EmbedBlock, Literal
)


def parse_code(code: str) -> Program:
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()


def test_parse_bot_and_config():
    code = (
        'bot "HelperBot"\n'
        'config:\n'
        '    prefix = "!"\n'
        '    status = "online"\n'
    )
    prog = parse_code(code)
    assert len(prog.statements) == 2
    assert isinstance(prog.statements[0], BotDecl)
    assert prog.statements[0].name == "HelperBot"

    cfg = prog.statements[1]
    assert isinstance(cfg, ConfigDecl)
    assert "prefix" in cfg.settings
    assert "status" in cfg.settings


def test_parse_command_with_parameters_and_mode():
    code = (
        'slash command warn(target: Member, reason = "No reason"):\n'
        '    require permission moderate_members\n'
        '    cooldown 5s per user\n'
        '    reply "Warned!"\n'
    )
    prog = parse_code(code)
    assert len(prog.statements) == 1
    cmd = prog.statements[0]
    assert isinstance(cmd, CommandDecl)
    assert cmd.name == "warn"
    assert cmd.mode == "slash"
    assert len(cmd.params) == 2
    assert cmd.params[0].name == "target"
    assert cmd.params[0].type_hint == "Member"
    assert cmd.params[1].name == "reason"
    assert cmd.params[1].default_value is not None

    body = cmd.body.statements
    assert isinstance(body[0], RequireStmt)
    assert body[0].value == "moderate_members"
    assert isinstance(body[1], CooldownStmt)
    assert body[1].duration.seconds == 5.0
    assert body[1].per == "user"
    assert isinstance(body[2], ReplyStmt)


def test_parse_beginner_when_event():
    code = (
        'when someone joins:\n'
        '    send #welcome "Welcome {member.name}!"\n'
    )
    prog = parse_code(code)
    assert len(prog.statements) == 1
    evt = prog.statements[0]
    assert isinstance(evt, EventDecl)
    assert evt.event_name == "member_join"
    assert len(evt.params) == 1
    assert evt.params[0].name == "member"

    body_stmt = evt.body.statements[0]
    assert isinstance(body_stmt, SendStmt)
    assert isinstance(body_stmt.expr, InterpolatedString)


def test_parse_embed():
    code = (
        'command info:\n'
        '    reply embed:\n'
        '        title "Bot Info"\n'
        '        description "A bot written in Cord"\n'
        '        color "#5865F2"\n'
        '        field "Uptime" "99.9%" inline=true\n'
    )
    prog = parse_code(code)
    cmd = prog.statements[0]
    reply_stmt = cmd.body.statements[0]
    assert isinstance(reply_stmt, ReplyStmt)
    assert reply_stmt.embed is not None
    embed = reply_stmt.embed
    assert isinstance(embed, EmbedBlock)
    assert len(embed.fields) == 1
    assert embed.fields[0].inline.value is True


def test_parse_task_and_function():
    code = (
        'fn add(a, b):\n'
        '    return a + b\n'
        '\n'
        'task heartbeat every 1m:\n'
        '    reply "thump"\n'
    )
    prog = parse_code(code)
    assert len(prog.statements) == 2
    fn = prog.statements[0]
    assert isinstance(fn, FunctionDecl)
    assert fn.name == "add"
    assert len(fn.params) == 2

    task = prog.statements[1]
    assert isinstance(task, TaskDecl)
    assert task.name == "heartbeat"
    assert task.interval.seconds == 60.0


def test_parse_ask_statement():
    code = (
        'command ask_test:\n'
        '    ask for name "What is your name?" timeout=30s\n'
    )
    prog = parse_code(code)
    ask_stmt = prog.statements[0].body.statements[0]
    assert isinstance(ask_stmt, AskStmt)
    assert ask_stmt.var_name == "name"
    assert ask_stmt.prompt is not None
    assert ask_stmt.timeout.seconds == 30.0


def test_parse_control_flow():
    code = (
        'if x > 10:\n'
        '    y = 1\n'
        'elif x == 10:\n'
        '    y = 0\n'
        'else:\n'
        '    y = -1\n'
    )
    prog = parse_code(code)
    if_stmt = prog.statements[0]
    assert isinstance(if_stmt, IfStmt)
    assert len(if_stmt.elif_branches) == 1
    assert if_stmt.else_body is not None


def test_parse_syntax_error():
    code = 'command ping\n    reply "missing colon"'
    with pytest.raises(ParserError) as exc_info:
        parse_code(code)
    assert "Expected ':'" in str(exc_info.value)
