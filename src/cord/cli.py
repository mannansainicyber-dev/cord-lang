"""
Command-Line Interface for the Cord Programming Language.
Commands:
    cord run <file.cord>   : Runs a Cord bot file
    cord check <file.cord> : Validates syntax and static structure without running
    cord fmt <file.cord>   : Formats a Cord source file
    cord init [name]       : Scaffolds a new starter Cord bot project
    cord --version         : Displays version and environment information
"""

import sys
import os
import argparse
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from cord import __version__
from cord.lexer import Lexer, LexerError
from cord.parser import Parser, ParserError
from cord.interpreter import Interpreter
from cord.discord_adapter import DiscordAdapter, MockDiscordAdapter
from cord.storage import Store


def print_error(msg: str):
    sys.stderr.write(f"\033[91m{msg}\033[0m\n")


def print_success(msg: str):
    sys.stdout.write(f"\033[92m{msg}\033[0m\n")


def print_info(msg: str):
    sys.stdout.write(f"\033[94m{msg}\033[0m\n")


def format_error_snippet(source: str, line: int, col: int, message: str, hint: Optional[str] = None) -> str:
    lines = source.splitlines()
    snippet_lines = []
    snippet_lines.append(f"\033[91mError: {message}\033[0m")

    if 1 <= line <= len(lines):
        target_line = lines[line - 1]
        snippet_lines.append(f"  --> Line {line}, Column {col}")
        snippet_lines.append(f"   |")
        snippet_lines.append(f"{line:2d} | {target_line}")
        pointer = " " * (col - 1) + "^"
        snippet_lines.append(f"   | \033[91m{pointer}\033[0m")

    if hint:
        snippet_lines.append(f"\n\033[93m💡 Hint: {hint}\033[0m")

    return "\n".join(snippet_lines)


def cmd_check(args: argparse.Namespace) -> int:
    files = args.files if isinstance(args.files, list) else [args.files]
    exit_code = 0

    for filepath in files:
        if not os.path.isfile(filepath):
            print_error(f"Error: File '{filepath}' does not exist.")
            exit_code = 1
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                source = f.read()

            lexer = Lexer(source, filename=filepath)
            tokens = lexer.tokenize()
            parser = Parser(tokens, filename=filepath)
            program = parser.parse()

            print_success(f"✓ '{filepath}' passed validation: 0 errors found.")
            print_info(f"  - Statements: {len(program.statements)}")

        except (LexerError, ParserError) as e:
            hint = getattr(e, "hint", None)
            err_output = format_error_snippet(source, e.line, e.col, e.message, hint)
            print_error(err_output)
            exit_code = 1
        except Exception as e:
            print_error(f"Validation error in '{filepath}': {e}")
            exit_code = 1

    return exit_code


def cmd_run(args: argparse.Namespace) -> int:
    filepath = args.file
    if not os.path.isfile(filepath):
        print_error(f"Error: File '{filepath}' does not exist.")
        return 1

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()

        lexer = Lexer(source, filename=filepath)
        tokens = lexer.tokenize()
        parser = Parser(tokens, filename=filepath)
        program = parser.parse()

    except (LexerError, ParserError) as e:
        hint = getattr(e, "hint", None)
        print_error(format_error_snippet(source, e.line, e.col, e.message, hint))
        return 1

    # Check for Discord token
    token = os.getenv("DISCORD_TOKEN")
    if not token or token.strip() in ("", "YOUR_BOT_TOKEN_HERE"):
        print_error(
            "Error: Discord bot token is missing!\n"
            "Please create a .env file in this directory with:\n"
            "    DISCORD_TOKEN=your_actual_token_here\n"
            "or set the DISCORD_TOKEN environment variable."
        )
        return 1

    try:
        db_path = getattr(args, "db", "cord_store.db")
        store = Store(db_path=db_path)
        interpreter = Interpreter(store=store)
        adapter = DiscordAdapter(interpreter, token=token)

        # Run top-level script
        import asyncio
        asyncio.run(interpreter.execute_program(program, ctx=adapter))

        print_info(f"Starting {interpreter.bot_name}...")
        adapter.start()
        return 0
    except Exception as e:
        print_error(f"Failed to start bot: {e}")
        return 1


def cmd_fmt(args: argparse.Namespace) -> int:
    files = args.files if isinstance(args.files, list) else [args.files]
    exit_code = 0

    for filepath in files:
        if not os.path.isfile(filepath):
            print_error(f"Error: File '{filepath}' does not exist.")
            exit_code = 1
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()

            formatted_lines = []
            for line in lines:
                rstripped = line.rstrip()
                if not rstripped:
                    formatted_lines.append("\n")
                else:
                    formatted_lines.append(rstripped + "\n")

            formatted_code = "".join(formatted_lines)
            if not formatted_code.endswith("\n"):
                formatted_code += "\n"

            if args.write:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(formatted_code)
                print_success(f"✓ Formatted and updated '{filepath}'.")
            else:
                sys.stdout.write(formatted_code)

        except Exception as e:
            print_error(f"Formatting failed for '{filepath}': {e}")
            exit_code = 1

    return exit_code


def cmd_init(args: argparse.Namespace) -> int:
    project_name = args.name or "my-cord-bot"
    if os.path.exists(project_name):
        print_error(f"Error: Directory or file '{project_name}' already exists.")
        return 1

    os.makedirs(project_name, exist_ok=True)

    # 1. bot.cord
    starter_cord = (
        'bot "HelperBot"\n'
        '\n'
        'config:\n'
        '    prefix = "!"\n'
        '    status = "online"\n'
        '    activity = "with Cord"\n'
        '\n'
        'when someone joins:\n'
        '    send #welcome "Welcome to the server, {member.name}!"\n'
        '\n'
        'command ping:\n'
        '    reply "Pong! Latency: {bot.latency}ms"\n'
        '\n'
        'command greet(target: Member = null):\n'
        '    user = target or author\n'
        '    reply "Hello, {user.mention}!"\n'
    )
    with open(os.path.join(project_name, "bot.cord"), "w", encoding="utf-8") as f:
        f.write(starter_cord)

    # 2. .env.example
    env_example = (
        "# Discord Bot Token (from Discord Developer Portal)\n"
        "DISCORD_TOKEN=YOUR_BOT_TOKEN_HERE\n"
    )
    with open(os.path.join(project_name, ".env.example"), "w", encoding="utf-8") as f:
        f.write(env_example)

    # 3. .gitignore
    gitignore = (
        ".env\n"
        "*.db\n"
        "__pycache__/\n"
    )
    with open(os.path.join(project_name, ".gitignore"), "w", encoding="utf-8") as f:
        f.write(gitignore)

    # 4. README.md
    readme = (
        f"# {project_name}\n\n"
        "A Discord bot powered by the **Cord** programming language.\n\n"
        "## Setup\n\n"
        "1. Copy `.env.example` to `.env`:\n"
        "   ```bash\n"
        "   cp .env.example .env\n"
        "   ```\n"
        "2. Add your Discord bot token to `.env`.\n"
        "3. Run the bot:\n"
        "   ```bash\n"
        "   cord run bot.cord\n"
        "   ```\n"
    )
    with open(os.path.join(project_name, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme)

    print_success(f"✓ Created new Cord project in '{project_name}'!")
    print_info(f"Next steps:\n  cd {project_name}\n  cp .env.example .env\n  cord run bot.cord")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="cord",
        description="Cord: The expressive programming language designed for Discord bots."
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"Cord {__version__} (Python {sys.version.split()[0]})"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # cord run <file>
    run_parser = subparsers.add_parser("run", help="Run a Cord bot file")
    run_parser.add_argument("file", help="Path to .cord file")
    run_parser.add_argument("--db", default="cord_store.db", help="Path to SQLite persistence database")

    # cord check <file> ...
    check_parser = subparsers.add_parser("check", help="Verify syntax and structure of Cord files")
    check_parser.add_argument("files", nargs="+", help="Path to one or more .cord files")

    # cord fmt <file> ...
    fmt_parser = subparsers.add_parser("fmt", help="Format Cord source files")
    fmt_parser.add_argument("files", nargs="+", help="Path to one or more .cord files")
    fmt_parser.add_argument("-w", "--write", action="store_true", help="Write formatted code directly to files")

    # cord init [name]
    init_parser = subparsers.add_parser("init", help="Initialize a new Cord project")
    init_parser.add_argument("name", nargs="?", default="my-cord-bot", help="Name of project directory")

    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "run":
        return cmd_run(args)
    elif args.command == "check":
        return cmd_check(args)
    elif args.command == "fmt":
        return cmd_fmt(args)
    elif args.command == "init":
        return cmd_init(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
