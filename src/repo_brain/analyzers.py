from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from .db import Database

LANGUAGES = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".java": "java", ".go": "go", ".rs": "rust", ".rb": "ruby",
    ".php": "php", ".cs": "csharp", ".cpp": "cpp", ".c": "c", ".h": "c",
    ".sql": "sql", ".md": "markdown", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".sh": "shell", ".ps1": "powershell", ".html": "html", ".css": "css",
}


def language_for(path: Path) -> str:
    return LANGUAGES.get(path.suffix.lower(), "unknown")


def _python_symbols(tree: ast.AST, source_hash: str) -> list[dict[str, Any]]:
    symbols: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parent = "method" if any(isinstance(p, ast.ClassDef) and node in getattr(p, "body", []) for p in ast.walk(tree) if isinstance(getattr(p, "body", None), list)) else "function"
            symbols.append({"name": node.name, "qualified_name": node.name, "symbol_type": parent, "start_line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno), "signature": node.name, "summary": "Python callable", "source_sha256": source_hash, "visibility": "private" if node.name.startswith("_") else "public"})
        elif isinstance(node, ast.ClassDef):
            symbols.append({"name": node.name, "qualified_name": node.name, "symbol_type": "class", "start_line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno), "signature": node.name, "summary": "Python class", "source_sha256": source_hash, "visibility": "public"})
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    symbols.append({"name": target.id, "qualified_name": target.id, "symbol_type": "constant", "start_line": node.lineno, "end_line": getattr(node, "end_lineno", node.lineno), "signature": target.id, "summary": "Module constant", "source_sha256": source_hash, "visibility": "public"})
    return symbols


def _python_imports(tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


JS_SYMBOL = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)|^\s*(?:export\s+)?class\s+(\w+)|^\s*(?:export\s+)?(?:interface|type)\s+(\w+)", re.MULTILINE)
JS_IMPORT = re.compile(r"(?:from\s+|import\s+|require\(\s*)['\"]([^'\"]+)['\"]")


def extract(path: Path, text: str, source_hash: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    language = language_for(path)
    if language == "python":
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return [], []
        symbols = _python_symbols(tree, source_hash)
        imports = _python_imports(tree)
        return symbols, [{"module": item, "dependency_type": "import", "label": item} for item in imports]
    if language in {"javascript", "typescript"}:
        symbols = []
        for match in JS_SYMBOL.finditer(text):
            name = next((group for group in match.groups() if group), "anonymous")
            kind = "function" if match.group(1) else "class" if match.group(2) else "type"
            line = text.count("\n", 0, match.start()) + 1
            symbols.append({"name": name, "qualified_name": name, "symbol_type": kind, "start_line": line, "end_line": line, "signature": name, "summary": "JavaScript/TypeScript symbol", "source_sha256": source_hash, "visibility": "public"})
        return symbols, [{"module": item, "dependency_type": "import", "label": item} for item in JS_IMPORT.findall(text)]
    # Generic: identify headings and common function declarations without claiming semantics.
    symbols = []
    for match in re.finditer(r"^\s*(?:def|func|fn|function)\s+(\w+)", text, re.MULTILINE):
        line = text.count("\n", 0, match.start()) + 1
        symbols.append({"name": match.group(1), "qualified_name": match.group(1), "symbol_type": "function", "start_line": line, "end_line": line, "signature": match.group(1), "summary": "Detected generic callable", "source_sha256": source_hash, "visibility": "unknown"})
    return symbols, []


def index_file(db: Database, repository_id: int, file_row: Any, root: Path) -> None:
    path = root / file_row["relative_path"]
    if file_row["category"] in {"binary", "secret", "large"} or not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    symbols, imports = extract(path, text, file_row["sha256"] or "")
    with db.transaction() as conn:
        conn.execute("DELETE FROM symbols WHERE file_id = ?", (file_row["id"],))
        conn.execute("DELETE FROM dependencies WHERE source_file_id = ?", (file_row["id"],))
        symbol_ids: dict[str, int] = {}
        for symbol in symbols:
            cur = conn.execute("""INSERT INTO symbols(file_id,name,qualified_name,symbol_type,start_line,end_line,signature,summary,source_sha256,visibility)
                VALUES (:file_id,:name,:qualified_name,:symbol_type,:start_line,:end_line,:signature,:summary,:source_sha256,:visibility)""", {**symbol, "file_id": file_row["id"]})
            symbol_ids[symbol["name"]] = int(cur.lastrowid)
        all_files = conn.execute("SELECT id, relative_path FROM files WHERE repository_id = ?", (repository_id,)).fetchall()
        by_path = {row["relative_path"]: row["id"] for row in all_files}
        by_stem = {Path(row["relative_path"]).stem: row["id"] for row in all_files}
        for dep in imports:
            module = dep["module"].replace("\\", "/")
            target = None
            if module.startswith("."):
                target = by_stem.get(module.lstrip("./").split("/")[-1])
            else:
                dotted = module.replace(".", "/")
                target = by_path.get(dotted + ".py") or by_path.get(dotted + ".ts") or by_path.get(dotted + ".js") or by_stem.get(module.split(".")[-1])
            conn.execute("""INSERT OR IGNORE INTO dependencies(source_file_id,target_file_id,dependency_type,label,confidence,source_sha256)
                VALUES (?,?,?,?,?,?)""", (file_row["id"], target, dep["dependency_type"], dep["label"], 0.8 if target else 0.3, file_row["sha256"]))
        if db.fts_available:
            conn.execute("DELETE FROM search_index WHERE kind='file' AND ref_id=?", (str(file_row["id"]),))
            body = f"{file_row['relative_path']} {file_row['basename']} {file_row['language']} {' '.join(s['name'] for s in symbols)}"
            conn.execute("INSERT INTO search_index(kind,ref_id,text) VALUES ('file',?,?)", (str(file_row["id"]), body))


def default_analysis(file_row: Any, text: str) -> dict[str, Any]:
    """Produce a conservative lexical analysis; agents can replace it with facts."""
    nonempty = [line.strip() for line in text.splitlines() if line.strip()]
    summary = f"{file_row['language'].title()} source file at {file_row['relative_path']} ({file_row['line_count']} lines)."
    responsibilities = [f"Defines {file_row['basename']} behavior"]
    if nonempty:
        responsibilities.append(f"Contains {len(nonempty)} non-empty source lines")
    return {"summary": summary, "responsibilities": responsibilities, "confidence": 0.35, "analyzer": "lexical"}
