"""Poor man's undefined-name checker (no external linters needed)."""
import ast, builtins, pathlib, sys

BUILTINS = set(dir(builtins)) | {"__file__", "__name__"}

def targets(node, out):
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.arg):
            out.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                out.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)

def check(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set(BUILTINS)
    targets(tree, names)  # generous: every binding anywhere counts
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in names:
            bad.append((n.lineno, n.id))
    return bad

rc = 0
for p in sorted(pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").rglob("*.py")):
    for line, name in check(p):
        print(f"{p}:{line}: undefined name {name!r}")
        rc = 1
sys.exit(rc)
