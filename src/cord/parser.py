"""
Recursive-descent Parser for the Cord programming language.
Produces clean AST nodes with detailed error reporting and beginner-friendly hints.
"""

import re
from typing import List, Optional, Any, Dict, Union
from cord.lexer import Token, TokenType, Lexer, LexerError
from cord.ast_nodes import (
    ASTNode, Program, Block, Statement,
    BotDecl, ConfigDecl, Parameter, CommandDecl, EventDecl, TaskDecl, FunctionDecl,
    VarAssign, CompoundAssign, IfStmt, WhileStmt, ForStmt, ReturnStmt, PassStmt,
    ReplyStmt, SendStmt, DeleteStmt, RequireStmt, CooldownStmt, AskStmt, ModeStmt,
    ExprStmt, Literal, DurationLiteral, InterpolatedString, Identifier, ChannelRef,
    BinaryOp, UnaryOp, ListLiteral, MapLiteral, IndexAccess, MemberAccess, CallExpr,
    EmbedBlock, EmbedField
)


class ParserError(Exception):
    def __init__(self, message: str, line: int, col: int, hint: Optional[str] = None):
        hint_str = f"\n  Hint: {hint}" if hint else ""
        super().__init__(f"Syntax Error at line {line}, col {col}: {message}{hint_str}")
        self.message = message
        self.line = line
        self.col = col
        self.hint = hint


class Parser:
    """
    Recursive-descent parser for Cord.
    """

    def __init__(self, tokens: List[Token], filename: str = "<source>"):
        self.tokens = tokens
        self.filename = filename
        self.pos = 0

    # -------------------------------------------------------------------------
    # Navigation & Matching Helpers
    # -------------------------------------------------------------------------

    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return self.tokens[-1]  # Return EOF token

    def check(self, token_type: TokenType) -> bool:
        return self.peek().type == token_type

    def advance(self) -> Token:
        tok = self.peek()
        if self.pos < len(self.tokens):
            self.pos += 1
        return tok

    def match(self, *token_types: TokenType) -> Optional[Token]:
        for tt in token_types:
            if self.check(tt):
                return self.advance()
        return None

    def consume(self, token_type: TokenType, err_msg: str, hint: Optional[str] = None) -> Token:
        if self.check(token_type):
            return self.advance()
        tok = self.peek()
        raise ParserError(
            f"{err_msg} (got {tok.type.name} '{tok.value}')",
            tok.line, tok.col, hint
        )

    def consume_identifier_like(self, err_msg: str, hint: Optional[str] = None) -> Token:
        tok = self.peek()
        if tok.type == TokenType.IDENTIFIER or (isinstance(tok.value, str) and tok.value.isidentifier()):
            return self.advance()
        raise ParserError(
            f"{err_msg} (got {tok.type.name} '{tok.value}')",
            tok.line, tok.col, hint
        )

    def skip_newlines(self):
        while self.check(TokenType.NEWLINE):
            self.advance()

    # -------------------------------------------------------------------------
    # Main Entry Point
    # -------------------------------------------------------------------------

    def parse(self) -> Program:
        statements: List[Statement] = []
        self.skip_newlines()

        while not self.check(TokenType.EOF):
            stmt = self.parse_top_level_statement()
            if stmt:
                statements.append(stmt)
            self.skip_newlines()

        return Program(statements=statements, line=1, col=1)

    # -------------------------------------------------------------------------
    # Top-Level Statements
    # -------------------------------------------------------------------------

    def parse_top_level_statement(self) -> Optional[Statement]:
        self.skip_newlines()
        tok = self.peek()

        if tok.type == TokenType.BOT:
            return self.parse_bot_decl()
        elif tok.type == TokenType.CONFIG:
            return self.parse_config_decl()
        elif tok.type in (TokenType.COMMAND, TokenType.SLASH, TokenType.PREFIX):
            return self.parse_command_decl()
        elif tok.type == TokenType.WHEN:
            return self.parse_beginner_when_event()
        elif tok.type == TokenType.EVENT:
            return self.parse_developer_event_decl()
        elif tok.type == TokenType.TASK:
            return self.parse_task_decl()
        elif tok.type == TokenType.FN:
            return self.parse_function_decl()
        else:
            # Allow top-level variables, assignments or statements
            return self.parse_statement()

    def parse_bot_decl(self) -> BotDecl:
        tok = self.advance()  # consume 'bot'
        name_tok = self.consume(TokenType.STRING, "Expected string for bot name", 'e.g. bot "MyBot"')
        self.skip_newlines()
        return BotDecl(name=name_tok.value, line=tok.line, col=tok.col)

    def parse_config_decl(self) -> ConfigDecl:
        tok = self.advance()  # consume 'config'
        self.consume(TokenType.COLON, "Expected ':' after 'config'", "Format:\nconfig:\n    prefix = '!'")
        self.consume(TokenType.NEWLINE, "Expected newline after 'config:'")
        self.consume(TokenType.INDENT, "Expected indented configuration block")

        settings: Dict[str, ASTNode] = {}
        while not self.check(TokenType.DEDENT) and not self.check(TokenType.EOF):
            self.skip_newlines()
            if self.check(TokenType.DEDENT):
                break
            key_tok = self.consume_identifier_like("Expected setting name in config block")
            self.consume(TokenType.ASSIGN, "Expected '=' after setting name")
            val_expr = self.parse_expression()
            settings[key_tok.value] = val_expr
            self.skip_newlines()

        self.consume(TokenType.DEDENT, "Expected end of config block")
        return ConfigDecl(settings=settings, line=tok.line, col=tok.col)

    def parse_command_decl(self) -> CommandDecl:
        mode = "both"
        tok = self.peek()

        # Handle "slash command ..." or "prefix command ..."
        if tok.type == TokenType.SLASH:
            self.advance()
            self.consume(TokenType.COMMAND, "Expected 'command' after 'slash'")
            mode = "slash"
        elif tok.type == TokenType.PREFIX:
            self.advance()
            self.consume(TokenType.COMMAND, "Expected 'command' after 'prefix'")
            mode = "prefix"
        else:
            self.consume(TokenType.COMMAND, "Expected 'command'")

        name_tok = self.consume(TokenType.IDENTIFIER, "Expected command name", "e.g. command ping:")
        params: List[Parameter] = []

        # Optional parameter list: command warn(target: Member, reason = "none")
        if self.match(TokenType.LPAREN):
            params = self.parse_parameters()
            self.consume(TokenType.RPAREN, "Expected ')' after parameter list")

        # Optional mode specification: command ping mode=slash:
        if self.match(TokenType.MODE):
            self.consume(TokenType.ASSIGN, "Expected '=' after 'mode'")
            mode_tok = self.peek()
            if mode_tok.type in (TokenType.SLASH, TokenType.PREFIX, TokenType.BOTH):
                mode = mode_tok.value
                self.advance()
            elif mode_tok.type == TokenType.IDENTIFIER and mode_tok.value in ("slash", "prefix", "both"):
                mode = mode_tok.value
                self.advance()
            else:
                raise ParserError("Expected 'slash', 'prefix', or 'both' for command mode", mode_tok.line, mode_tok.col)

        self.consume(TokenType.COLON, "Expected ':' after command header")
        body = self.parse_block()

        # Check if the body contains an explicit "mode slash|prefix|both" statement
        for stmt in body.statements:
            if isinstance(stmt, ModeStmt):
                mode = stmt.mode

        return CommandDecl(name=name_tok.value, params=params, body=body, mode=mode, line=tok.line, col=tok.col)

    def parse_beginner_when_event(self) -> EventDecl:
        tok = self.advance()  # consume 'when'
        
        # Match English-like event phrasing:
        # - when someone joins:
        # - when someone leaves:
        # - when a message is sent:
        # - when a reaction is added:
        # - when bot starts:
        words = []
        while not self.check(TokenType.COLON) and not self.check(TokenType.NEWLINE) and not self.check(TokenType.EOF):
            words.append(self.advance().value)

        phrase = " ".join(str(w) for w in words).strip().lower()
        self.consume(TokenType.COLON, f"Expected ':' after 'when {phrase}'")
        body = self.parse_block()

        if "someone joins" in phrase or "member joins" in phrase or "user joins" in phrase:
            return EventDecl(event_name="member_join", params=[Parameter(name="member", type_hint="Member")], body=body, line=tok.line, col=tok.col)
        elif "someone leaves" in phrase or "member leaves" in phrase or "user leaves" in phrase:
            return EventDecl(event_name="member_leave", params=[Parameter(name="member", type_hint="Member")], body=body, line=tok.line, col=tok.col)
        elif "message is sent" in phrase or "message sent" in phrase or "message" in phrase:
            return EventDecl(event_name="message", params=[Parameter(name="message", type_hint="Message")], body=body, line=tok.line, col=tok.col)
        elif "reaction is added" in phrase or "reaction added" in phrase or "reaction" in phrase:
            return EventDecl(event_name="reaction_add", params=[Parameter(name="reaction"), Parameter(name="user")], body=body, line=tok.line, col=tok.col)
        elif "bot starts" in phrase or "ready" in phrase:
            return EventDecl(event_name="ready", params=[], body=body, line=tok.line, col=tok.col)
        else:
            # Fallback custom phrase
            event_clean = phrase.replace(" ", "_")
            return EventDecl(event_name=event_clean, params=[], body=body, line=tok.line, col=tok.col)

    def parse_developer_event_decl(self) -> EventDecl:
        tok = self.advance()  # consume 'event'
        name_tok = self.consume(TokenType.IDENTIFIER, "Expected event name", "e.g. event member_join(member):")
        params: List[Parameter] = []
        if self.match(TokenType.LPAREN):
            params = self.parse_parameters()
            self.consume(TokenType.RPAREN, "Expected ')' after parameter list")
        self.consume(TokenType.COLON, "Expected ':' after event header")
        body = self.parse_block()
        return EventDecl(event_name=name_tok.value, params=params, body=body, line=tok.line, col=tok.col)

    def parse_task_decl(self) -> TaskDecl:
        tok = self.advance()  # consume 'task'
        name_tok = self.consume(TokenType.IDENTIFIER, "Expected task name", "e.g. task update_status every 30m:")
        self.consume(TokenType.EVERY, "Expected 'every' after task name", "e.g. task clean_logs every 1h:")
        
        dur_tok = self.consume(TokenType.DURATION, "Expected duration for task interval", "e.g. 30m, 1h, 5s")
        interval = DurationLiteral(seconds=dur_tok.value, raw=dur_tok.raw, line=dur_tok.line, col=dur_tok.col)

        self.consume(TokenType.COLON, "Expected ':' after task interval")
        body = self.parse_block()
        return TaskDecl(name=name_tok.value, interval=interval, body=body, line=tok.line, col=tok.col)

    def parse_function_decl(self) -> FunctionDecl:
        tok = self.advance()  # consume 'fn'
        name_tok = self.consume(TokenType.IDENTIFIER, "Expected function name", "e.g. fn get_balance(user_id):")
        params: List[Parameter] = []
        if self.match(TokenType.LPAREN):
            params = self.parse_parameters()
            self.consume(TokenType.RPAREN, "Expected ')' after parameter list")
        self.consume(TokenType.COLON, "Expected ':' after function header")
        body = self.parse_block()
        return FunctionDecl(name=name_tok.value, params=params, body=body, line=tok.line, col=tok.col)

    def parse_parameters(self) -> List[Parameter]:
        params: List[Parameter] = []
        if self.check(TokenType.RPAREN):
            return params

        while True:
            param_tok = self.consume(TokenType.IDENTIFIER, "Expected parameter name")
            type_hint: Optional[str] = None
            default_val: Optional[ASTNode] = None

            if self.match(TokenType.COLON):
                hint_tok = self.consume(TokenType.IDENTIFIER, "Expected type conversion hint after ':'", "e.g. target: Member")
                type_hint = hint_tok.value

            if self.match(TokenType.ASSIGN):
                default_val = self.parse_expression()

            params.append(Parameter(name=param_tok.value, type_hint=type_hint, default_value=default_val, line=param_tok.line, col=param_tok.col))

            if not self.match(TokenType.COMMA):
                break

        return params

    # -------------------------------------------------------------------------
    # Statements & Suites
    # -------------------------------------------------------------------------

    def parse_block(self) -> Block:
        self.consume(TokenType.NEWLINE, "Expected newline after ':'")
        self.consume(TokenType.INDENT, "Expected indented block")
        statements: List[Statement] = []

        while not self.check(TokenType.DEDENT) and not self.check(TokenType.EOF):
            self.skip_newlines()
            if self.check(TokenType.DEDENT):
                break
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
            self.skip_newlines()

        self.consume(TokenType.DEDENT, "Expected end of indented block")
        return Block(statements=statements)

    def parse_statement(self) -> Statement:
        self.skip_newlines()
        tok = self.peek()

        if tok.type == TokenType.REPLY:
            return self.parse_reply_stmt()
        elif tok.type == TokenType.SEND:
            return self.parse_send_stmt()
        elif tok.type == TokenType.DELETE:
            return self.parse_delete_stmt()
        elif tok.type == TokenType.REQUIRE:
            return self.parse_require_stmt()
        elif tok.type == TokenType.COOLDOWN:
            return self.parse_cooldown_stmt()
        elif tok.type == TokenType.ASK:
            return self.parse_ask_stmt()
        elif tok.type == TokenType.MODE:
            return self.parse_mode_stmt()
        elif tok.type == TokenType.IF:
            return self.parse_if_stmt()
        elif tok.type == TokenType.WHILE:
            return self.parse_while_stmt()
        elif tok.type == TokenType.FOR:
            return self.parse_for_stmt()
        elif tok.type == TokenType.RETURN:
            return self.parse_return_stmt()
        elif tok.type == TokenType.PASS:
            self.advance()
            return PassStmt(line=tok.line, col=tok.col)
        else:
            return self.parse_assignment_or_expression_stmt()

    def parse_reply_stmt(self) -> ReplyStmt:
        tok = self.advance()  # consume 'reply'
        if self.match(TokenType.EMBED):
            self.consume(TokenType.COLON, "Expected ':' after 'embed'")
            embed_node = self.parse_embed_block()
            return ReplyStmt(embed=embed_node, line=tok.line, col=tok.col)
        else:
            expr = self.parse_expression()
            return ReplyStmt(expr=expr, line=tok.line, col=tok.col)

    def parse_send_stmt(self) -> SendStmt:
        tok = self.advance()  # consume 'send'
        target = self.parse_primary_expression()

        if self.match(TokenType.EMBED):
            self.consume(TokenType.COLON, "Expected ':' after 'embed'")
            embed_node = self.parse_embed_block()
            return SendStmt(target=target, embed=embed_node, line=tok.line, col=tok.col)
        else:
            expr = self.parse_expression()
            return SendStmt(target=target, expr=expr, line=tok.line, col=tok.col)

    def parse_delete_stmt(self) -> DeleteStmt:
        tok = self.advance()  # consume 'delete'
        target = None
        if not self.check(TokenType.NEWLINE) and not self.check(TokenType.EOF):
            target = self.parse_expression()
        return DeleteStmt(target=target, line=tok.line, col=tok.col)

    def parse_require_stmt(self) -> RequireStmt:
        tok = self.advance()  # consume 'require'
        kind_tok = self.consume(TokenType.PERMISSION, "Expected 'permission' after 'require'", "e.g. require permission moderate_members")
        perm_tok = self.consume(TokenType.IDENTIFIER, "Expected permission name", "e.g. moderate_members, kick_members, administrator")
        return RequireStmt(kind="permission", value=perm_tok.value, line=tok.line, col=tok.col)

    def parse_cooldown_stmt(self) -> CooldownStmt:
        tok = self.advance()  # consume 'cooldown'
        dur_tok = self.consume(TokenType.DURATION, "Expected duration after 'cooldown'", "e.g. cooldown 5s per user")
        duration = DurationLiteral(seconds=dur_tok.value, raw=dur_tok.raw, line=dur_tok.line, col=dur_tok.col)

        per = "user"
        if self.match(TokenType.PER):
            per_tok = self.advance()
            if per_tok.type == TokenType.IDENTIFIER or per_tok.type in (TokenType.BOT,):
                per = str(per_tok.value).lower()
            else:
                per = str(per_tok.value).lower()

        return CooldownStmt(duration=duration, per=per, line=tok.line, col=tok.col)

    def parse_ask_stmt(self) -> AskStmt:
        tok = self.advance()  # consume 'ask'
        self.consume(TokenType.FOR, "Expected 'for' after 'ask'", "e.g. ask for name [prompt] [timeout=60s]")
        var_tok = self.consume(TokenType.IDENTIFIER, "Expected variable name to store response")

        prompt_expr: Optional[ASTNode] = None
        timeout_lit: Optional[DurationLiteral] = None

        while not self.check(TokenType.NEWLINE) and not self.check(TokenType.EOF):
            if self.match(TokenType.TIMEOUT):
                self.consume(TokenType.ASSIGN, "Expected '=' after timeout")
                dur_tok = self.consume(TokenType.DURATION, "Expected duration value for timeout")
                timeout_lit = DurationLiteral(seconds=dur_tok.value, raw=dur_tok.raw, line=dur_tok.line, col=dur_tok.col)
            else:
                prompt_expr = self.parse_expression()

        return AskStmt(var_name=var_tok.value, prompt=prompt_expr, timeout=timeout_lit, line=tok.line, col=tok.col)

    def parse_mode_stmt(self) -> ModeStmt:
        tok = self.advance()  # consume 'mode'
        mode_tok = self.advance()
        val = str(mode_tok.value).lower()
        if val not in ("slash", "prefix", "both"):
            raise ParserError("Mode must be 'slash', 'prefix', or 'both'", mode_tok.line, mode_tok.col)
        return ModeStmt(mode=val, line=tok.line, col=tok.col)

    def parse_embed_block(self) -> EmbedBlock:
        self.consume(TokenType.NEWLINE, "Expected newline after 'embed:'")
        self.consume(TokenType.INDENT, "Expected indented embed block")

        title_expr = None
        desc_expr = None
        color_expr = None
        thumb_expr = None
        img_expr = None
        footer_expr = None
        fields: List[EmbedField] = []

        while not self.check(TokenType.DEDENT) and not self.check(TokenType.EOF):
            self.skip_newlines()
            if self.check(TokenType.DEDENT):
                break
            field_tok = self.advance()

            if field_tok.type == TokenType.TITLE:
                title_expr = self.parse_expression()
            elif field_tok.type == TokenType.DESCRIPTION:
                desc_expr = self.parse_expression()
            elif field_tok.type == TokenType.COLOR:
                color_expr = self.parse_expression()
            elif field_tok.type == TokenType.THUMBNAIL:
                thumb_expr = self.parse_expression()
            elif field_tok.type == TokenType.IMAGE:
                img_expr = self.parse_expression()
            elif field_tok.type == TokenType.FOOTER:
                footer_expr = self.parse_expression()
            elif field_tok.type == TokenType.FIELD:
                name_expr = self.parse_expression()
                val_expr = self.parse_expression()
                inline_expr = Literal(value=False)
                if self.match(TokenType.INLINE):
                    self.consume(TokenType.ASSIGN, "Expected '=' after inline")
                    inline_expr = self.parse_expression()
                fields.append(EmbedField(name=name_expr, value=val_expr, inline=inline_expr, line=field_tok.line, col=field_tok.col))
            else:
                raise ParserError(f"Unexpected embed property '{field_tok.value}'", field_tok.line, field_tok.col)

            self.skip_newlines()

        self.consume(TokenType.DEDENT, "Expected end of embed block")
        return EmbedBlock(
            title=title_expr,
            description=desc_expr,
            color=color_expr,
            thumbnail=thumb_expr,
            image=img_expr,
            footer=footer_expr,
            fields=fields
        )

    def parse_if_stmt(self) -> IfStmt:
        tok = self.advance()  # consume 'if'
        cond = self.parse_expression()
        self.consume(TokenType.COLON, "Expected ':' after if condition")
        then_body = self.parse_block()

        elif_branches = []
        else_body = None

        while self.match(TokenType.ELIF):
            elif_cond = self.parse_expression()
            self.consume(TokenType.COLON, "Expected ':' after elif condition")
            elif_body = self.parse_block()
            elif_branches.append((elif_cond, elif_body))

        if self.match(TokenType.ELSE):
            self.consume(TokenType.COLON, "Expected ':' after else")
            else_body = self.parse_block()

        return IfStmt(condition=cond, then_body=then_body, elif_branches=elif_branches, else_body=else_body, line=tok.line, col=tok.col)

    def parse_while_stmt(self) -> WhileStmt:
        tok = self.advance()  # consume 'while'
        cond = self.parse_expression()
        self.consume(TokenType.COLON, "Expected ':' after while condition")
        body = self.parse_block()
        return WhileStmt(condition=cond, body=body, line=tok.line, col=tok.col)

    def parse_for_stmt(self) -> ForStmt:
        tok = self.advance()  # consume 'for'
        var_tok = self.consume(TokenType.IDENTIFIER, "Expected loop variable name")
        self.consume(TokenType.IN, "Expected 'in' after loop variable")
        iterable = self.parse_expression()
        self.consume(TokenType.COLON, "Expected ':' after for statement")
        body = self.parse_block()
        return ForStmt(var_name=var_tok.value, iterable=iterable, body=body, line=tok.line, col=tok.col)

    def parse_return_stmt(self) -> ReturnStmt:
        tok = self.advance()  # consume 'return'
        val = None
        if not self.check(TokenType.NEWLINE) and not self.check(TokenType.EOF):
            val = self.parse_expression()
        return ReturnStmt(value=val, line=tok.line, col=tok.col)

    def parse_assignment_or_expression_stmt(self) -> Statement:
        expr = self.parse_expression()

        # Check for assignment operators: =, +=, -=, *=, /=
        if self.match(TokenType.ASSIGN):
            val = self.parse_expression()
            return VarAssign(target=expr, value=val, line=expr.line, col=expr.col)
        elif self.match(TokenType.PLUS_ASSIGN):
            val = self.parse_expression()
            return CompoundAssign(target=expr, op="+", value=val, line=expr.line, col=expr.col)
        elif self.match(TokenType.MINUS_ASSIGN):
            val = self.parse_expression()
            return CompoundAssign(target=expr, op="-", value=val, line=expr.line, col=expr.col)
        elif self.match(TokenType.STAR_ASSIGN):
            val = self.parse_expression()
            return CompoundAssign(target=expr, op="*", value=val, line=expr.line, col=expr.col)
        elif self.match(TokenType.SLASH_ASSIGN):
            val = self.parse_expression()
            return CompoundAssign(target=expr, op="/", value=val, line=expr.line, col=expr.col)

        return ExprStmt(expr=expr, line=expr.line, col=expr.col)

    # -------------------------------------------------------------------------
    # Expressions (Operator Precedence)
    # -------------------------------------------------------------------------

    def parse_expression(self) -> ASTNode:
        return self.parse_or()

    def parse_or(self) -> ASTNode:
        left = self.parse_and()
        while self.match(TokenType.OR):
            op = "or"
            right = self.parse_and()
            left = BinaryOp(left=left, op=op, right=right, line=left.line, col=left.col)
        return left

    def parse_and(self) -> ASTNode:
        left = self.parse_not()
        while self.match(TokenType.AND):
            op = "and"
            right = self.parse_not()
            left = BinaryOp(left=left, op=op, right=right, line=left.line, col=left.col)
        return left

    def parse_not(self) -> ASTNode:
        if self.match(TokenType.NOT):
            tok = self.tokens[self.pos - 1]
            operand = self.parse_not()
            return UnaryOp(op="not", operand=operand, line=tok.line, col=tok.col)
        return self.parse_comparison()

    def parse_comparison(self) -> ASTNode:
        left = self.parse_addition()
        while True:
            op_tok = self.match(TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.LTE, TokenType.GT, TokenType.GTE)
            if op_tok:
                op = op_tok.value
                right = self.parse_addition()
                left = BinaryOp(left=left, op=op, right=right, line=left.line, col=left.col)
            else:
                break
        return left

    def parse_addition(self) -> ASTNode:
        left = self.parse_multiplication()
        while True:
            op_tok = self.match(TokenType.PLUS, TokenType.MINUS)
            if op_tok:
                op = op_tok.value
                right = self.parse_multiplication()
                left = BinaryOp(left=left, op=op, right=right, line=left.line, col=left.col)
            else:
                break
        return left

    def parse_multiplication(self) -> ASTNode:
        left = self.parse_unary()
        while True:
            op_tok = self.match(TokenType.STAR, TokenType.SLASH_OP, TokenType.PERCENT)
            if op_tok:
                op = op_tok.value
                right = self.parse_unary()
                left = BinaryOp(left=left, op=op, right=right, line=left.line, col=left.col)
            else:
                break
        return left

    def parse_unary(self) -> ASTNode:
        op_tok = self.match(TokenType.MINUS, TokenType.PLUS)
        if op_tok:
            operand = self.parse_unary()
            return UnaryOp(op=op_tok.value, operand=operand, line=op_tok.line, col=op_tok.col)
        return self.parse_postfix()

    def parse_postfix(self) -> ASTNode:
        expr = self.parse_primary_expression()

        while True:
            if self.match(TokenType.LPAREN):
                # Function call
                args = []
                kwargs = {}
                if not self.check(TokenType.RPAREN):
                    while True:
                        # Check keyword arg: key=val
                        if self.check(TokenType.IDENTIFIER) and self.peek(1).type == TokenType.ASSIGN:
                            kw_name = self.advance().value
                            self.advance()  # consume '='
                            kwargs[kw_name] = self.parse_expression()
                        else:
                            args.append(self.parse_expression())
                        if not self.match(TokenType.COMMA):
                            break
                self.consume(TokenType.RPAREN, "Expected ')' after call arguments")
                expr = CallExpr(callee=expr, args=args, kwargs=kwargs, line=expr.line, col=expr.col)
            elif self.match(TokenType.LBRACKET):
                # Subscript / index access
                idx_expr = self.parse_expression()
                self.consume(TokenType.RBRACKET, "Expected ']' after index")
                expr = IndexAccess(target=expr, index=idx_expr, line=expr.line, col=expr.col)
            elif self.match(TokenType.DOT):
                # Member access
                member_tok = self.consume_identifier_like("Expected property name after '.'")
                expr = MemberAccess(target=expr, member=member_tok.value, line=expr.line, col=expr.col)
            else:
                break

        return expr

    def parse_primary_expression(self) -> ASTNode:
        tok = self.peek()

        if tok.type == TokenType.INT or tok.type == TokenType.FLOAT:
            self.advance()
            return Literal(value=tok.value, raw=tok.raw, line=tok.line, col=tok.col)
        elif tok.type == TokenType.DURATION:
            self.advance()
            return DurationLiteral(seconds=tok.value, raw=tok.raw, line=tok.line, col=tok.col)
        elif tok.type == TokenType.STRING:
            self.advance()
            return self.process_string_interpolation(tok)
        elif tok.type == TokenType.TRUE:
            self.advance()
            return Literal(value=True, raw="true", line=tok.line, col=tok.col)
        elif tok.type == TokenType.FALSE:
            self.advance()
            return Literal(value=False, raw="false", line=tok.line, col=tok.col)
        elif tok.type == TokenType.NULL:
            self.advance()
            return Literal(value=None, raw="null", line=tok.line, col=tok.col)
        elif tok.type == TokenType.CHANNEL_REF:
            self.advance()
            return ChannelRef(channel_name=tok.value, line=tok.line, col=tok.col)
        elif tok.type == TokenType.IDENTIFIER or tok.type in (TokenType.BOT, TokenType.MODE, TokenType.SLASH, TokenType.PREFIX, TokenType.BOTH):
            self.advance()
            return Identifier(name=tok.value, line=tok.line, col=tok.col)
        elif tok.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expression()
            self.consume(TokenType.RPAREN, "Expected ')' to close expression")
            return expr
        elif tok.type == TokenType.LBRACKET:
            # List literal: [1, 2, 3]
            self.advance()
            elements = []
            if not self.check(TokenType.RBRACKET):
                while True:
                    elements.append(self.parse_expression())
                    if not self.match(TokenType.COMMA):
                        break
            self.consume(TokenType.RBRACKET, "Expected ']' after list elements")
            return ListLiteral(elements=elements, line=tok.line, col=tok.col)
        elif tok.type == TokenType.LBRACE:
            # Map literal: {"key": value}
            self.advance()
            pairs = []
            if not self.check(TokenType.RBRACE):
                while True:
                    key_expr = self.parse_expression()
                    self.consume(TokenType.COLON, "Expected ':' between key and value in map literal")
                    val_expr = self.parse_expression()
                    pairs.append((key_expr, val_expr))
                    if not self.match(TokenType.COMMA):
                        break
            self.consume(TokenType.RBRACE, "Expected '}' after map literal")
            return MapLiteral(pairs=pairs, line=tok.line, col=tok.col)
        else:
            raise ParserError(f"Unexpected token in expression: {tok.type.name} '{tok.value}'", tok.line, tok.col)

    def process_string_interpolation(self, string_tok: Token) -> ASTNode:
        """
        Splits string into literal parts and expressions when `{expr}` is detected.
        """
        content = string_tok.value
        # If there are no curly braces, it's a plain literal
        if "{" not in content:
            return Literal(value=content, raw=string_tok.raw, line=string_tok.line, col=string_tok.col)

        # Parse `{...}` interpolations
        parts: List[Union[str, ASTNode]] = []
        pattern = re.compile(r"\{([^}]+)\}")
        last_idx = 0

        for match in pattern.finditer(content):
            start, end = match.span()
            if start > last_idx:
                parts.append(content[last_idx:start])

            expr_code = match.group(1).strip()
            # Lex and parse the inner expression
            inner_lexer = Lexer(expr_code, filename=self.filename)
            inner_tokens = inner_lexer.tokenize()
            inner_parser = Parser(inner_tokens, filename=self.filename)
            expr_ast = inner_parser.parse_expression()
            parts.append(expr_ast)

            last_idx = end

        if last_idx < len(content):
            parts.append(content[last_idx:])

        return InterpolatedString(parts=parts, line=string_tok.line, col=string_tok.col)
