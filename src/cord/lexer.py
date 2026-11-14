"""
Lexer (Tokenizer) for the Cord programming language.
Handles Python-style indentation, durations, channel references, and keywords.
"""

from enum import Enum, auto
from typing import List, Optional, Any, NamedTuple


class TokenType(Enum):
    # End of File & Structure
    EOF = auto()
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()

    # Literals
    IDENTIFIER = auto()
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    DURATION = auto()
    CHANNEL_REF = auto()  # #general, #welcome

    # Keywords - Declarations
    BOT = auto()
    CONFIG = auto()
    COMMAND = auto()
    SLASH = auto()
    PREFIX = auto()
    BOTH = auto()
    MODE = auto()
    WHEN = auto()
    EVENT = auto()
    TASK = auto()
    EVERY = auto()
    FN = auto()

    # Keywords - Control Flow
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    IN = auto()
    RETURN = auto()
    PASS = auto()

    # Keywords - Discord Actions & Guards
    REPLY = auto()
    SEND = auto()
    DELETE = auto()
    REQUIRE = auto()
    PERMISSION = auto()
    COOLDOWN = auto()
    PER = auto()
    ASK = auto()
    TIMEOUT = auto()

    # Keywords - UI Components
    WITH = auto()
    BUTTON = auto()
    SELECT = auto()
    OPTION = auto()

    # Keywords - Embeds
    EMBED = auto()
    TITLE = auto()
    DESCRIPTION = auto()
    COLOR = auto()
    THUMBNAIL = auto()
    IMAGE = auto()
    FOOTER = auto()
    FIELD = auto()
    INLINE = auto()

    # Operators & Logic
    PLUS = auto()         # +
    MINUS = auto()        # -
    STAR = auto()         # *
    SLASH_OP = auto()     # /
    PERCENT = auto()      # %
    ASSIGN = auto()       # =
    PLUS_ASSIGN = auto()  # +=
    MINUS_ASSIGN = auto() # -=
    STAR_ASSIGN = auto()  # *=
    SLASH_ASSIGN = auto() # /=
    EQ = auto()           # ==
    NEQ = auto()          # !=
    LT = auto()           # <
    LTE = auto()          # <=
    GT = auto()           # >
    GTE = auto()          # >=
    AND = auto()
    OR = auto()
    NOT = auto()

    # Constants
    TRUE = auto()
    FALSE = auto()
    NULL = auto()

    # Delimiters
    LPAREN = auto()       # (
    RPAREN = auto()       # )
    LBRACKET = auto()     # [
    RBRACKET = auto()     # ]
    LBRACE = auto()       # {
    RBRACE = auto()       # }
    COLON = auto()        # :
    COMMA = auto()        # ,
    DOT = auto()          # .


class Token(NamedTuple):
    type: TokenType
    value: Any
    line: int
    col: int
    raw: str = ""

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {repr(self.value)}, L{self.line}:C{self.col})"


KEYWORDS = {
    "bot": TokenType.BOT,
    "config": TokenType.CONFIG,
    "command": TokenType.COMMAND,
    "slash": TokenType.SLASH,
    "prefix": TokenType.PREFIX,
    "both": TokenType.BOTH,
    "mode": TokenType.MODE,
    "when": TokenType.WHEN,
    "event": TokenType.EVENT,
    "task": TokenType.TASK,
    "every": TokenType.EVERY,
    "fn": TokenType.FN,
    "if": TokenType.IF,
    "elif": TokenType.ELIF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "in": TokenType.IN,
    "return": TokenType.RETURN,
    "pass": TokenType.PASS,
    "reply": TokenType.REPLY,
    "send": TokenType.SEND,
    "delete": TokenType.DELETE,
    "require": TokenType.REQUIRE,
    "permission": TokenType.PERMISSION,
    "cooldown": TokenType.COOLDOWN,
    "per": TokenType.PER,
    "ask": TokenType.ASK,
    "timeout": TokenType.TIMEOUT,
    "with": TokenType.WITH,
    "button": TokenType.BUTTON,
    "select": TokenType.SELECT,
    "option": TokenType.OPTION,
    "embed": TokenType.EMBED,
    "title": TokenType.TITLE,
    "description": TokenType.DESCRIPTION,
    "color": TokenType.COLOR,
    "thumbnail": TokenType.THUMBNAIL,
    "image": TokenType.IMAGE,
    "footer": TokenType.FOOTER,
    "field": TokenType.FIELD,
    "inline": TokenType.INLINE,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "null": TokenType.NULL,
}


class LexerError(Exception):
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"Syntax Error at line {line}, col {col}: {message}")
        self.message = message
        self.line = line
        self.col = col


class Lexer:
    """
    Lexer for the Cord programming language.
    Produces a list of tokens with full indentation tracking.
    """

    def __init__(self, source: str, filename: str = "<source>"):
        self.source = source
        self.filename = filename
        self.length = len(source)
        self.pos = 0
        self.line = 1
        self.col = 1

        self.indent_stack = [0]
        self.tokens: List[Token] = []
        self.paren_depth = 0  # Ignore newlines inside (), [], {}

    def error(self, msg: str, line: Optional[int] = None, col: Optional[int] = None):
        raise LexerError(msg, line or self.line, col or self.col)

    def peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx < self.length:
            return self.source[idx]
        return ""

    def advance(self) -> str:
        if self.pos >= self.length:
            return ""
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def match(self, expected: str) -> bool:
        if self.peek() == expected:
            self.advance()
            return True
        return False

    def tokenize(self) -> List[Token]:
        at_line_start = True

        while self.pos < self.length:
            # Handle line indentation at start of lines
            if at_line_start:
                indent_col = self.col
                indent_line = self.line
                indent_width = 0

                # Count whitespace for indentation
                while self.pos < self.length and self.peek() in (" ", "\t"):
                    ch = self.advance()
                    if ch == "\t":
                        indent_width += 4
                    else:
                        indent_width += 1

                # Check if line is empty or comment
                if self.peek() == "\n":
                    self.advance()
                    continue
                if self.peek() == "#":
                    self.skip_comment()
                    if self.peek() == "\n":
                        self.advance()
                    continue
                if self.pos >= self.length:
                    break

                # Emit INDENT / DEDENT only if not inside parentheses
                if self.paren_depth == 0:
                    current_indent = self.indent_stack[-1]
                    if indent_width > current_indent:
                        self.indent_stack.append(indent_width)
                        self.tokens.append(Token(TokenType.INDENT, indent_width, indent_line, indent_col))
                    elif indent_width < current_indent:
                        while len(self.indent_stack) > 1 and indent_width < self.indent_stack[-1]:
                            self.indent_stack.pop()
                            self.tokens.append(Token(TokenType.DEDENT, indent_width, indent_line, indent_col))
                        if indent_width != self.indent_stack[-1]:
                            self.error(f"Inconsistent indentation: level {indent_width} does not match any outer indentation level", indent_line, indent_col)

                at_line_start = False

            ch = self.peek()

            # Skip spaces and tabs within a line
            if ch in (" ", "\t"):
                self.advance()
                continue

            # Skip comments
            if ch == "#":
                self.skip_comment()
                continue

            # Newlines
            if ch == "\n":
                line_num = self.line
                col_num = self.col
                self.advance()
                at_line_start = True
                if self.paren_depth == 0:
                    # Avoid emitting consecutive NEWLINE tokens
                    if self.tokens and self.tokens[-1].type != TokenType.NEWLINE and self.tokens[-1].type != TokenType.INDENT:
                        self.tokens.append(Token(TokenType.NEWLINE, "\n", line_num, col_num))
                continue

            # Channel references: #welcome, #general, #bot-commands
            # (Note: comments start with # followed by space or non-identifier, but we can differentiate:
            # If # is immediately followed by letter or underscore, it's a channel ref!
            # Otherwise it's a comment.)
            # Handled above: if comment, skip_comment is called unless it's a channel ref.
            # Let's refine channel reference check:
            start_line = self.line
            start_col = self.col

            # Numbers & Durations
            if ch.isdigit():
                self.lex_number_or_duration()
                continue

            # Strings
            if ch in ('"', "'"):
                self.lex_string()
                continue

            # Identifiers & Keywords
            if ch.isalpha() or ch == "_":
                self.lex_identifier()
                continue

            # Delimiters and operators
            self.advance()

            if ch == "(":
                self.paren_depth += 1
                self.tokens.append(Token(TokenType.LPAREN, "(", start_line, start_col))
            elif ch == ")":
                if self.paren_depth > 0:
                    self.paren_depth -= 1
                self.tokens.append(Token(TokenType.RPAREN, ")", start_line, start_col))
            elif ch == "[":
                self.paren_depth += 1
                self.tokens.append(Token(TokenType.LBRACKET, "[", start_line, start_col))
            elif ch == "]":
                if self.paren_depth > 0:
                    self.paren_depth -= 1
                self.tokens.append(Token(TokenType.RBRACKET, "]", start_line, start_col))
            elif ch == "{":
                self.paren_depth += 1
                self.tokens.append(Token(TokenType.LBRACE, "{", start_line, start_col))
            elif ch == "}":
                if self.paren_depth > 0:
                    self.paren_depth -= 1
                self.tokens.append(Token(TokenType.RBRACE, "}", start_line, start_col))
            elif ch == ":":
                self.tokens.append(Token(TokenType.COLON, ":", start_line, start_col))
            elif ch == ",":
                self.tokens.append(Token(TokenType.COMMA, ",", start_line, start_col))
            elif ch == ".":
                self.tokens.append(Token(TokenType.DOT, ".", start_line, start_col))
            elif ch == "+":
                if self.match("="):
                    self.tokens.append(Token(TokenType.PLUS_ASSIGN, "+=", start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.PLUS, "+", start_line, start_col))
            elif ch == "-":
                if self.match("="):
                    self.tokens.append(Token(TokenType.MINUS_ASSIGN, "-=", start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.MINUS, "-", start_line, start_col))
            elif ch == "*":
                if self.match("="):
                    self.tokens.append(Token(TokenType.STAR_ASSIGN, "*=", start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.STAR, "*", start_line, start_col))
            elif ch == "/":
                if self.match("="):
                    self.tokens.append(Token(TokenType.SLASH_ASSIGN, "/=", start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.SLASH_OP, "/", start_line, start_col))
            elif ch == "%":
                self.tokens.append(Token(TokenType.PERCENT, "%", start_line, start_col))
            elif ch == "=":
                if self.match("="):
                    self.tokens.append(Token(TokenType.EQ, "==", start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.ASSIGN, "=", start_line, start_col))
            elif ch == "!":
                if self.match("="):
                    self.tokens.append(Token(TokenType.NEQ, "!=", start_line, start_col))
                else:
                    self.error("Unexpected character '!' (did you mean '!=' or prefix config?)", start_line, start_col)
            elif ch == "<":
                if self.match("="):
                    self.tokens.append(Token(TokenType.LTE, "<=", start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.LT, "<", start_line, start_col))
            elif ch == ">":
                if self.match("="):
                    self.tokens.append(Token(TokenType.GTE, ">=", start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.GT, ">", start_line, start_col))
            else:
                self.error(f"Unexpected character: {repr(ch)}", start_line, start_col)

        # Emit trailing newline if needed
        if self.tokens and self.tokens[-1].type != TokenType.NEWLINE:
            self.tokens.append(Token(TokenType.NEWLINE, "\n", self.line, self.col))

        # Emit remaining DEDENT tokens at EOF
        while len(self.indent_stack) > 1:
            self.indent_stack.pop()
            self.tokens.append(Token(TokenType.DEDENT, self.indent_stack[-1], self.line, self.col))

        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens

    def skip_comment(self):
        # Check if this might be a channel reference: #channel-name
        # e.g., if preceded by send or in expression
        # In Cord: comments are # followed by space, or lines like # comment.
        # But in `send #welcome "text"`, #welcome is a channel ref!
        # If # is immediately followed by an alphanumeric / underscore / hyphen character:
        start_line = self.line
        start_col = self.col
        next_ch = self.peek(1)
        if next_ch.isalpha() or next_ch == "_":
            # Channel reference!
            self.advance()  # consume '#'
            name_chars = []
            while self.pos < self.length and (self.peek().isalnum() or self.peek() in ("_", "-")):
                name_chars.append(self.advance())
            channel_name = "".join(name_chars)
            self.tokens.append(Token(TokenType.CHANNEL_REF, channel_name, start_line, start_col, raw=f"#{channel_name}"))
            return

        # Otherwise it's a regular comment: consume to newline
        while self.pos < self.length and self.peek() != "\n":
            self.advance()

    def lex_number_or_duration(self):
        start_line = self.line
        start_col = self.col
        num_str = []
        is_float = False

        while self.pos < self.length and (self.peek().isdigit() or self.peek() == "."):
            if self.peek() == ".":
                # Check if it's a method call like 5.foo or dot operator
                if self.peek(1).isalpha() or is_float:
                    break
                is_float = True
            num_str.append(self.advance())

        val_str = "".join(num_str)
        num_val = float(val_str) if is_float else int(val_str)

        # Check for duration suffixes: ms, s, m, h, d
        # Look ahead for duration suffix
        unit_chars = []
        while self.pos < self.length and self.peek().isalpha():
            unit_chars.append(self.advance())

        unit = "".join(unit_chars)
        if unit:
            seconds = 0.0
            if unit == "ms":
                seconds = num_val / 1000.0
            elif unit == "s":
                seconds = float(num_val)
            elif unit == "m":
                seconds = float(num_val) * 60.0
            elif unit == "h":
                seconds = float(num_val) * 3600.0
            elif unit == "d":
                seconds = float(num_val) * 86400.0
            else:
                self.error(f"Unknown duration unit '{unit}'. Valid units are ms, s, m, h, d.", start_line, start_col)

            self.tokens.append(Token(TokenType.DURATION, seconds, start_line, start_col, raw=f"{val_str}{unit}"))
        else:
            token_type = TokenType.FLOAT if is_float else TokenType.INT
            self.tokens.append(Token(token_type, num_val, start_line, start_col, raw=val_str))

    def lex_string(self):
        quote = self.advance()
        start_line = self.line
        start_col = self.col
        chars = []

        while self.pos < self.length and self.peek() != quote:
            ch = self.advance()
            if ch == "\\":
                if self.pos >= self.length:
                    self.error("Unterminated escape sequence in string", start_line, start_col)
                esc = self.advance()
                if esc == "n":
                    chars.append("\n")
                elif esc == "t":
                    chars.append("\t")
                elif esc == "r":
                    chars.append("\r")
                elif esc == "\\":
                    chars.append("\\")
                elif esc == quote:
                    chars.append(quote)
                elif esc == "{" or esc == "}":
                    chars.append(esc)
                else:
                    chars.append(f"\\{esc}")
            elif ch == "\n":
                self.error("Unterminated string (multi-line strings without triple quotes are not allowed)", start_line, start_col)
            else:
                chars.append(ch)

        if self.pos >= self.length or self.peek() != quote:
            self.error(f"Unterminated string literal starting at line {start_line}, col {start_col}", start_line, start_col)

        self.advance()  # consume closing quote
        content = "".join(chars)
        self.tokens.append(Token(TokenType.STRING, content, start_line, start_col, raw=f"{quote}{content}{quote}"))

    def lex_identifier(self):
        start_line = self.line
        start_col = self.col
        chars = []

        while self.pos < self.length and (self.peek().isalnum() or self.peek() == "_"):
            chars.append(self.advance())

        ident = "".join(chars)
        token_type = KEYWORDS.get(ident, TokenType.IDENTIFIER)
        self.tokens.append(Token(token_type, ident, start_line, start_col))
