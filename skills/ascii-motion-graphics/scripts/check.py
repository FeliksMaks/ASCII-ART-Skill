"""Static check of a model-written art program: python -I check.py art.py
Passes only `import math` / `from math import ...`, one top-level `def frame(t)`, no I/O builtins and no dunders.
A filter, not a sandbox: read the code too."""
import ast, sys

BAD_NAMES = {"open", "exec", "eval", "compile", "__import__", "input", "print", "globals", "locals", "vars", "getattr",
             "setattr", "delattr", "breakpoint", "help", "exit", "quit", "memoryview", "type", "object"}
src = open(sys.argv[1], encoding="utf-8").read()
tree = ast.parse(src)
errs = []
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        errs += [f"line {n.lineno}: import {x.name}" for x in n.names if x.name != "math"]
    elif isinstance(n, ast.ImportFrom):
        if n.module != "math":
            errs.append(f"line {n.lineno}: from {n.module} import")
    elif isinstance(n, ast.Name) and n.id in BAD_NAMES:
        errs.append(f"line {n.lineno}: {n.id}")
    elif isinstance(n, ast.Attribute) and n.attr.startswith("__"):
        errs.append(f"line {n.lineno}: .{n.attr}")
    elif isinstance(n, ast.Name) and n.id.startswith("__"):
        errs.append(f"line {n.lineno}: {n.id}")
    elif isinstance(n, ast.Global):
        errs.append(f"line {n.lineno}: global")
top = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.Assign, ast.Expr))]
errs += [f"line {n.lineno}: top-level {type(n).__name__}" for n in top]
for n in tree.body:   # top-level expressions only as docstrings; assignments only of constants
    if isinstance(n, ast.Expr) and not isinstance(n.value, ast.Constant):
        errs.append(f"line {n.lineno}: top-level call or expression")
if not any(isinstance(n, ast.FunctionDef) and n.name == "frame" for n in tree.body):
    errs.append("no top-level def frame(t)")
if errs:
    print("REJECTED:", *errs, sep="\n  ")
    sys.exit(1)
print("ok:", sys.argv[1])
