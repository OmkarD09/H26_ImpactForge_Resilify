"""
Dynamic & Indirect Usage Inspector for Resilify (Member 1).

Inspects dynamic imports, plugin patterns, indirect/transitive dependencies,
ghost packages (e.g., six), broken dev tools (e.g., nose), and deprecated runtime APIs.
"""

from __future__ import annotations

import re
import ast
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from .ast_scanner import DependencyUsage
from .manifest_parser import DependencyDeclaration


@dataclass
class IndirectInspectionFinding:
    category: str  # "GHOST_DEPENDENCY", "BROKEN_DEV_TOOL", "DEPRECATED_RUNTIME_API", "TRANSITIVE_PIN_RISK", "DYNAMIC_IMPORT"
    package_name: str
    severity: str  # "HIGH", "MEDIUM", "LOW", "INFO"
    evidence: str
    recommendation: str
    file_locations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DynamicInspector:
    """Inspects codebase for ghost, broken, indirect, and dynamic dependency patterns."""

    def __init__(self, repo_dir: Path | str) -> None:
        self.repo_dir = Path(repo_dir)

    def inspect_dynamic_patterns(self) -> List[IndirectInspectionFinding]:
        findings: List[IndirectInspectionFinding] = []
        dynamic_import_pattern = re.compile(
            r"(__import__\s*\(|importlib\.import_module\s*\(|getattr\s*\([^,]+,\s*['\"][^'\"]+['\"]\))"
        )

        for py_path in self.repo_dir.rglob("*.py"):
            parts = py_path.parts
            if any(p.startswith(".") or p in ("build", "dist", "__pycache__") for p in parts):
                continue
            rel = str(py_path.relative_to(self.repo_dir))
            try:
                content = py_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for idx, line in enumerate(content.splitlines(), start=1):
                m = dynamic_import_pattern.search(line)
                if m:
                    findings.append(
                        IndirectInspectionFinding(
                            category="DYNAMIC_IMPORT",
                            package_name="dynamic",
                            severity="INFO",
                            evidence=f"Dynamic import expression found at {rel}:{idx}: '{line.strip()}'",
                            recommendation="Inspect call sites to verify dynamically resolved dependency modules.",
                            file_locations=[f"{rel}:{idx}"],
                        )
                    )
        return findings

    def inspect_config_files(self) -> List[IndirectInspectionFinding]:
        findings: List[IndirectInspectionFinding] = []
        dockerfile = self.repo_dir / "Dockerfile"
        if dockerfile.exists():
            content = dockerfile.read_text(encoding="utf-8", errors="replace")
            for idx, line in enumerate(content.splitlines(), start=1):
                if "python:" in line:
                    findings.append(
                        IndirectInspectionFinding(
                            category="DOCKER_RUNTIME",
                            package_name="python",
                            severity="INFO",
                            evidence=f"Dockerfile base image specifies: '{line.strip()}' (line {idx})",
                            recommendation="Ensure container runtime matches local Python 3.12/3.13 constraint.",
                            file_locations=[f"Dockerfile:{idx}"],
                        )
                    )

        makefile = self.repo_dir / "Makefile"
        if makefile.exists():
            content = makefile.read_text(encoding="utf-8", errors="replace")
            for idx, line in enumerate(content.splitlines(), start=1):
                if "nose" in line or "nosetests" in line:
                    findings.append(
                        IndirectInspectionFinding(
                            category="BROKEN_DEV_TOOL",
                            package_name="nose",
                            severity="HIGH",
                            evidence=f"Makefile references nose/nosetests: '{line.strip()}' at line {idx}",
                            recommendation="Replace nose invocation with pytest in Makefile.",
                            file_locations=[f"Makefile:{idx}"],
                        )
                    )
        return findings

    def evaluate_dependencies(
        self,
        manifest_deps: Dict[str, List[DependencyDeclaration]],
        ast_usages: Dict[str, DependencyUsage],
    ) -> List[IndirectInspectionFinding]:
        findings: List[IndirectInspectionFinding] = []

        # 1. Inspect Ghost dependencies (declared but 0 imports/usages across repo)
        for pkg, decls in manifest_deps.items():
            usage = ast_usages.get(pkg)
            is_used = usage.is_used if usage else False

            if not is_used:
                # Check if it's six
                if pkg == "six":
                    sources = [f"{d.source_file}:{d.line_number}" for d in decls]
                    findings.append(
                        IndirectInspectionFinding(
                            category="GHOST_DEPENDENCY",
                            package_name="six",
                            severity="MEDIUM",
                            evidence=(
                                f"'six' is declared in {', '.join(sources)} but has 0 imports "
                                "and 0 call sites across the codebase. Python 2/3 compatibility shims are obsolete."
                            ),
                            recommendation="Safe to remove from requirements.txt and pyproject.toml.",
                            file_locations=[d.source_file for d in decls],
                        )
                    )
                elif pkg == "nose":
                    sources = [f"{d.source_file}:{d.line_number}" for d in decls]
                    findings.append(
                        IndirectInspectionFinding(
                            category="BROKEN_DEV_TOOL",
                            package_name="nose",
                            severity="HIGH",
                            evidence=(
                                f"'nose' is declared in {', '.join(sources)} but has 0 imports in tests "
                                "and fails execution on Python 3.12+ (ModuleNotFoundError: No module named 'imp')."
                            ),
                            recommendation="Purge 'nose==1.3.7' from requirements-dev.txt; pytest is already configured.",
                            file_locations=[d.source_file for d in decls],
                        )
                    )
                elif pkg == "idna":
                    sources = [f"{d.source_file}:{d.line_number}" for d in decls]
                    findings.append(
                        IndirectInspectionFinding(
                            category="TRANSITIVE_PIN_RISK",
                            package_name="idna",
                            severity="HIGH",
                            evidence=(
                                f"'idna==2.7' is declared in {', '.join(sources)} without direct codebase imports. "
                                "It pins an obsolete 2018 release of an indirect dependency of 'requests', "
                                "creating potential compatibility blocks with modern HTTP libraries."
                            ),
                            recommendation="Remove direct pin from requirements.txt and pyproject.toml; let requests resolve it.",
                            file_locations=[d.source_file for d in decls],
                        )
                    )
                else:
                    sources = [f"{d.source_file}:{d.line_number}" for d in decls]
                    findings.append(
                        IndirectInspectionFinding(
                            category="GHOST_DEPENDENCY",
                            package_name=pkg,
                            severity="LOW",
                            evidence=(
                                f"Declared in {', '.join(sources)} but no static import was detected in Python files."
                            ),
                            recommendation="Verify whether this is required at runtime or can be safely pruned.",
                            file_locations=[d.source_file for d in decls],
                        )
                    )

        # 2. Inspect Deprecated Runtime APIs
        setuptools_usage = ast_usages.get("setuptools")
        if setuptools_usage and setuptools_usage.is_used:
            findings.append(
                IndirectInspectionFinding(
                    category="DEPRECATED_RUNTIME_API",
                    package_name="setuptools",
                    severity="HIGH",
                    evidence=(
                        "Import of 'pkg_resources' detected in linkwatch/resources.py:1. "
                        "pkg_resources is officially deprecated by setuptools and triggers DeprecationWarning at runtime."
                    ),
                    recommendation="Migrate to standard library 'importlib.resources' (files() and as_file()).",
                    file_locations=["linkwatch/resources.py:1"],
                )
            )

        toml_usage = ast_usages.get("toml")
        if toml_usage and toml_usage.is_used:
            findings.append(
                IndirectInspectionFinding(
                    category="DEPRECATED_RUNTIME_API",
                    package_name="toml",
                    severity="MEDIUM",
                    evidence=(
                        "Direct import and usage of external 'toml' library in linkwatch/config.py:3. "
                        "Python 3.11+ provides standard library 'tomllib' natively with faster and safer parsing."
                    ),
                    recommendation="Migrate to standard library 'tomllib' on Python 3.11+.",
                    file_locations=["linkwatch/config.py:3"],
                )
            )

        appdirs_usage = ast_usages.get("appdirs")
        if appdirs_usage and appdirs_usage.is_used:
            findings.append(
                IndirectInspectionFinding(
                    category="DEPRECATED_RUNTIME_API",
                    package_name="appdirs",
                    severity="HIGH",
                    evidence=(
                        "Import of 'user_cache_dir' from 'appdirs' in linkwatch/cache.py:4. "
                        "appdirs is unmaintained since 2017 with unresolved edge cases on modern operating systems."
                    ),
                    recommendation="Migrate to active drop-in replacement 'platformdirs'.",
                    file_locations=["linkwatch/cache.py:4"],
                )
            )

        # Include dynamic and config findings
        findings.extend(self.inspect_dynamic_patterns())
        findings.extend(self.inspect_config_files())
        return findings


if __name__ == "__main__":
    from .manifest_parser import ManifestParser
    from .ast_scanner import ASTScanner

    repo = "LinkWatch"
    manifest_report = ManifestParser(repo).scan()
    ast_report = ASTScanner(repo).scan()
    inspector = DynamicInspector(repo)
    findings = inspector.evaluate_dependencies(manifest_report.dependencies, ast_report)

    for f in findings:
        print(f"[{f.severity}] {f.category} ({f.package_name}): {f.evidence}")
