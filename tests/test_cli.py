"""
Tests for the Cord CLI tool.
"""

import os
import pytest
from cord.cli import main


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "Cord 0.2.0" in captured.out


def test_cli_check_valid(tmp_path):
    cord_file = tmp_path / "valid.cord"
    cord_file.write_text(
        'bot "TestBot"\n'
        'command ping:\n'
        '    reply "Pong!"\n'
    )
    code = main(["check", str(cord_file)])
    assert code == 0


def test_cli_check_syntax_error(tmp_path, capsys):
    cord_file = tmp_path / "invalid.cord"
    cord_file.write_text(
        'command ping\n'
        '    reply "Missing colon"\n'
    )
    code = main(["check", str(cord_file)])
    assert code == 1
    captured = capsys.readouterr()
    assert "Expected ':'" in captured.err


def test_cli_init_project(tmp_path):
    target_dir = tmp_path / "test-bot"
    code = main(["init", str(target_dir)])
    assert code == 0

    assert (target_dir / "bot.cord").is_file()
    assert (target_dir / ".env.example").is_file()
    assert (target_dir / ".gitignore").is_file()
    assert (target_dir / "README.md").is_file()


def test_cli_fmt(tmp_path, capsys):
    cord_file = tmp_path / "messy.cord"
    cord_file.write_text(
        'bot "Test"   \n\n'
        'command ping:  \n'
        '    reply "Pong"   \n'
    )
    code = main(["fmt", "-w", str(cord_file)])
    assert code == 0

    formatted = cord_file.read_text()
    assert "   \n" not in formatted


def test_cli_run_missing_token(tmp_path, monkeypatch, capsys):
    cord_file = tmp_path / "bot.cord"
    cord_file.write_text(
        'bot "Test"\n'
        'command ping:\n'
        '    reply "Pong!"\n'
    )
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    code = main(["run", str(cord_file)])
    assert code == 1
    captured = capsys.readouterr()
    assert "Discord bot token is missing" in captured.err


def test_cli_docker_scaffold(tmp_path):
    bot_file = tmp_path / "bot.cord"
    bot_file.write_text('bot "DockerBot"\n')
    code = main(["docker", "-o", str(tmp_path)])
    assert code == 0

    assert (tmp_path / "Dockerfile").is_file()
    assert (tmp_path / "docker-compose.yml").is_file()
    assert (tmp_path / ".dockerignore").is_file()

    df_content = (tmp_path / "Dockerfile").read_text()
    assert '"cord", "run", "bot.cord"' in df_content
    compose_content = (tmp_path / "docker-compose.yml").read_text()
    assert 'restart: unless-stopped' in compose_content


def test_cli_repl_exit(monkeypatch, capsys):
    inputs = iter([".exit"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    code = main(["repl"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Interactive REPL" in captured.out
    assert "Goodbye!" in captured.out
