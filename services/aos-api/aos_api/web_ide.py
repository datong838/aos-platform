"""W2-#22 · Web IDE。

基于 Web 的代码编辑器后端：会话管理 + 虚拟文件系统 + LSP 风格诊断 + IntelliSense。
诊断复用 functions_python_builder._check_code（黑名单静态检查）。

详见 docs/palantier/20_tech/220tech_w2-e-media-lineage-ide.md §2.4/§3.3。
"""
from __future__ import annotations

import ast
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["error", "warning", "info"]


class IdeDiagnostic(BaseModel):
    file: str
    line: int
    column: int = 0
    end_line: int = 0
    end_column: int = 0
    severity: Severity
    code: str
    message: str


class IdeCompletion(BaseModel):
    label: str
    kind: str = "text"
    detail: str = ""
    insert_text: str = ""


class IdeHover(BaseModel):
    file: str
    line: int
    signature: str = ""
    docstring: str = ""


class IdeSymbol(BaseModel):
    name: str
    kind: str
    file: str
    line: int
    detail: str = ""


class IdeFile(BaseModel):
    path: str
    content: str = ""
    language: str = "python"


class IdeSession(BaseModel):
    id: str = Field(default_factory=lambda: "ide-" + uuid.uuid4().hex[:8])
    name: str = "default"
    files: dict[str, IdeFile] = Field(default_factory=dict)
    open_file: str = ""
    cursor_line: int = 1
    cursor_column: int = 1


class IdeError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


_PYTHON_BUILTINS_COMPLETIONS = [
    IdeCompletion(label="len", kind="function", detail="len(obj) -> int", insert_text="len($0)"),
    IdeCompletion(label="str", kind="class", detail="str 对象", insert_text="str($0)"),
    IdeCompletion(label="int", kind="class", detail="int 对象", insert_text="int($0)"),
    IdeCompletion(label="float", kind="class", detail="float 对象", insert_text="float($0)"),
    IdeCompletion(label="bool", kind="class", detail="bool 对象", insert_text="bool($0)"),
    IdeCompletion(label="list", kind="class", detail="list 对象", insert_text="list($0)"),
    IdeCompletion(label="dict", kind="class", detail="dict 对象", insert_text="dict($0)"),
    IdeCompletion(label="range", kind="function", detail="range(n)", insert_text="range($0)"),
    IdeCompletion(label="enumerate", kind="function", detail="enumerate(iterable)", insert_text="enumerate($0)"),
    IdeCompletion(label="sorted", kind="function", detail="sorted(iterable)", insert_text="sorted($0)"),
]

_TRANSFORM_KEYWORDS = [
    IdeCompletion(label="def transform", kind="snippet", detail="定义 transform 函数", insert_text="def transform(rows):\n    return rows\n"),
    IdeCompletion(label="return", kind="keyword", insert_text="return "),
    IdeCompletion(label="for", kind="keyword", insert_text="for $0 in "),
    IdeCompletion(label="if", kind="keyword", insert_text="if $0:"),
]


class WebIdeEngine:
    """Web IDE 会话引擎：虚拟文件系统 + 诊断 + 补全 + 符号。"""

    def __init__(self) -> None:
        self._sessions: dict[str, IdeSession] = {}

    def create_session(self, name: str = "default") -> IdeSession:
        session = IdeSession(name=name)
        session.files["main.py"] = IdeFile(path="main.py", content="def transform(rows):\n    return rows\n")
        session.open_file = "main.py"
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> IdeSession:
        if session_id not in self._sessions:
            raise IdeError("SESSION_NOT_FOUND", f"会话 {session_id!r} 不存在")
        return self._sessions[session_id]

    def list_sessions(self) -> list[IdeSession]:
        return list(self._sessions.values())

    def delete_session(self, session_id: str) -> bool:
        existed = session_id in self._sessions
        self._sessions.pop(session_id, None)
        return existed

    def open_file(self, session_id: str, path: str) -> IdeFile:
        session = self.get_session(session_id)
        if path not in session.files:
            raise IdeError("FILE_NOT_FOUND", f"文件 {path!r} 不存在")
        session.open_file = path
        return session.files[path]

    def create_file(self, session_id: str, path: str, content: str = "", language: str = "python") -> IdeFile:
        session = self.get_session(session_id)
        if path in session.files:
            raise IdeError("FILE_EXISTS", f"文件 {path!r} 已存在")
        f = IdeFile(path=path, content=content, language=language)
        session.files[path] = f
        return f

    def write_file(self, session_id: str, path: str, content: str) -> IdeFile:
        session = self.get_session(session_id)
        if path not in session.files:
            session.files[path] = IdeFile(path=path)
        session.files[path].content = content
        return session.files[path]

    def delete_file(self, session_id: str, path: str) -> bool:
        session = self.get_session(session_id)
        existed = path in session.files
        session.files.pop(path, None)
        if session.open_file == path:
            session.open_file = ""
        return existed

    def list_files(self, session_id: str) -> list[IdeFile]:
        return list(self.get_session(session_id).files.values())

    def diagnostics(self, session_id: str, path: str | None = None) -> list[IdeDiagnostic]:
        session = self.get_session(session_id)
        target = path or session.open_file
        if not target or target not in session.files:
            return []
        code = session.files[target].content
        return self._check_python(target, code)

    def _check_python(self, file: str, code: str) -> list[IdeDiagnostic]:
        diags: list[IdeDiagnostic] = []
        from .functions_python_builder import _check_code
        errors = _check_code(code)
        for err in errors:
            line = 1
            col = 0
            parts = err.split(":", 1)
            code_id = "LINT"
            message = err
            if len(parts) == 2:
                code_id = parts[0].strip()
                message = parts[1].strip()
            if "line" in message.lower():
                try:
                    line_str = message.split("line")[1].strip().split()[0]
                    line = int(line_str)
                except (ValueError, IndexError):
                    pass
            diags.append(IdeDiagnostic(
                file=file, line=line, column=col, severity="error",
                code=code_id, message=message,
            ))
        return diags

    def completions(self, session_id: str, prefix: str, path: str | None = None) -> list[IdeCompletion]:
        session = self.get_session(session_id)
        target = path or session.open_file
        result: list[IdeCompletion] = []
        if target and target in session.files:
            code = session.files[target].content
            result.extend(self._ast_completions(code, prefix))
        if not prefix:
            result.extend(_PYTHON_BUILTINS_COMPLETIONS)
            result.extend(_TRANSFORM_KEYWORDS)
        else:
            lower = prefix.lower()
            result.extend(c for c in _PYTHON_BUILTINS_COMPLETIONS if lower in c.label.lower())
            result.extend(c for c in _TRANSFORM_KEYWORDS if lower in c.label.lower())
        return result

    def _ast_completions(self, code: str, prefix: str) -> list[IdeCompletion]:
        completions: list[IdeCompletion] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return completions
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not prefix or prefix.lower() in node.name.lower():
                    args = [a.arg for a in node.args.args]
                    completions.append(IdeCompletion(
                        label=node.name, kind="function",
                        detail=f"{node.name}({', '.join(args)})",
                        insert_text=f"{node.name}($0)",
                    ))
            elif isinstance(node, ast.ClassDef):
                if not prefix or prefix.lower() in node.name.lower():
                    completions.append(IdeCompletion(
                        label=node.name, kind="class",
                        detail=f"class {node.name}",
                        insert_text=f"{node.name}($0)",
                    ))
        return completions

    def symbols(self, session_id: str, path: str | None = None) -> list[IdeSymbol]:
        session = self.get_session(session_id)
        target = path or session.open_file
        if not target or target not in session.files:
            return []
        code = session.files[target].content
        symbols: list[IdeSymbol] = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return symbols
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(IdeSymbol(name=node.name, kind="function", file=target, line=node.lineno,
                                         detail=f"def {node.name}(...)"))
            elif isinstance(node, ast.ClassDef):
                symbols.append(IdeSymbol(name=node.name, kind="class", file=target, line=node.lineno))
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and (not _IDE_PREFIX or _IDE_PREFIX in t.id):
                        symbols.append(IdeSymbol(name=t.id, kind="variable", file=target, line=node.lineno))
        return symbols

    def hover(self, session_id: str, line: int, path: str | None = None) -> IdeHover:
        session = self.get_session(session_id)
        target = path or session.open_file
        if not target or target not in session.files:
            return IdeHover(file=target or "", line=line)
        code = session.files[target].content
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return IdeHover(file=target, line=line)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno == line:
                args = [a.arg for a in node.args.args]
                doc = ast.get_docstring(node) or ""
                return IdeHover(file=target, line=line,
                                signature=f"def {node.name}({', '.join(args)})",
                                docstring=doc)
        return IdeHover(file=target, line=line)


_IDE_PREFIX = ""

_engine = WebIdeEngine()


def get_engine() -> WebIdeEngine:
    return _engine
