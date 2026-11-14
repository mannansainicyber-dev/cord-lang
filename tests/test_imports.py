import asyncio
import os
import pytest
from cord.lexer import Lexer
from cord.parser import Parser
from cord.interpreter import Interpreter
from cord.discord_adapter import MockDiscordAdapter
from cord.ast_nodes import ImportStmt


def test_parser_import_statement():
    code = (
        'import "commands/admin.cord"\n'
        'import utils as u\n'
    )
    tokens = Lexer(code).tokenize()
    program = Parser(tokens).parse()
    assert len(program.statements) == 2
    s1, s2 = program.statements[0], program.statements[1]

    assert isinstance(s1, ImportStmt)
    assert s1.module_path == "commands/admin.cord"
    assert s1.alias is None

    assert isinstance(s2, ImportStmt)
    assert s2.module_path == "utils"
    assert s2.alias == "u"


def test_multi_file_execution(tmp_path):
    # 1. Create a helper module
    utils_file = tmp_path / "helpers.cord"
    utils_file.write_text(
        'fn calc_bonus(points):\n'
        '    return points * 2\n'
        '\n'
        'multiplier = 10\n'
    )

    # 2. Create a commands module
    cmds_file = tmp_path / "sub_cmds.cord"
    cmds_file.write_text(
        'command bonus(target: Member):\n'
        '    b = calc_bonus(multiplier)\n'
        '    reply "Awarded {b} bonus to {target.name}!"\n'
    )

    # 3. Create main bot file
    main_file = tmp_path / "main.cord"
    main_file.write_text(
        'bot "ModularBot"\n'
        'import "helpers.cord"\n'
        'import "sub_cmds.cord"\n'
    )

    async def _run():
        interpreter = Interpreter()
        adapter = MockDiscordAdapter(interpreter)

        with open(main_file, "r") as f:
            source = f.read()
        tokens = Lexer(source, filename=str(main_file)).tokenize()
        program = Parser(tokens, filename=str(main_file)).parse()

        await interpreter.execute_program(program, ctx=adapter, filename=str(main_file))

        assert "bonus" in adapter.registered_commands
        await adapter.dispatch_prefix_command("!bonus <@100>")

        assert len(adapter.sent_messages) == 1
        assert "Awarded 20 bonus to TestUser!" in adapter.sent_messages[0]["content"]

    asyncio.run(_run())


def test_circular_import_safety(tmp_path):
    file_a = tmp_path / "mod_a.cord"
    file_b = tmp_path / "mod_b.cord"

    file_a.write_text(
        f'import "{file_b.name}"\n'
        'a_val = 1\n'
    )
    file_b.write_text(
        f'import "{file_a.name}"\n'
        'b_val = 2\n'
    )

    async def _run():
        interpreter = Interpreter()
        adapter = MockDiscordAdapter(interpreter)

        with open(file_a, "r") as f:
            source = f.read()
        tokens = Lexer(source, filename=str(file_a)).tokenize()
        program = Parser(tokens, filename=str(file_a)).parse()

        # Should terminate cleanly without recursion error
        await interpreter.execute_program(program, ctx=adapter, filename=str(file_a))
        assert interpreter.global_env.has("a_val")

    asyncio.run(_run())


def test_aliased_import_module_proxy(tmp_path):
    math_file = tmp_path / "my_math.cord"
    math_file.write_text(
        'fn square(n):\n'
        '    return n * n\n'
        'version = "1.0"\n'
    )

    main_file = tmp_path / "main.cord"
    main_file.write_text(
        'import "my_math.cord" as calc\n'
        'command compute:\n'
        '    res = calc.square(6)\n'
        '    reply "Square is {res}, ver {calc.version}"\n'
    )

    async def _run():
        interpreter = Interpreter()
        adapter = MockDiscordAdapter(interpreter)

        with open(main_file, "r") as f:
            source = f.read()
        tokens = Lexer(source, filename=str(main_file)).tokenize()
        program = Parser(tokens, filename=str(main_file)).parse()

        await interpreter.execute_program(program, ctx=adapter, filename=str(main_file))
        await adapter.dispatch_prefix_command("!compute")

        assert len(adapter.sent_messages) == 1
        assert adapter.sent_messages[0]["content"] == "Square is 36, ver 1.0"

    asyncio.run(_run())
