"""
Tests for the Cord Lexer.
"""

import pytest
from cord.lexer import Lexer, TokenType, LexerError


def test_lex_basic_tokens():
    code = 'bot "TestBot"\nx = 42\ny = 3.14'
    lexer = Lexer(code)
    tokens = lexer.tokenize()

    types = [t.type for t in tokens]
    assert types == [
        TokenType.BOT, TokenType.STRING, TokenType.NEWLINE,
        TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.INT, TokenType.NEWLINE,
        TokenType.IDENTIFIER, TokenType.ASSIGN, TokenType.FLOAT, TokenType.NEWLINE,
        TokenType.EOF
    ]
    assert tokens[1].value == "TestBot"
    assert tokens[5].value == 42
    assert tokens[9].value == 3.14


def test_lex_indentation():
    code = (
        "command ping:\n"
        "    reply \"Pong!\"\n"
        "    x = 1\n"
        "bot \"Done\"\n"
    )
    lexer = Lexer(code)
    tokens = lexer.tokenize()

    types = [t.type for t in tokens]
    assert TokenType.INDENT in types
    assert TokenType.DEDENT in types

    # Check order: COMMAND, IDENTIFIER, COLON, NEWLINE, INDENT, REPLY, STRING, NEWLINE, ... DEDENT, BOT, STRING
    assert tokens[0].type == TokenType.COMMAND
    assert tokens[1].value == "ping"
    assert tokens[2].type == TokenType.COLON
    assert tokens[3].type == TokenType.NEWLINE
    assert tokens[4].type == TokenType.INDENT
    assert tokens[5].type == TokenType.REPLY
    assert tokens[6].value == "Pong!"


def test_lex_durations():
    code = "5s 30m 2h 1d 500ms"
    lexer = Lexer(code)
    tokens = [t for t in lexer.tokenize() if t.type == TokenType.DURATION]

    assert len(tokens) == 5
    assert tokens[0].value == 5.0
    assert tokens[1].value == 1800.0
    assert tokens[2].value == 7200.0
    assert tokens[3].value == 86400.0
    assert tokens[4].value == 0.5


def test_lex_channel_references():
    code = "send #welcome \"Hello\""
    lexer = Lexer(code)
    tokens = lexer.tokenize()

    types = [t.type for t in tokens]
    assert TokenType.CHANNEL_REF in types
    channel_tok = [t for t in tokens if t.type == TokenType.CHANNEL_REF][0]
    assert channel_tok.value == "welcome"


def test_lex_operators():
    code = "+ - * / % += -= *= /= == != < <= > >= and or not"
    lexer = Lexer(code)
    tokens = [t.type for t in lexer.tokenize() if t.type != TokenType.NEWLINE and t.type != TokenType.EOF]

    expected = [
        TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH_OP, TokenType.PERCENT,
        TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN, TokenType.STAR_ASSIGN, TokenType.SLASH_ASSIGN,
        TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.LTE, TokenType.GT, TokenType.GTE,
        TokenType.AND, TokenType.OR, TokenType.NOT
    ]
    assert tokens == expected


def test_lex_unterminated_string_error():
    code = 'reply "Unterminated string'
    lexer = Lexer(code)
    with pytest.raises(LexerError) as exc_info:
        lexer.tokenize()
    assert "Unterminated string" in str(exc_info.value)


def test_lex_inconsistent_indentation():
    code = (
        "if true:\n"
        "    x = 1\n"
        "  y = 2\n"
    )
    lexer = Lexer(code)
    with pytest.raises(LexerError) as exc_info:
        lexer.tokenize()
    assert "Inconsistent indentation" in str(exc_info.value)
