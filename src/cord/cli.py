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

    # Load environment variables (.env)
    try:
        from dotenv import load_dotenv
        custom_env = getattr(args, "env", None)
        if custom_env and os.path.isfile(custom_env):
            load_dotenv(dotenv_path=custom_env, override=True)
        else:
            # 1. Check current working directory
            cwd_env = os.path.join(os.getcwd(), ".env")
            if os.path.isfile(cwd_env):
                load_dotenv(dotenv_path=cwd_env, override=True)

            # 2. Check script directory
            script_dir = os.path.dirname(os.path.abspath(filepath))
            script_env = os.path.join(script_dir, ".env")
            if os.path.isfile(script_env) and script_dir != os.getcwd():
                load_dotenv(dotenv_path=script_env, override=False)
    except ImportError:
        pass

    # Check for Discord token
    token = getattr(args, "token", None) or os.getenv("DISCORD_TOKEN")
    if token:
        token = token.strip().strip("'\"")

    if not token or token in ("", "YOUR_BOT_TOKEN_HERE"):
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
        asyncio.run(interpreter.execute_program(program, ctx=adapter, filename=filepath))

        print_info(f"Starting {interpreter.bot_name}...")
        adapter.start()
        return 0
    except KeyboardInterrupt:
        print_info("\nBot stopped by user.")
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


def cmd_repl(args: argparse.Namespace) -> int:
    try:
        import readline
    except ImportError:
        pass

    import asyncio
    db_path = getattr(args, "db", ":memory:")
    store = Store(db_path=db_path)
    interpreter = Interpreter(store=store)

    print_info(f"Cord {__version__} Interactive REPL")
    print("Type '.help' for commands, '.exit' or Ctrl+D to exit.\n")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    buffer = []
    in_block = False

    while True:
        try:
            prompt = "... " if in_block else "cord> "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nExiting Cord REPL.")
            break

        stripped = line.strip()
        if not in_block:
            if stripped in (".exit", "exit", "quit", ".quit"):
                print("Goodbye!")
                break
            elif stripped in (".help", "help"):
                print("Cord REPL Help:")
                print("  Type any Cord expression (e.g. 2 + 2, fetch('https://...')) or statement")
                print("  .exit / exit    - Exit REPL")
                print("  .clear / clear  - Clear terminal")
                print("  .env            - List defined variables in global scope")
                print("  .help           - Show this help message\n")
                continue
            elif stripped in (".clear", "clear"):
                os.system("clear" if os.name != "nt" else "cls")
                continue
            elif stripped == ".env":
                print("Defined variables:")
                for k, v in interpreter.global_env.values.items():
                    print(f"  {k} = {v}")
                print()
                continue

        if line.endswith(":") or (in_block and line.startswith("    ")):
            in_block = True
            buffer.append(line)
            continue
        elif in_block and not stripped:
            in_block = False
            code = "\n".join(buffer)
            buffer = []
        elif in_block:
            buffer.append(line)
            continue
        else:
            code = line

        if not code.strip():
            continue

        try:
            tokens = Lexer(code).tokenize()
            parser = Parser(tokens)
            try:
                expr_node = parser.parse_expression()
                val = loop.run_until_complete(interpreter.eval_expr(expr_node, interpreter.global_env, None))
                if val is not None:
                    print(f"\033[92m=>\033[0m {repr(val)}")
                continue
            except Exception:
                pass

            tokens = Lexer(code).tokenize()
            prog = Parser(tokens).parse()
            loop.run_until_complete(interpreter.execute_program(prog, None))
        except LexerError as e:
            print_error(f"Syntax Error: {e}")
        except ParserError as e:
            print_error(f"Parse Error: {e}")
        except Exception as e:
            print_error(f"Error: {e}")

    return 0


def cmd_docker(args: argparse.Namespace) -> int:
    out_dir = getattr(args, "output", ".")
    entrypoint = getattr(args, "entry", None)

    if not entrypoint:
        if os.path.isdir(out_dir):
            cord_files = [f for f in os.listdir(out_dir) if f.endswith(".cord")]
            if "bot.cord" in cord_files:
                entrypoint = "bot.cord"
            elif "main.cord" in cord_files:
                entrypoint = "main.cord"
            elif cord_files:
                entrypoint = cord_files[0]
            else:
                entrypoint = "bot.cord"
        else:
            entrypoint = "bot.cord"

    dockerfile_content = (
        "# Generated by Cord CLI (cord docker)\n"
        "FROM python:3.12-slim\n\n"
        "WORKDIR /app\n\n"
        "ENV PYTHONUNBUFFERED=1 \\\n"
        "    PYTHONDONTWRITEBYTECODE=1\n\n"
        "RUN apt-get update && apt-get install -y --no-install-recommends \\\n"
        "    gcc \\\n"
        "    && rm -rf /var/lib/apt/lists/*\n\n"
        "RUN pip install --no-cache-dir cord-lang\n\n"
        "COPY . /app\n\n"
        f'CMD ["cord", "run", "{entrypoint}"]\n'
    )

    docker_compose_content = (
        "# Generated by Cord CLI (cord docker)\n"
        "version: '3.8'\n\n"
        "services:\n"
        "  bot:\n"
        "    build: .\n"
        "    restart: unless-stopped\n"
        "    env_file:\n"
        "      - .env\n"
        "    volumes:\n"
        "      - ./cord_store.db:/app/cord_store.db\n"
    )

    dockerignore_content = (
        ".git\n"
        "__pycache__/\n"
        "*.pyc\n"
        ".env\n"
        ".venv\n"
        "venv/\n"
    )

    dockerfile_path = os.path.join(out_dir, "Dockerfile")
    compose_path = os.path.join(out_dir, "docker-compose.yml")
    dockerignore_path = os.path.join(out_dir, ".dockerignore")

    with open(dockerfile_path, "w", encoding="utf-8") as f:
        f.write(dockerfile_content)

    with open(compose_path, "w", encoding="utf-8") as f:
        f.write(docker_compose_content)

    with open(dockerignore_path, "w", encoding="utf-8") as f:
        f.write(dockerignore_content)

    print_success("✓ Docker scaffolding complete:")
    print_info(f"  - {dockerfile_path}")
    print_info(f"  - {compose_path}")
    print_info(f"  - {dockerignore_path}")
    print_info(f"\nTo build and run in Docker:\n  docker compose up -d --build")
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
    run_parser.add_argument("--token", help="Discord bot token override")
    run_parser.add_argument("--env", help="Path to custom .env configuration file")

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

    # cord repl
    repl_parser = subparsers.add_parser("repl", help="Start an interactive Cord REPL session")
    repl_parser.add_argument("--db", default=":memory:", help="Database for store in REPL")

    # cord docker
    docker_parser = subparsers.add_parser("docker", help="Generate production Dockerfile and docker-compose.yml")
    docker_parser.add_argument("--entry", help="Main entrypoint .cord file")
    docker_parser.add_argument("-o", "--output", default=".", help="Output directory")

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
    elif args.command == "repl":
        return cmd_repl(args)
    elif args.command == "docker":
        return cmd_docker(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
