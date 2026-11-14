"""
Tests for Discord Adapter, Dual Command Registration, and Event Dispatching.
Tests run completely offline without Discord tokens or network dependencies.
"""

import pytest
import asyncio
from cord.lexer import Lexer
from cord.parser import Parser
from cord.interpreter import Interpreter
from cord.discord_adapter import MockDiscordAdapter, DiscordAdapter
from cord.runtime import CordMember, CordChannel


def setup_bot(code: str) -> tuple[Interpreter, MockDiscordAdapter]:
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    program = Parser(tokens).parse()

    interp = Interpreter()
    adapter = MockDiscordAdapter(interp)
    asyncio.run(interp.execute_program(program, ctx=adapter))
    # Also register commands & events on adapter
    for cmd in interp.commands.values():
        adapter.register_command(cmd)
    for evts in interp.events.values():
        for evt in evts:
            adapter.register_event(evt)
    return interp, adapter


def test_dual_command_dispatch():
    code = (
        'command ping:\n'
        '    reply "Pong! Latency: 15ms"\n'
    )
    _, adapter = setup_bot(code)

    # 1. Test invocation via prefix
    asyncio.run(adapter.dispatch_prefix_command("!ping"))
    assert len(adapter.sent_messages) == 1
    assert adapter.sent_messages[0]["action"] == "reply"
    assert "Pong!" in adapter.sent_messages[0]["content"]

    # 2. Test invocation via slash interaction
    asyncio.run(adapter.dispatch_slash_command("ping", kwargs={}))
    assert len(adapter.sent_messages) == 2
    assert "Pong!" in adapter.sent_messages[1]["content"]


def test_explicit_modality_restrictions():
    code = (
        'slash command slash_only:\n'
        '    reply "Slash only!"\n'
        '\n'
        'prefix command prefix_only:\n'
        '    reply "Prefix only!"\n'
    )
    _, adapter = setup_bot(code)

    # Try triggering slash_only via prefix: should do nothing
    asyncio.run(adapter.dispatch_prefix_command("!slash_only"))
    assert len(adapter.sent_messages) == 0

    # Trigger slash_only via slash: succeeds
    asyncio.run(adapter.dispatch_slash_command("slash_only", kwargs={}))
    assert len(adapter.sent_messages) == 1
    assert adapter.sent_messages[0]["content"] == "Slash only!"

    # Try triggering prefix_only via slash: should do nothing
    asyncio.run(adapter.dispatch_slash_command("prefix_only", kwargs={}))
    assert len(adapter.sent_messages) == 1

    # Trigger prefix_only via prefix: succeeds
    asyncio.run(adapter.dispatch_prefix_command("!prefix_only"))
    assert len(adapter.sent_messages) == 2
    assert adapter.sent_messages[1]["content"] == "Prefix only!"


def test_prefix_argument_conversion():
    code = (
        'command warn(target: Member, reason = "Spamming"):\n'
        '    reply "Warned {target.name}: {reason}"\n'
    )
    _, adapter = setup_bot(code)

    # Dispatch prefix command with mention and multi-word reason
    asyncio.run(adapter.dispatch_prefix_command("!warn <@100> Rule 1 violation"))
    assert len(adapter.sent_messages) == 1
    assert "Warned TestUser: Rule 1 violation" in adapter.sent_messages[0]["content"]


def test_member_join_event():
    code = (
        'when someone joins:\n'
        '    send #welcome "Welcome to the server, {member.name}!"\n'
    )
    _, adapter = setup_bot(code)

    new_member = CordMember(member_id=202, name="Newbie")
    asyncio.run(adapter.dispatch_event("member_join", member=new_member))

    assert len(adapter.sent_messages) == 1
    assert adapter.sent_messages[0]["action"] == "send"
    assert adapter.sent_messages[0]["channel"] == "welcome"
    assert "Welcome to the server, Newbie!" in adapter.sent_messages[0]["content"]


def test_interactive_ask_flow():
    code = (
        'command quiz:\n'
        '    ask for answer "What is 2+2?" timeout=5s\n'
        '    if answer == "4":\n'
        '        reply "Correct!"\n'
        '    else:\n'
        '        reply "Wrong!"\n'
    )
    interp, adapter = setup_bot(code)

    # Queue mock input
    adapter.push_input("4")

    asyncio.run(adapter.dispatch_prefix_command("!quiz"))
    assert len(adapter.sent_messages) == 2
    assert adapter.sent_messages[0]["content"] == "What is 2+2?"
    assert adapter.sent_messages[1]["content"] == "Correct!"


def test_token_validation_error():
    interp = Interpreter()
    # Missing token
    with pytest.raises(ValueError) as exc:
        DiscordAdapter(interp, token="")
    assert "Missing or invalid Discord bot token" in str(exc.value)

    # Placeholder token
    with pytest.raises(ValueError) as exc:
        DiscordAdapter(interp, token="YOUR_BOT_TOKEN_HERE")
    assert "Missing or invalid Discord bot token" in str(exc.value)
