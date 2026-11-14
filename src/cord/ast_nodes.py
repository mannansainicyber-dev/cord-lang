"""
AST (Abstract Syntax Tree) node definitions for the Cord programming language.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict, Union


@dataclass
class ASTNode:
    """Base class for all AST nodes with source position tracking."""
    line: int = 1
    col: int = 1


# ============================================================================
# Expressions
# ============================================================================

@dataclass
class Literal(ASTNode):
    """Literal values: int, float, str, bool, null, or duration."""
    value: Any = None
    raw: str = ""


@dataclass
class DurationLiteral(ASTNode):
    """Duration value in seconds (e.g., 5s, 10m, 2h, 1d)."""
    seconds: float = 0.0
    raw: str = ""


@dataclass
class InterpolatedString(ASTNode):
    """String containing interpolated expressions, e.g. "Hello {name}! 2+2={2+2}"."""
    parts: List[Union[str, ASTNode]] = field(default_factory=list)


@dataclass
class Identifier(ASTNode):
    """Variable or reference identifier."""
    name: str = ""


@dataclass
class BinaryOp(ASTNode):
    """Binary operations: +, -, *, /, %, ==, !=, <, <=, >, >=, and, or."""
    left: ASTNode = field(default_factory=ASTNode)
    op: str = ""
    right: ASTNode = field(default_factory=ASTNode)


@dataclass
class UnaryOp(ASTNode):
    """Unary operations: not, -, +."""
    op: str = ""
    operand: ASTNode = field(default_factory=ASTNode)


@dataclass
class ListLiteral(ASTNode):
    """List literal: [1, 2, 3]."""
    elements: List[ASTNode] = field(default_factory=list)


@dataclass
class MapLiteral(ASTNode):
    """Map/dict literal: {"key": value}."""
    pairs: List[tuple] = field(default_factory=list)  # List of (ASTNode key, ASTNode value)


@dataclass
class IndexAccess(ASTNode):
    """Index or subscript access: target[index]."""
    target: ASTNode = field(default_factory=ASTNode)
    index: ASTNode = field(default_factory=ASTNode)


@dataclass
class MemberAccess(ASTNode):
    """Member or attribute access: target.member."""
    target: ASTNode = field(default_factory=ASTNode)
    member: str = ""


@dataclass
class CallExpr(ASTNode):
    """Function or method call: callee(arg1, arg2, kw=val)."""
    callee: ASTNode = field(default_factory=ASTNode)
    args: List[ASTNode] = field(default_factory=list)
    kwargs: Dict[str, ASTNode] = field(default_factory=dict)


@dataclass
class ChannelRef(ASTNode):
    """Channel reference literal, e.g. #welcome or #rules."""
    channel_name: str = ""


@dataclass
class EmbedField(ASTNode):
    """Field inside an embed block: field "name" "value" inline=true."""
    name: ASTNode = field(default_factory=ASTNode)
    value: ASTNode = field(default_factory=ASTNode)
    inline: ASTNode = field(default_factory=lambda: Literal(value=False))


@dataclass
class EmbedBlock(ASTNode):
    """Embed constructor block."""
    title: Optional[ASTNode] = None
    description: Optional[ASTNode] = None
    color: Optional[ASTNode] = None
    thumbnail: Optional[ASTNode] = None
    image: Optional[ASTNode] = None
    footer: Optional[ASTNode] = None
    fields: List[EmbedField] = field(default_factory=list)


# ============================================================================
# Interactive UI Components (Buttons & Select Menus)
# ============================================================================

@dataclass
class ButtonItem(ASTNode):
    """Interactive Button component."""
    custom_id: ASTNode = field(default_factory=ASTNode)
    label: Optional[ASTNode] = None
    style: Optional[ASTNode] = None
    emoji: Optional[ASTNode] = None
    url: Optional[ASTNode] = None
    disabled: Optional[ASTNode] = None


@dataclass
class SelectOption(ASTNode):
    """Option inside a select menu."""
    value: ASTNode = field(default_factory=ASTNode)
    label: Optional[ASTNode] = None
    description: Optional[ASTNode] = None
    emoji: Optional[ASTNode] = None
    default: Optional[ASTNode] = None


@dataclass
class SelectItem(ASTNode):
    """Interactive Select Menu component."""
    custom_id: ASTNode = field(default_factory=ASTNode)
    placeholder: Optional[ASTNode] = None
    min_values: Optional[ASTNode] = None
    max_values: Optional[ASTNode] = None
    disabled: Optional[ASTNode] = None
    options: List[SelectOption] = field(default_factory=list)


@dataclass
class ComponentBlock(ASTNode):
    """Collection of UI components attached via 'with:'."""
    items: List[ASTNode] = field(default_factory=list)


# ============================================================================
# Statements
# ============================================================================

@dataclass
class Statement(ASTNode):
    """Base statement node."""
    pass


@dataclass
class Block(Statement):
    """A suite of statements."""
    statements: List[Statement] = field(default_factory=list)


@dataclass
class BotDecl(Statement):
    """Top-level bot name declaration: bot "MyBot"."""
    name: str = ""


@dataclass
class ConfigDecl(Statement):
    """Top-level config block: config: prefix = '!'."""
    settings: Dict[str, ASTNode] = field(default_factory=dict)


@dataclass
class Parameter(ASTNode):
    """Command or function parameter with optional type conversion hint and default."""
    name: str = ""
    type_hint: Optional[str] = None  # e.g. "Member", "Int", "String", "Role", "Channel"
    default_value: Optional[ASTNode] = None


@dataclass
class CommandDecl(Statement):
    """Command declaration: command warn(target: Member) mode=both: ..."""
    name: str = ""
    params: List[Parameter] = field(default_factory=list)
    body: Block = field(default_factory=Block)
    mode: str = "both"  # "both", "slash", or "prefix"
    description: str = ""


@dataclass
class EventDecl(Statement):
    """Event listener declaration: event member_join(member): ... or when someone joins: ..."""
    event_name: str = ""
    params: List[Parameter] = field(default_factory=list)
    body: Block = field(default_factory=Block)


@dataclass
class TaskDecl(Statement):
    """Periodic task declaration: task update_status every 30m: ..."""
    name: str = ""
    interval: DurationLiteral = field(default_factory=DurationLiteral)
    body: Block = field(default_factory=Block)


@dataclass
class FunctionDecl(Statement):
    """User-defined function: fn add(a, b): return a + b."""
    name: str = ""
    params: List[Parameter] = field(default_factory=list)
    body: Block = field(default_factory=Block)


@dataclass
class VarAssign(Statement):
    """Variable assignment: target = expr."""
    target: ASTNode = field(default_factory=ASTNode)  # Identifier, IndexAccess, or MemberAccess
    value: ASTNode = field(default_factory=ASTNode)


@dataclass
class CompoundAssign(Statement):
    """Compound assignment: target += expr."""
    target: ASTNode = field(default_factory=ASTNode)
    op: str = ""  # '+', '-', '*', '/'
    value: ASTNode = field(default_factory=ASTNode)


@dataclass
class IfStmt(Statement):
    """If statement with optional elif and else clauses."""
    condition: ASTNode = field(default_factory=ASTNode)
    then_body: Block = field(default_factory=Block)
    elif_branches: List[tuple] = field(default_factory=list)  # List of (ASTNode condition, Block body)
    else_body: Optional[Block] = None


@dataclass
class WhileStmt(Statement):
    """While loop."""
    condition: ASTNode = field(default_factory=ASTNode)
    body: Block = field(default_factory=Block)


@dataclass
class ForStmt(Statement):
    """For loop: for item in items: ..."""
    var_name: str = ""
    iterable: ASTNode = field(default_factory=ASTNode)
    body: Block = field(default_factory=Block)


@dataclass
class ReturnStmt(Statement):
    """Return statement."""
    value: Optional[ASTNode] = None


@dataclass
class ReplyStmt(Statement):
    """Discord reply: reply "..." or reply embed: ... or reply ... with: ..."""
    expr: Optional[ASTNode] = None
    embed: Optional[EmbedBlock] = None
    components: Optional[ComponentBlock] = None


@dataclass
class SendStmt(Statement):
    """Discord send: send #general "hello" or send #general embed: ... or with: ..."""
    target: ASTNode = field(default_factory=ASTNode)  # ChannelRef, Identifier, or Expr
    expr: Optional[ASTNode] = None
    embed: Optional[EmbedBlock] = None
    components: Optional[ComponentBlock] = None


@dataclass
class DeleteStmt(Statement):
    """Discord delete: delete [message]."""
    target: Optional[ASTNode] = None


@dataclass
class RequireStmt(Statement):
    """Pre-condition requirement: require permission moderate_members."""
    kind: str = "permission"  # "permission", "role", "owner"
    value: str = ""


@dataclass
class CooldownStmt(Statement):
    """Rate limit cooldown: cooldown 5s per user|guild|channel."""
    duration: DurationLiteral = field(default_factory=DurationLiteral)
    per: str = "user"  # "user", "guild", "channel"


@dataclass
class AskStmt(Statement):
    """Interactive input prompt: ask for <var> [prompt] [timeout=60s]."""
    var_name: str = ""
    prompt: Optional[ASTNode] = None
    timeout: Optional[DurationLiteral] = None


@dataclass
class ModeStmt(Statement):
    """Command modality override inside body: mode slash|prefix|both."""
    mode: str = "both"


@dataclass
class ExprStmt(Statement):
    """Expression as a statement."""
    expr: ASTNode = field(default_factory=ASTNode)


@dataclass
class PassStmt(Statement):
    """No-op statement."""
    pass


@dataclass
class Program(ASTNode):
    """Complete Cord program (file)."""
    statements: List[Statement] = field(default_factory=list)
