"""
AST Code Scanner for Resilify (Member 1).

Parses Python AST across the repository to map exact file paths, line numbers,
import statements, imported symbols, and call-site contexts for each dependency.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Any


# Mapping of top-level import names to PyPI package names
MODULE_TO_PACKAGE = {
    "appdirs": "appdirs",
    "toml": "toml",
    "requests": "requests",
    "jinja2": "jinja2",
    "pydantic": "pydantic",
    "click": "click",
    "six": "six",
    "chardet": "chardet",
    "pkg_resources": "setuptools",
    "setuptools": "setuptools",
    "dateutil": "python-dateutil",
    "rich": "rich",
    "idna": "idna",
    "pytest": "pytest",
    "nose": "nose",
    "certifi": "certifi",
    "urllib3": "urllib3",
}


@dataclass
class CallSite:
    file_path: str
    line_number: int
    call_expression: str
    callee_name: str
    code_snippet: str


@dataclass
class ImportOccurrence:
    file_path: str
    line_number: int
    statement: str
    imported_module: str
    imported_symbols: List[str]
    package_name: str


@dataclass
class DependencyUsage:
    package_name: str
    top_level_module: str
    is_used: bool
    import_count: int
    call_count: int
    imports: List[ImportOccurrence] = field(default_factory=list)
    call_sites: List[CallSite] = field(default_factory=list)
    files_using: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ASTVisitor(ast.NodeVisitor):
    """Visits AST nodes to record imports and call sites."""

    def __init__(self, file_path: str, source_lines: List[str]) -> None:
        self.file_path = file_path
        self.source_lines = source_lines
        self.imports: List[ImportOccurrence] = []
        self.call_sites: List[CallSite] = []
        # Map local symbol/alias -> (module, original_symbol)
        self.symbol_map: Dict[str, tuple[str, str]] = {}
        # Track imported top-level modules
        self.imported_modules: Set[str] = set()

    def _get_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip()
        return ""

    def visit_Import(self, node: ast.Import) -> None:
        statement = self._get_snippet(node.lineno)
        for alias in node.names:
            top_module = alias.name.split(".")[0]
            local_name = alias.asname or alias.name
            self.imported_modules.add(top_module)
            self.symbol_map[local_name] = (top_module, alias.name)

            package = MODULE_TO_PACKAGE.get(top_module, top_module)
            self.imports.append(
                ImportOccurrence(
                    file_path=self.file_path,
                    line_number=node.lineno,
                    statement=statement,
                    imported_module=alias.name,
                    imported_symbols=[alias.name],
                    package_name=package,
                )
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        statement = self._get_snippet(node.lineno)
        if not node.module:
            self.generic_visit(node)
            return

        top_module = node.module.split(".")[0]
        self.imported_modules.add(top_module)
        symbols = [a.name for a in node.names]

        for alias in node.names:
            local_name = alias.asname or alias.name
            self.symbol_map[local_name] = (top_module, alias.name)

        package = MODULE_TO_PACKAGE.get(top_module, top_module)
        self.imports.append(
            ImportOccurrence(
                file_path=self.file_path,
                line_number=node.lineno,
                statement=statement,
                imported_module=node.module,
                imported_symbols=symbols,
                package_name=package,
            )
        )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        callee_name = ""
        matched_module = None

        if isinstance(node.func, ast.Name):
            callee_name = node.func.id
            if callee_name in self.symbol_map:
                matched_module, _ = self.symbol_map[callee_name]
        elif isinstance(node.func, ast.Attribute):
            # E.g. toml.load(...) or requests.get(...)
            parts: List[str] = []
            curr = node.func
            while isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            if isinstance(curr, ast.Name):
                parts.append(curr.id)
                parts.reverse()
                callee_name = ".".join(parts)
                root_obj = parts[0]
                if root_obj in self.symbol_map:
                    matched_module, _ = self.symbol_map[root_obj]
                elif root_obj in self.imported_modules:
                    matched_module = root_obj

        if matched_module and matched_module in MODULE_TO_PACKAGE:
            snippet = self._get_snippet(node.lineno)
            package = MODULE_TO_PACKAGE[matched_module]
            self.call_sites.append(
                CallSite(
                    file_path=self.file_path,
                    line_number=node.lineno,
                    call_expression=callee_name,
                    callee_name=callee_name,
                    code_snippet=snippet,
                )
            )

        self.generic_visit(node)


class ASTScanner:
    """Scans all Python files in a directory to build dependency usage trees."""

    def __init__(self, repo_dir: Path | str, target_packages: Optional[List[str]] = None) -> None:
        self.repo_dir = Path(repo_dir)
        self.target_packages = [p.lower() for p in (target_packages or list(MODULE_TO_PACKAGE.values()))]

    def scan(self) -> Dict[str, DependencyUsage]:
        # Initialize usage dictionary
        usages: Dict[str, DependencyUsage] = {}
        for pkg in self.target_packages:
            # find corresponding top-level module
            top_mod = pkg
            for m, p in MODULE_TO_PACKAGE.items():
                if p.lower() == pkg:
                    top_mod = m
                    break
            usages[pkg] = DependencyUsage(
                package_name=pkg,
                top_level_module=top_mod,
                is_used=False,
                import_count=0,
                call_count=0,
            )

        # Walk all .py files in repo (excluding venvs and hidden folders)
        for py_path in self.repo_dir.rglob("*.py"):
            parts = py_path.parts
            if any(p.startswith(".") or p in ("build", "dist", "__pycache__") for p in parts):
                continue

            rel_path = str(py_path.relative_to(self.repo_dir))
            try:
                content = py_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content, filename=str(py_path))
            except Exception:
                continue

            visitor = ASTVisitor(rel_path, content.splitlines())
            visitor.visit(tree)

            # Record imports
            for imp in visitor.imports:
                pkg_key = imp.package_name.lower()
                if pkg_key in usages:
                    u = usages[pkg_key]
                    u.is_used = True
                    u.import_count += 1
                    u.imports.append(imp)
                    if rel_path not in u.files_using:
                        u.files_using.append(rel_path)

            # Record call sites
            for call in visitor.call_sites:
                # Find matching package
                for mod, pkg_name in MODULE_TO_PACKAGE.items():
                    if call.callee_name.startswith(mod) or mod in visitor.symbol_map:
                        k = pkg_name.lower()
                        if k in usages:
                            u = usages[k]
                            u.call_count += 1
                            u.call_sites.append(call)
                            if rel_path not in u.files_using:
                                u.files_using.append(rel_path)
                            break

        return usages


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "LinkWatch"
    scanner = ASTScanner(target)
    results = scanner.scan()
    for pkg, u in results.items():
        print(f"[{pkg}] used={u.is_used}, imports={u.import_count}, calls={u.call_count}, files={u.files_using}")
        for imp in u.imports:
            print(f"   -> {imp.file_path}:{imp.line_number} | {imp.statement}")
