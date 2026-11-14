"""
Tests for the Cord Interpreter and Execution Engine.
"""

import pytest
import asyncio
from cord.lexer import Lexer
from cord.parser import Parser
from cord.interpreter import Interpreter
from cord.runtime import ExecutionContext, CordMember, CordChannel, CordEmbed
from cord.storage import Store


def run_code(code: str, ctx: ExecutionContext = None, store: Store = None):
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    program = parser.parse()

    interp = Interpreter(store=store)
    asyncio.run(interp.execute_program(program, ctx=ctx))
    return interp


def test_basic_evaluation():
    code = (
        "x = 10 + 5 * 2\n"
        "name = 'Cord'\n"
        "greeting = 'Hello {name}!'\n"
        "is_cool = true and not false\n"
    )
    interp = run_code(code)
    assert interp.global_env.get("x") == 20
    assert interp.global_env.get("greeting") == "Hello Cord!"
    assert interp.global_env.get("is_cool") is True


def test_data_structures():
    code = (
        "nums = [1, 2, 3]\n"
        "nums.append(4)\n"
        "person = {'name': 'Alice', 'role': 'Admin'}\n"
        "person.name = 'Bob'\n"
    )
    interp = run_code(code)
    assert interp.global_env.get("nums") == [1, 2, 3, 4]
    assert interp.global_env.get("person")["name"] == "Bob"


def test_functions_and_recursion():
    code = (
        "fn factorial(n):\n"
        "    if n <= 1:\n"
        "        return 1\n"
        "    return n * factorial(n - 1)\n"
        "\n"
        "res = factorial(5)\n"
    )
    interp = run_code(code)
    assert interp.global_env.get("res") == 120


def test_loops():
    code = (
        "total = 0\n"
        "for i in [1, 2, 3, 4, 5]:\n"
        "    total += i\n"
        "\n"
        "count = 0\n"
        "while count < 3:\n"
        "    count += 1\n"
    )
    interp = run_code(code)
    assert interp.global_env.get("total") == 15
    assert interp.global_env.get("count") == 3


def test_persistent_store():
    store = Store(db_path=":memory:")
    code1 = (
        "store.counter = 10\n"
        "store.users = {'alice': 100}\n"
        "store.users.alice += 50\n"
    )
    run_code(code1, store=store)
    assert store.counter == 10
    assert store.users["alice"] == 150


def test_command_reply_and_permissions():
    author_mod = CordMember(member_id=1, name="AdminUser", permissions=["moderate_members"])
    author_normal = CordMember(member_id=2, name="RegularUser", permissions=[])
    channel = CordChannel(channel_id=10, name="general")

    code = (
        "command ban_user:\n"
        "    require permission moderate_members\n"
        "    reply 'User banned by {author.name}'\n"
    )

    interp = Interpreter()
    lexer = Lexer(code)
    prog = Parser(lexer.tokenize()).parse()
    asyncio.run(interp.execute_program(prog))

    cmd = interp.commands["ban_user"]

    # Test with moderator: should succeed
    ctx_mod = ExecutionContext(bot_adapter=None, author=author_mod, channel=channel)
    setattr(ctx_mod, "command_name", "ban_user")
    asyncio.run(interp.execute_command(cmd, ctx_mod))
    assert len(ctx_mod.replies) == 1
    assert "User banned by AdminUser" in ctx_mod.replies[0]["content"]

    # Test with normal user: should be rejected by require permission
    ctx_normal = ExecutionContext(bot_adapter=None, author=author_normal, channel=channel)
    setattr(ctx_normal, "command_name", "ban_user")
    asyncio.run(interp.execute_command(cmd, ctx_normal))
    assert len(ctx_normal.replies) == 1
    assert "do not have the required permission" in ctx_normal.replies[0]["content"]


def test_embed_generation():
    author = CordMember(member_id=1, name="Author")
    channel = CordChannel(channel_id=10, name="bot-commands")
    ctx = ExecutionContext(bot_adapter=None, author=author, channel=channel)

    code = (
        "command stats:\n"
        "    reply embed:\n"
        "        title 'Statistics'\n"
        "        description 'Bot health metrics'\n"
        "        color '#00FF00'\n"
        "        field 'Latency' '20ms' inline=true\n"
        "        field 'Guilds' 12 inline=true\n"
    )

    interp = Interpreter()
    lexer = Lexer(code)
    prog = Parser(lexer.tokenize()).parse()
    asyncio.run(interp.execute_program(prog))

    cmd = interp.commands["stats"]
    asyncio.run(interp.execute_command(cmd, ctx))

    assert len(ctx.replies) == 1
    embed = ctx.replies[0]["embed"]
    assert isinstance(embed, CordEmbed)
    assert embed.title == "Statistics"
    assert embed.description == "Bot health metrics"
    assert embed.color == "#00FF00"
    assert len(embed.fields) == 2
    assert embed.fields[0]["name"] == "Latency"
    assert embed.fields[0]["value"] == "20ms"


def test_if_block_scoping():
    code = (
        "fn decide(flag):\n"
        "    if flag:\n"
        "        msg = 'yes'\n"
        "    else:\n"
        "        msg = 'no'\n"
        "    return msg\n"
        "\n"
        "res_yes = decide(true)\n"
        "res_no = decide(false)\n"
    )
    interp = run_code(code)
    assert interp.global_env.get("res_yes") == "yes"
    assert interp.global_env.get("res_no") == "no"


def test_dict_and_store_methods():
    store = Store(db_path=":memory:")
    code = (
        "fn check_bal(uid):\n"
        "    if not store.has('balances'):\n"
        "        store.balances = {}\n"
        "    return store.balances.get(uid, 100)\n"
        "\n"
        "val = check_bal('user1')\n"
        "store.balances['user1'] = 250\n"
        "val_updated = check_bal('user1')\n"
    )
    interp = run_code(code, store=store)
    assert interp.global_env.get("val") == 100
    assert interp.global_env.get("val_updated") == 250


def test_numeric_coercion_and_string_plus():
    code = (
        "raw_id = '100'\n"
        "rolled = (raw_id % 6) + 1\n"
        "msg = 'Count: ' + 5\n"
    )
    interp = run_code(code)
    assert interp.global_env.get("rolled") == 5
    assert interp.global_env.get("msg") == "Count: 5"
