"""
harness/port_guard.py – AST-based import and safety check for port files.

spec step 8: routines/<name>.py must define <name>(x: float) -> float.
Before import, an AST check allows:
  - `import math` and `from math import ...`
  - no other imports
  - no open, exec, eval, __import__, compile, globals, getattr on modules
  - no dunder attribute access (e.g. __class__, __dict__)
Violations -> verdict DISQUALIFIED (never hidden).
"""

import ast
import importlib.util
import sys
from pathlib import Path

# Names that are always banned as function calls
_BANNED_CALLS = {"open", "exec", "eval", "__import__", "compile", "globals", "getattr",
                 "setattr", "delattr", "vars", "locals", "breakpoint", "input", "help"}

# Introspection attributes that reach frames, code objects or other modules' globals
_BANNED_ATTR_PREFIXES = ("f_", "gi_", "cr_", "ag_", "tb_", "co_")

# Any name starting with __ is banned as an attribute
def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


class _ASTChecker(ast.NodeVisitor):
    def __init__(self):
        self.violations: list[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name != "math":
                self.violations.append(
                    f"Line {node.lineno}: import of '{alias.name}' not allowed (only 'import math')"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module != "math":
            self.violations.append(
                f"Line {node.lineno}: 'from {node.module} import ...' not allowed (only 'from math import ...')"
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Direct call to banned name: open(...), exec(...), etc.
        if isinstance(node.func, ast.Name):
            if node.func.id in _BANNED_CALLS:
                self.violations.append(
                    f"Line {node.lineno}: call to banned function '{node.func.id}'"
                )
        # Attribute call: getattr(x, ...) is banned above; also ban dunder attrs
        if isinstance(node.func, ast.Attribute):
            if _is_dunder(node.func.attr):
                self.violations.append(
                    f"Line {node.lineno}: call via dunder attribute '{node.func.attr}'"
                )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if _is_dunder(node.attr):
            self.violations.append(
                f"Line {getattr(node, 'lineno', '?')}: access to dunder attribute '{node.attr}'"
            )
        elif node.attr.startswith(_BANNED_ATTR_PREFIXES):
            self.violations.append(
                f"Line {getattr(node, 'lineno', '?')}: introspection attribute '{node.attr}' not allowed"
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        # __builtins__, __loader__, __spec__ ... and banned builtins used by name
        if _is_dunder(node.id) or node.id in _BANNED_CALLS:
            self.violations.append(
                f"Line {getattr(node, 'lineno', '?')}: name '{node.id}' not allowed"
            )
        self.generic_visit(node)


def check_port_ast(path: str) -> tuple[bool, str]:
    """Return (ok, reason).  ok=True means the file passes; False means DISQUALIFIED."""
    try:
        source = Path(path).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc}"
    except Exception as exc:
        return False, f"Cannot read/parse file: {exc}"

    checker = _ASTChecker()
    checker.visit(tree)
    if checker.violations:
        return False, "; ".join(checker.violations)
    return True, ""


def load_port(path: str, name: str):
    """Load a port module after AST check.  Raises RuntimeError('DISQUALIFIED: ...') on failure."""
    ok, reason = check_port_ast(path)
    if not ok:
        raise RuntimeError(f"DISQUALIFIED: {reason}")

    spec = importlib.util.spec_from_file_location(f"routines.{name}", path)
    if spec is None:
        raise RuntimeError(f"DISQUALIFIED: cannot create module spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:
        raise RuntimeError(f"DISQUALIFIED: import error: {exc}") from exc

    fn = getattr(mod, name, None)
    if fn is None or not callable(fn):
        raise RuntimeError(f"DISQUALIFIED: module has no callable '{name}'")
    return fn
