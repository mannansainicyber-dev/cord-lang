import pytest
import asyncio
from cord.lexer import Lexer, TokenType
from cord.parser import Parser
from cord.interpreter import Interpreter
from cord.discord_adapter import MockDiscordAdapter, DiscordAdapter
from cord.runtime import CordButton, CordSelect, CordSelectOption, CordView


def test_lexer_component_tokens():
    code = "reply 'test' with:\n    button 'btn':\n    select 'sel':\n    option 'opt':"
    tokens = Lexer(code).tokenize()
    types = [t.type for t in tokens if t.type not in (TokenType.NEWLINE, TokenType.INDENT, TokenType.DEDENT, TokenType.EOF)]
    assert TokenType.WITH in types
    assert TokenType.BUTTON in types
    assert TokenType.SELECT in types
    assert TokenType.OPTION in types


def test_parser_button_and_select_components():
    code = (
        'command menu:\n'
        '    reply "Please choose:" with:\n'
        '        button "verify_btn":\n'
        '            label: "Verify Me"\n'
        '            style: "success"\n'
        '            emoji: "✅"\n'
        '        select "role_select":\n'
        '            placeholder: "Select your team..."\n'
        '            min_values: 1\n'
        '            max_values: 2\n'
        '            option "dev":\n'
        '                label: "Developer"\n'
        '                description: "Codes features"\n'
        '                emoji: "💻"\n'
        '            option "design":\n'
        '                label: "Designer"\n'
    )
    tokens = Lexer(code).tokenize()
    program = Parser(tokens).parse()
    cmd = program.statements[0]
    reply_stmt = cmd.body.statements[0]

    assert reply_stmt.components is not None
    assert len(reply_stmt.components.items) == 2

    # Button check
    btn = reply_stmt.components.items[0]
    assert btn.custom_id.value == "verify_btn"
    assert btn.label.value == "Verify Me"
    assert btn.style.value == "success"
    assert btn.emoji.value == "✅"

    # Select check
    sel = reply_stmt.components.items[1]
    assert sel.custom_id.value == "role_select"
    assert sel.placeholder.value == "Select your team..."
    assert len(sel.options) == 2
    assert sel.options[0].value.value == "dev"
    assert sel.options[0].label.value == "Developer"
    assert sel.options[1].value.value == "design"


def test_parser_when_component_events():
    code = (
        'when button "verify_btn" is clicked:\n'
        '    reply "Verified!"\n'
        'when select "role_select" is chosen:\n'
        '    reply "Role selected!"\n'
    )
    tokens = Lexer(code).tokenize()
    program = Parser(tokens).parse()
    assert len(program.statements) == 2
    evt1, evt2 = program.statements[0], program.statements[1]

    assert evt1.event_name == "button_verify_btn"
    assert evt2.event_name == "select_role_select"


def test_button_execution_and_click_event():
    async def _run():
        code = (
            'command prompt_verify:\n'
            '    reply "Click to verify!" with:\n'
            '        button "verify_btn":\n'
            '            label: "Verify"\n'
            '            style: "success"\n'
            '\n'
            'when button "verify_btn" is clicked:\n'
            '    reply "Welcome {author.name}! You are verified."\n'
        )
        interpreter = Interpreter()
        adapter = MockDiscordAdapter(interpreter)
        tokens = Lexer(code).tokenize()
        program = Parser(tokens).parse()

        await interpreter.execute_program(program, ctx=adapter)
        assert "prompt_verify" in adapter.registered_commands
        assert "button_verify_btn" in interpreter.events

        # 1. Trigger the command to send the button
        await adapter.dispatch_prefix_command("!prompt_verify")
        assert len(adapter.sent_messages) == 1
        sent = adapter.sent_messages[0]
        assert sent["action"] == "reply"
        assert sent["content"] == "Click to verify!"
        assert sent["view"] is not None
        assert len(sent["view"].items) == 1
        btn = sent["view"].items[0]
        assert isinstance(btn, CordButton)
        assert btn.custom_id == "verify_btn"
        assert btn.label == "Verify"
        assert btn.style == "success"

        # 2. Simulate user clicking the button
        await adapter.click_button("verify_btn")
        assert len(adapter.sent_messages) == 2
        click_reply = adapter.sent_messages[1]
        assert click_reply["action"] == "reply"
        assert "You are verified." in click_reply["content"]
        assert "TestUser" in click_reply["content"]

    asyncio.run(_run())


def test_select_menu_execution_and_selection_event():
    async def _run():
        code = (
            'command choose_team:\n'
            '    reply "Select team:" with:\n'
            '        select "team_picker":\n'
            '            placeholder: "Pick one"\n'
            '            option "red":\n'
            '                label: "Red Team"\n'
            '            option "blue":\n'
            '                label: "Blue Team"\n'
            '\n'
            'when select "team_picker" is chosen:\n'
            '    reply "You picked {selected}!"\n'
        )
        interpreter = Interpreter()
        adapter = MockDiscordAdapter(interpreter)
        tokens = Lexer(code).tokenize()
        program = Parser(tokens).parse()

        await interpreter.execute_program(program, ctx=adapter)
        assert "choose_team" in adapter.registered_commands
        assert "select_team_picker" in interpreter.events

        # 1. Trigger command
        await adapter.dispatch_prefix_command("!choose_team")
        assert len(adapter.sent_messages) == 1
        sent = adapter.sent_messages[0]
        assert sent["view"] is not None
        sel = sent["view"].items[0]
        assert isinstance(sel, CordSelect)
        assert sel.custom_id == "team_picker"
        assert len(sel.options) == 2

        # 2. Simulate user making a selection
        await adapter.choose_select("team_picker", ["blue"])
        assert len(adapter.sent_messages) == 2
        choose_reply = adapter.sent_messages[1]
        assert choose_reply["content"] == "You picked blue!"

    asyncio.run(_run())


def test_discord_view_conversion():
    interpreter = Interpreter()
    adapter = DiscordAdapter(interpreter, token="dummy_token_for_offline_test")

    cord_view = CordView([
        CordButton(custom_id="btn_test", label="Test", style="danger", emoji="⚠️"),
        CordSelect(
            custom_id="sel_test",
            placeholder="Choose...",
            options=[CordSelectOption(value="v1", label="L1")]
        )
    ])
    discord_view = adapter._to_discord_view(cord_view)
    assert discord_view is not None
    assert len(discord_view.children) == 2
