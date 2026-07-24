"""W1-1 · Function 表达式引擎。

提供表达式 词法分析 → 递归下降语法分析 → 求值 / 类型推导 的纯 Python 实现，
不依赖 FastAPI，便于单测与后续 W1-10 沙箱复用。

详见 docs/palantier/20_tech/220tech_function-engine.md。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Union


# --------------------------------------------------------------------------- #
# 错误模型
# --------------------------------------------------------------------------- #
class FunctionError(Exception):
    """表达式引擎错误。code 稳定，供 API 层映射为 ApiError。"""

    def __init__(
        self,
        code: str,
        message: str,
        position: Optional[int] = None,
        detail: Optional[dict[str, Any]] = None,
    ) -> None:
        self.code = code
        self.message = message
        self.position = position
        self.detail = detail
        super().__init__(message)


MAX_EXPRESSION_LEN = 4096


# --------------------------------------------------------------------------- #
# AST
# --------------------------------------------------------------------------- #
@dataclass
class Literal:
    value: Any
    type: str  # "number" | "string" | "boolean" | "null"


@dataclass
class Identifier:
    name: str


@dataclass
class PropertyAccess:
    obj: "Expr"
    attr: str
    safe: bool = False


@dataclass
class FunctionCall:
    name: str
    args: list["Expr"]


@dataclass
class BinaryOp:
    op: str
    left: "Expr"
    right: "Expr"


@dataclass
class UnaryOp:
    op: str
    operand: "Expr"


@dataclass
class Conditional:
    cond: "Expr"
    then: "Expr"
    else_: "Expr"


Expr = Union[Literal, Identifier, PropertyAccess, FunctionCall, BinaryOp, UnaryOp, Conditional]


# --------------------------------------------------------------------------- #
# 词法分析
# --------------------------------------------------------------------------- #
_TWO_CHAR_OPS = {">=", "<=", "==", "!=", "&&", "||"}
_SINGLE_OPS = set("+-*/<>!")
_KEYWORDS = {"if", "then", "else", "true", "false", "null"}


@dataclass
class Token:
    type: str
    value: str
    position: int


class Lexer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.i = 0
        self.n = len(text)

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.i < self.n:
            c = self.text[self.i]
            if c in " \t\r\n":
                self.i += 1
                continue
            if c == '"':
                tokens.append(self._read_string())
                continue
            if c.isdigit() or (c == "." and self.i + 1 < self.n and self.text[self.i + 1].isdigit()):
                tokens.append(self._read_number())
                continue
            if c.isalpha() or c == "_":
                tokens.append(self._read_ident())
                continue
            tok = self._read_operator()
            if tok is not None:
                tokens.append(tok)
                continue
            raise FunctionError("PARSE_ERROR", f"非法字符 {c!r}", self.i)
        tokens.append(Token("EOF", "", self.n))
        return tokens

    def _read_string(self) -> Token:
        start = self.i
        self.i += 1  # 跳过开引号
        buf: list[str] = []
        while self.i < self.n:
            c = self.text[self.i]
            if c == "\\" and self.i + 1 < self.n:
                nxt = self.text[self.i + 1]
                buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
                self.i += 2
                continue
            if c == '"':
                self.i += 1
                return Token("STRING", "".join(buf), start)
            buf.append(c)
            self.i += 1
        raise FunctionError("PARSE_ERROR", "字符串未闭合", start)

    def _read_number(self) -> Token:
        start = self.i
        seen_dot = False
        while self.i < self.n and (self.text[self.i].isdigit() or self.text[self.i] == "."):
            if self.text[self.i] == ".":
                if seen_dot:
                    break
                seen_dot = True
            self.i += 1
        return Token("NUMBER", self.text[start:self.i], start)

    def _read_ident(self) -> Token:
        start = self.i
        while self.i < self.n and (self.text[self.i].isalnum() or self.text[self.i] == "_"):
            self.i += 1
        word = self.text[start:self.i]
        if word in _KEYWORDS:
            return Token(word.upper(), word, start)
        return Token("IDENT", word, start)

    def _read_operator(self) -> Optional[Token]:
        two = self.text[self.i:self.i + 2]
        if two == "?.":
            self.i += 2
            return Token("QDOT", two, self.i - 2)
        c = self.text[self.i]
        if two in _TWO_CHAR_OPS:
            self.i += 2
            return Token("OP", two, self.i - 2)
        if c in _SINGLE_OPS:
            self.i += 1
            return Token("OP", c, self.i - 1)
        simple = {"(": "LPAREN", ")": "RPAREN", ".": "DOT", ",": "COMMA"}
        if c in simple:
            self.i += 1
            return Token(simple[c], c, self.i - 1)
        return None


# --------------------------------------------------------------------------- #
# 语法分析（递归下降）
# --------------------------------------------------------------------------- #
class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0

    def parse(self) -> Expr:
        node = self._conditional()
        if self._peek().type != "EOF":
            raise FunctionError("PARSE_ERROR", "表达式末尾存在多余内容", self._peek().position)
        return node

    def _peek(self) -> Token:
        return self.tokens[self.i]

    def _advance(self) -> Token:
        tok = self.tokens[self.i]
        self.i += 1
        return tok

    def _expect(self, ttype: str) -> Token:
        tok = self._peek()
        if tok.type != ttype:
            raise FunctionError("PARSE_ERROR", f"期望 {ttype} 但遇到 {tok.type}", tok.position)
        return self._advance()

    def _conditional(self) -> Expr:
        if self._peek().type == "IF":
            pos = self._advance().position
            cond = self._conditional()
            self._expect("THEN")
            then = self._conditional()
            self._expect("ELSE")
            else_ = self._conditional()
            return Conditional(cond, then, else_)
        return self._logic_or()

    def _logic_or(self) -> Expr:
        left = self._logic_and()
        while self._peek().type == "OP" and self._peek().value == "||":
            op = self._advance().value
            right = self._logic_and()
            left = BinaryOp(op, left, right)
        return left

    def _logic_and(self) -> Expr:
        left = self._equality()
        while self._peek().type == "OP" and self._peek().value == "&&":
            op = self._advance().value
            right = self._equality()
            left = BinaryOp(op, left, right)
        return left

    def _equality(self) -> Expr:
        left = self._comparison()
        while self._peek().type == "OP" and self._peek().value in ("==", "!="):
            op = self._advance().value
            right = self._comparison()
            left = BinaryOp(op, left, right)
        return left

    def _comparison(self) -> Expr:
        left = self._additive()
        while self._peek().type == "OP" and self._peek().value in (">", "<", ">=", "<="):
            op = self._advance().value
            right = self._additive()
            left = BinaryOp(op, left, right)
        return left

    def _additive(self) -> Expr:
        left = self._multiplicative()
        while self._peek().type == "OP" and self._peek().value in ("+", "-"):
            op = self._advance().value
            right = self._multiplicative()
            left = BinaryOp(op, left, right)
        return left

    def _multiplicative(self) -> Expr:
        left = self._unary()
        while self._peek().type == "OP" and self._peek().value in ("*", "/"):
            op = self._advance().value
            right = self._unary()
            left = BinaryOp(op, left, right)
        return left

    def _unary(self) -> Expr:
        if self._peek().type == "OP" and self._peek().value in ("!", "-"):
            op = self._advance().value
            return UnaryOp(op, self._unary())
        return self._postfix()

    def _postfix(self) -> Expr:
        node = self._primary()
        while True:
            t = self._peek()
            if t.type == "DOT":
                self._advance()
                attr_tok = self._expect("IDENT")
                node = PropertyAccess(node, attr_tok.value, safe=False)
            elif t.type == "QDOT":
                self._advance()
                attr_tok = self._expect("IDENT")
                node = PropertyAccess(node, attr_tok.value, safe=True)
            elif t.type == "LPAREN":
                if isinstance(node, Identifier):
                    fn_name = node.name
                    base: list[Expr] = []
                elif isinstance(node, PropertyAccess):
                    fn_name = node.attr
                    base = [node.obj]
                else:
                    raise FunctionError("PARSE_ERROR", "仅标识符或属性可作为函数调用", t.position)
                self._advance()
                args = list(base)
                if self._peek().type != "RPAREN":
                    args.append(self._conditional())
                    while self._peek().type == "COMMA":
                        self._advance()
                        args.append(self._conditional())
                self._expect("RPAREN")
                node = FunctionCall(fn_name, args)
            else:
                break
        return node

    def _primary(self) -> Expr:
        t = self._peek()
        if t.type == "NUMBER":
            self._advance()
            val: Any = float(t.value) if "." in t.value else int(t.value)
            return Literal(val, "number")
        if t.type == "STRING":
            self._advance()
            return Literal(t.value, "string")
        if t.type == "TRUE":
            self._advance()
            return Literal(True, "boolean")
        if t.type == "FALSE":
            self._advance()
            return Literal(False, "boolean")
        if t.type == "NULL":
            self._advance()
            return Literal(None, "null")
        if t.type == "IDENT":
            self._advance()
            return Identifier(t.value)
        if t.type == "LPAREN":
            self._advance()
            node = self._conditional()
            self._expect("RPAREN")
            return node
        raise FunctionError("PARSE_ERROR", f"意外的 token {t.type}", t.position)


# --------------------------------------------------------------------------- #
# 求值
# --------------------------------------------------------------------------- #
def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


class Evaluator:
    def __init__(self, object_resolver: Optional[Callable[[str], Any]] = None) -> None:
        self.object_resolver = object_resolver
        self._extra_funcs: dict[str, Callable[[list[Any], "Evaluator"], Any]] = {}

    def register_function(self, name: str, fn: Callable[[list[Any], "Evaluator"], Any]) -> None:
        self._extra_funcs[name] = fn

    def eval(self, expr: Expr, context: dict[str, Any]) -> Any:
        method = getattr(self, "_eval_" + type(expr).__name__)
        return method(expr, context)

    def _eval_Literal(self, node: Literal, context: dict[str, Any]) -> Any:
        return node.value

    def _eval_Identifier(self, node: Identifier, context: dict[str, Any]) -> Any:
        if node.name not in context:
            raise FunctionError("UNDEFINED_VAR", f"未定义的变量 {node.name!r}")
        return context[node.name]

    def _eval_PropertyAccess(self, node: PropertyAccess, context: dict[str, Any]) -> Any:
        obj = self.eval(node.obj, context)
        if obj is None:
            if node.safe:
                return None
            raise FunctionError("NULL_DEREF", f"无法对 null 访问属性 {node.attr!r}")
        if isinstance(obj, dict):
            return obj.get(node.attr)
        # Ontology 对象：优先 get_property 方法
        getter = getattr(obj, "get_property", None)
        if callable(getter):
            return getter(node.attr)
        return getattr(obj, node.attr, None)

    def _eval_FunctionCall(self, node: FunctionCall, context: dict[str, Any]) -> Any:
        args = [self.eval(a, context) for a in node.args]
        fn = self._extra_funcs.get(node.name) or _BUILTINS.get(node.name)
        if fn is None:
            raise FunctionError("UNDEFINED_FUNCTION", f"未定义的函数 {node.name!r}")
        return fn(args, self)

    def _eval_BinaryOp(self, node: BinaryOp, context: dict[str, Any]) -> Any:
        op = node.op
        if op == "&&":
            return bool(self.eval(node.left, context)) and bool(self.eval(node.right, context))
        if op == "||":
            return bool(self.eval(node.left, context)) or bool(self.eval(node.right, context))
        left = self.eval(node.left, context)
        right = self.eval(node.right, context)
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op in (">", "<", ">=", "<="):
            self._require_same_compare_type(left, right, op)
            if op == ">":
                return left > right
            if op == "<":
                return left < right
            if op == ">=":
                return left >= right
            return left <= right
        if op == "+":
            if isinstance(left, str) and isinstance(right, str):
                return left + right
            if _is_number(left) and _is_number(right):
                return left + right
            raise FunctionError(
                "TYPE_MISMATCH",
                f"运算符 + 不支持 {_type_name(left)} 与 {_type_name(right)}",
            )
        if op == "-":
            self._require_numbers(left, right, op)
            return left - right
        if op == "*":
            self._require_numbers(left, right, op)
            return left * right
        if op == "/":
            self._require_numbers(left, right, op)
            if right == 0:
                raise FunctionError("DIVISION_BY_ZERO", "除零错误")
            return left / right
        raise FunctionError("PARSE_ERROR", f"未知运算符 {op}")

    @staticmethod
    def _require_numbers(left: Any, right: Any, op: str) -> None:
        if not (_is_number(left) and _is_number(right)):
            raise FunctionError(
                "TYPE_MISMATCH", f"运算符 {op} 需要 number，实际 {_type_name(left)} 与 {_type_name(right)}"
            )

    @staticmethod
    def _require_same_compare_type(left: Any, right: Any, op: str) -> None:
        same = (_is_number(left) and _is_number(right)) or (isinstance(left, str) and isinstance(right, str))
        if not same:
            raise FunctionError(
                "TYPE_MISMATCH",
                f"运算符 {op} 需要同类型，实际 {_type_name(left)} 与 {_type_name(right)}",
            )

    def _eval_UnaryOp(self, node: UnaryOp, context: dict[str, Any]) -> Any:
        val = self.eval(node.operand, context)
        if node.op == "!":
            if not isinstance(val, bool):
                raise FunctionError("TYPE_MISMATCH", f"运算符 ! 需要 boolean，实际 {_type_name(val)}")
            return not val
        if node.op == "-":
            if not _is_number(val):
                raise FunctionError("TYPE_MISMATCH", f"运算符 - 需要 number，实际 {_type_name(val)}")
            return -val
        raise FunctionError("PARSE_ERROR", f"未知一元运算符 {node.op}")

    def _eval_Conditional(self, node: Conditional, context: dict[str, Any]) -> Any:
        cond = self.eval(node.cond, context)
        return self.eval(node.then, context) if cond else self.eval(node.else_, context)


def _type_name(x: Any) -> str:
    if x is None:
        return "null"
    if isinstance(x, bool):
        return "boolean"
    if isinstance(x, (int, float)):
        return "number"
    if isinstance(x, str):
        return "string"
    if isinstance(x, (list, tuple)):
        return "array"
    return "object"


# --------------------------------------------------------------------------- #
# 内置函数
# --------------------------------------------------------------------------- #
def _builtin_get_property(args: list[Any], ev: Evaluator) -> Any:
    if len(args) != 2:
        raise FunctionError("TYPE_MISMATCH", "getProperty 需要 2 个参数 (obj, name)")
    obj, name = args
    if obj is None:
        raise FunctionError("NULL_DEREF", "getProperty 的对象为 null")
    if isinstance(obj, dict):
        return obj.get(name)
    getter = getattr(obj, "get_property", None)
    if callable(getter):
        return getter(name)
    return getattr(obj, name, None)


def _builtin_link(args: list[Any], ev: Evaluator) -> Any:
    if len(args) != 2:
        raise FunctionError("TYPE_MISMATCH", "link 需要 2 个参数 (obj, link_name)")
    obj, name = args
    if obj is None:
        raise FunctionError("NULL_DEREF", "link 的对象为 null")
    linker = getattr(obj, "link", None)
    if callable(linker):
        return linker(name)
    raise FunctionError("TYPE_MISMATCH", f"对象不支持 link 操作")


def _builtin_len(args: list[Any], ev: Evaluator) -> Any:
    if len(args) != 1:
        raise FunctionError("TYPE_MISMATCH", "len 需要 1 个参数")
    val = args[0]
    if isinstance(val, (str, list, tuple, dict)):
        return len(val)
    raise FunctionError("TYPE_MISMATCH", f"len 不支持 {_type_name(val)}")


def _builtin_upper(args: list[Any], ev: Evaluator) -> Any:
    _require_str("upper", args)
    return args[0].upper()


def _builtin_lower(args: list[Any], ev: Evaluator) -> Any:
    _require_str("lower", args)
    return args[0].lower()


def _builtin_to_string(args: list[Any], ev: Evaluator) -> Any:
    if len(args) != 1:
        raise FunctionError("TYPE_MISMATCH", "toString 需要 1 个参数")
    val = args[0]
    if isinstance(val, bool):
        return "true" if val else "false"
    if val is None:
        return "null"
    return str(val)


def _require_str(name: str, args: list[Any]) -> None:
    if len(args) != 1 or not isinstance(args[0], str):
        raise FunctionError("TYPE_MISMATCH", f"{name} 需要 1 个 string 参数")


_BUILTINS: dict[str, Callable[[list[Any], Evaluator], Any]] = {
    "getProperty": _builtin_get_property,
    "link": _builtin_link,
    "len": _builtin_len,
    "upper": _builtin_upper,
    "lower": _builtin_lower,
    "toString": _builtin_to_string,
}


# --------------------------------------------------------------------------- #
# 类型推导
# --------------------------------------------------------------------------- #
class TypeInferer:
    def __init__(self, context_schema: Optional[dict[str, str]] = None) -> None:
        self.context_schema = context_schema or {}
        self.errors: list[FunctionError] = []

    def infer(self, expr: Expr) -> str:
        method = getattr(self, "_infer_" + type(expr).__name__)
        return method(expr)

    def _infer_Literal(self, node: Literal) -> str:
        return node.type

    def _infer_Identifier(self, node: Identifier) -> str:
        return self.context_schema.get(node.name, "any")

    def _infer_PropertyAccess(self, node: PropertyAccess) -> str:
        return "any"

    def _infer_FunctionCall(self, node: FunctionCall) -> str:
        returns = {"len": "number", "upper": "string", "lower": "string", "toString": "string"}
        return returns.get(node.name, "any")

    def _infer_BinaryOp(self, node: BinaryOp) -> str:
        if node.op in ("&&", "||", "==", "!=", ">", "<", ">=", "<="):
            return "boolean"
        left = self.infer(node.left)
        right = self.infer(node.right)
        if node.op == "+":
            if left == "string" and right == "string":
                return "string"
            if left == "number" and right == "number":
                return "number"
            if "any" in (left, right):
                return "any"
            self.errors.append(
                FunctionError("TYPE_MISMATCH", f"运算符 + 不支持 {left} 与 {right}")
            )
            return "any"
        return "number"

    def _infer_UnaryOp(self, node: UnaryOp) -> str:
        return "boolean" if node.op == "!" else "number"

    def _infer_Conditional(self, node: Conditional) -> str:
        then_t = self.infer(node.then)
        else_t = self.infer(node.else_)
        if then_t == else_t:
            return then_t
        if "any" in (then_t, else_t):
            return then_t if then_t != "any" else else_t
        self.errors.append(
            FunctionError("TYPE_MISMATCH", f"条件分支类型不一致 {then_t} vs {else_t}")
        )
        return then_t


# --------------------------------------------------------------------------- #
# 顶层 API
# --------------------------------------------------------------------------- #
def parse(text: str) -> Expr:
    if len(text) > MAX_EXPRESSION_LEN:
        raise FunctionError("PARSE_ERROR", f"表达式超过最大长度 {MAX_EXPRESSION_LEN}")
    return Parser(Lexer(text).tokenize()).parse()


def evaluate(expr: Expr, context: Optional[dict[str, Any]] = None) -> Any:
    return Evaluator().eval(expr, context or {})


def infer_type(expr: Expr, context_schema: Optional[dict[str, str]] = None) -> str:
    return TypeInferer(context_schema).infer(expr)
