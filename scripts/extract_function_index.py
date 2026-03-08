#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue"}
DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".idea",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "coverage",
}

JS_FUNCTION_RE = re.compile(
    r"^(?P<indent>\s*)(?:export\s+default\s+|export\s+)?"
    r"(?:(?P<async1>async)\s+)?function(?:\s*\*)?\s+(?P<name1>[A-Za-z_$][\w$]*)\s*\((?P<params1>[^)]*)\)\s*\{"
    r"|^(?P<indent2>\s*)(?:export\s+const\s+|export\s+let\s+|export\s+var\s+|const\s+|let\s+|var\s+)"
    r"(?P<name2>[A-Za-z_$][\w$]*)\s*=\s*(?:(?P<async2>async)\s+)?\((?P<params2>[^)]*)\)\s*=>\s*(?P<body2>.+)$"
    r"|^(?P<indent3>\s*)(?P<name3>[A-Za-z_$][\w$]*)\s*:\s*(?:(?P<async3>async)\s+)?function\s*\((?P<params3>[^)]*)\)\s*\{",
)
RETURN_RE = re.compile(r"\breturn\b(?P<expr>.*)")
VUE_SCRIPT_RE = re.compile(r"<script\b[^>]*>(?P<body>.*?)</script>", re.DOTALL | re.IGNORECASE)


@dataclass
class FunctionSummary:
    name: str
    signature: str
    comment: str
    returns: list[str]
    line: int
    language: str
    kind: str


@dataclass
class FileSummary:
    path: str
    language: str
    functions: list[FunctionSummary]


class ReturnCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.returns: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for stmt in node.body:
            self.visit(stmt)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        super().generic_visit(node)

    def visit_Return(self, node: ast.Return) -> None:
        if node.value is None:
            value = "None"
        else:
            value = ast.unparse(node.value)
        if value not in self.returns:
            self.returns.append(value)


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def clean_comment_block(text: str) -> str:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        line = re.sub(r"^//\s?", "", line)
        line = re.sub(r"^/\*+\s?", "", line)
        line = re.sub(r"^\*\s?", "", line)
        line = re.sub(r"\*/$", "", line)
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def collect_files(targets: list[Path], include: set[str], exclude_dirs: set[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for target in targets:
        resolved = target.resolve()
        if resolved.is_file():
            if resolved.suffix.lower() in include and not any(part in exclude_dirs for part in resolved.parts):
                if resolved not in seen:
                    seen.add(resolved)
                    yield resolved
            continue

        for path in resolved.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in include:
                continue
            if any(part in exclude_dirs for part in path.parts):
                continue
            if path in seen:
                continue
            seen.add(path)
            yield path


def python_signature(node: ast.AST, lines: list[str]) -> str:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return ""
    body_line = node.body[0].lineno if node.body else node.end_lineno or node.lineno
    header = "".join(lines[node.lineno - 1 : body_line - 1]).strip()
    return collapse_whitespace(header.rstrip(":"))


def summarize_python_file(path: Path, base_dir: Path) -> FileSummary:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    functions: list[FunctionSummary] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not hasattr(node, "lineno"):
            continue
        signature = python_signature(node, lines)
        docstring = ast.get_docstring(node) or ""
        collector = ReturnCollector()
        collector.visit(node)
        kind = "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function"
        functions.append(
            FunctionSummary(
                name=node.name,
                signature=signature,
                comment=docstring.strip(),
                returns=collector.returns,
                line=node.lineno,
                language="python",
                kind=kind,
            )
        )

    functions.sort(key=lambda item: item.line)
    return FileSummary(path=str(path.relative_to(base_dir)), language="python", functions=functions)


def extract_leading_comment(lines: list[str], start_index: int) -> str:
    block: list[str] = []
    i = start_index - 1
    in_block_comment = False

    while i >= 0:
        stripped = lines[i].strip()
        if not stripped:
            if block:
                break
            i -= 1
            continue
        if stripped.startswith("//"):
            block.append(lines[i])
            i -= 1
            continue
        if stripped.endswith("*/") or in_block_comment:
            block.append(lines[i])
            if "/*" in stripped:
                in_block_comment = False
                i -= 1
                break
            in_block_comment = True
            i -= 1
            continue
        if stripped.startswith("/*"):
            block.append(lines[i])
            i -= 1
            break
        break

    block.reverse()
    return clean_comment_block("".join(block))


def collect_js_returns(body_lines: list[str], concise_body: str | None = None) -> list[str]:
    returns: list[str] = []
    if concise_body is not None:
        body = concise_body.strip().rstrip(";")
        if body.startswith("{"):
            body_lines = [body]
        elif body:
            return [collapse_whitespace(body)]

    for line in body_lines:
        stripped = line.strip()
        match = RETURN_RE.search(stripped)
        if not match:
            continue
        expr = match.group("expr").strip().rstrip(";")
        value = collapse_whitespace(expr) if expr else "undefined"
        if value == "{":
            value = "{...}"
        if value not in returns:
            returns.append(value)
    return returns


def summarize_js_like_source(source: str, path_label: str, language: str) -> FileSummary:
    lines = source.splitlines()
    functions: list[FunctionSummary] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        match = JS_FUNCTION_RE.match(line)
        if not match:
            i += 1
            continue

        name = match.group("name1") or match.group("name2") or match.group("name3")
        params = match.group("params1") or match.group("params2") or match.group("params3") or ""
        is_async = bool(match.group("async1") or match.group("async2") or match.group("async3"))
        concise_body = match.group("body2") if match.group("name2") else None
        signature_prefix = "async " if is_async else ""
        signature = f"{signature_prefix}{name}({collapse_whitespace(params)})"
        comment = extract_leading_comment(lines, i)
        kind = "async_function" if is_async else "function"

        if concise_body is not None and not concise_body.strip().startswith("{"):
            returns = collect_js_returns([], concise_body=concise_body)
            functions.append(
                FunctionSummary(
                    name=name,
                    signature=signature,
                    comment=comment,
                    returns=returns,
                    line=i + 1,
                    language=language,
                    kind=kind,
                )
            )
            i += 1
            continue

        brace_delta = line.count("{") - line.count("}")
        body_lines: list[str] = []
        j = i + 1
        while j < len(lines):
            current = lines[j]
            brace_delta += current.count("{") - current.count("}")
            if brace_delta <= 0:
                break
            body_lines.append(current)
            j += 1

        returns = collect_js_returns(body_lines, concise_body=concise_body)
        functions.append(
            FunctionSummary(
                name=name,
                signature=signature,
                comment=comment,
                returns=returns,
                line=i + 1,
                language=language,
                kind=kind,
            )
        )
        i = j + 1

    return FileSummary(path=path_label, language=language, functions=functions)


def summarize_vue_file(path: Path, base_dir: Path) -> FileSummary:
    source = path.read_text(encoding="utf-8")
    matches = list(VUE_SCRIPT_RE.finditer(source))
    all_functions: list[FunctionSummary] = []
    for match in matches:
        script_body = match.group("body")
        summary = summarize_js_like_source(script_body, str(path.relative_to(base_dir)), "vue")
        all_functions.extend(summary.functions)
    all_functions.sort(key=lambda item: item.line)
    return FileSummary(path=str(path.relative_to(base_dir)), language="vue", functions=all_functions)


def summarize_js_file(path: Path, base_dir: Path) -> FileSummary:
    language = "typescript" if path.suffix.lower() in {".ts", ".tsx"} else "javascript"
    return summarize_js_like_source(path.read_text(encoding="utf-8"), str(path.relative_to(base_dir)), language)


def to_markdown(items: list[FileSummary]) -> str:
    lines: list[str] = []
    for item in items:
        if not item.functions:
            continue
        lines.append(f"# {item.path}")
        for func in item.functions:
            lines.append("")
            lines.append(f"- {func.signature}")
            if func.comment:
                lines.append(f"  comment: {func.comment}")
            if func.returns:
                lines.append(f"  returns: {', '.join(func.returns)}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="提取项目中每个函数的签名、注释和返回值，用于 AI 上下文压缩。")
    parser.add_argument("targets", nargs="*", default=["."], help="要扫描的文件或目录，默认当前目录")
    parser.add_argument("--format", choices=["json", "md"], default="json", help="输出格式")
    parser.add_argument("--output", help="输出文件路径；不传则打印到 stdout")
    parser.add_argument("--extensions", nargs="*", default=sorted(SUPPORTED_EXTENSIONS), help="要扫描的扩展名列表")
    parser.add_argument("--exclude-dir", action="append", default=[], help="额外排除的目录名，可重复传入")
    parser.add_argument("--skip-empty", action="store_true", help="跳过没有函数的文件")
    args = parser.parse_args()

    targets = [Path(item) for item in args.targets]
    display_root = Path.cwd().resolve()
    include = {ext if ext.startswith(".") else f".{ext}" for ext in args.extensions}
    exclude_dirs = DEFAULT_EXCLUDE_DIRS | set(args.exclude_dir)

    results: list[FileSummary] = []
    for path in sorted(collect_files(targets, include, exclude_dirs), key=lambda item: str(item)):
        try:
            if path.suffix.lower() == ".py":
                summary = summarize_python_file(path, display_root)
            elif path.suffix.lower() == ".vue":
                summary = summarize_vue_file(path, display_root)
            else:
                summary = summarize_js_file(path, display_root)
        except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
            summary = FileSummary(
                path=str(path.relative_to(display_root)),
                language=path.suffix.lower().lstrip("."),
                functions=[
                    FunctionSummary(
                        name="__parse_error__",
                        signature="",
                        comment=f"Failed to parse file: {exc}",
                        returns=[],
                        line=1,
                        language=path.suffix.lower().lstrip("."),
                        kind="error",
                    )
                ],
            )
        if args.skip_empty and not summary.functions:
            continue
        results.append(summary)

    if args.format == "json":
        payload = [
            {
                "path": item.path,
                "language": item.language,
                "functions": [asdict(func) for func in item.functions],
            }
            for item in results
        ]
        output = json.dumps(payload, ensure_ascii=False, indent=2)
    else:
        output = to_markdown(results)

    if args.output:
        Path(args.output).write_text(output + ("" if output.endswith("\n") else "\n"), encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
