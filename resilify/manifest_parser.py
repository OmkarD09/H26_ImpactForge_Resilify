"""
Manifest and Lockfile Parser for Resilify (Member 1).

Inspects requirements.txt, requirements-dev.txt, and pyproject.toml to extract
pinned versions, constraints, and detect version conflicts across manifests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import tomllib  # Python 3.11+
except ImportError:
    import toml as tomllib  # Fallback


def normalize_name(name: str) -> str:
    """Normalize package name according to PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower().strip()


@dataclass
class DependencyDeclaration:
    name: str
    normalized_name: str
    specifier: str
    is_pinned: bool
    pinned_version: Optional[str]
    source_file: str
    line_number: int
    raw_line: str
    is_dev: bool = False


@dataclass
class ManifestConflict:
    package: str
    sources: List[str]
    specifiers: List[str]
    conflict_type: str
    description: str


@dataclass
class ManifestReport:
    manifest_files_found: List[str]
    dependencies: Dict[str, List[DependencyDeclaration]]
    conflicts: List[ManifestConflict]
    total_unique_dependencies: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_files_found": self.manifest_files_found,
            "total_unique_dependencies": self.total_unique_dependencies,
            "conflicts": [asdict(c) for c in self.conflicts],
            "dependencies": {
                k: [asdict(d) for d in v] for k, v in self.dependencies.items()
            },
        }


class ManifestParser:
    """Parses Python dependency manifests and identifies cross-file inconsistencies."""

    DEP_PATTERN = re.compile(
        r"^\s*([A-Za-z0-9_\-\.]+)\s*([=><~^!].*)?$", re.IGNORECASE
    )

    def __init__(self, repo_dir: Path | str) -> None:
        self.repo_dir = Path(repo_dir)

    def parse_requirements_file(
        self, file_path: Path, is_dev: bool = False
    ) -> List[DependencyDeclaration]:
        declarations: List[DependencyDeclaration] = []
        if not file_path.exists():
            return declarations

        rel_path = str(file_path.relative_to(self.repo_dir))
        content = file_path.read_text(encoding="utf-8", errors="replace")

        for line_num, line in enumerate(content.splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Strip inline comments
            line_without_comment = stripped.split("#")[0].strip()
            if not line_without_comment:
                continue

            match = self.DEP_PATTERN.match(line_without_comment)
            if not match:
                continue

            raw_name, raw_spec = match.group(1), match.group(2) or ""
            norm = normalize_name(raw_name)
            spec = raw_spec.strip()

            is_pinned = spec.startswith("==")
            pinned_version = spec[2:].strip() if is_pinned else None

            declarations.append(
                DependencyDeclaration(
                    name=raw_name,
                    normalized_name=norm,
                    specifier=spec,
                    is_pinned=is_pinned,
                    pinned_version=pinned_version,
                    source_file=rel_path,
                    line_number=line_num,
                    raw_line=stripped,
                    is_dev=is_dev,
                )
            )

        return declarations

    def parse_pyproject_toml(
        self, file_path: Path
    ) -> List[DependencyDeclaration]:
        declarations: List[DependencyDeclaration] = []
        if not file_path.exists():
            return declarations

        rel_path = str(file_path.relative_to(self.repo_dir))
        content = file_path.read_text(encoding="utf-8", errors="replace")

        try:
            data = tomllib.loads(content)
        except Exception:
            return declarations

        # Extract [project.dependencies]
        project_deps = data.get("project", {}).get("dependencies", [])
        if isinstance(project_deps, list):
            for idx, item in enumerate(project_deps, start=1):
                item_str = str(item).strip()
                match = self.DEP_PATTERN.match(item_str)
                if not match:
                    continue

                raw_name, raw_spec = match.group(1), match.group(2) or ""
                norm = normalize_name(raw_name)
                spec = raw_spec.strip()
                is_pinned = spec.startswith("==")
                pinned_ver = spec[2:].strip() if is_pinned else None

                declarations.append(
                    DependencyDeclaration(
                        name=raw_name,
                        normalized_name=norm,
                        specifier=spec,
                        is_pinned=is_pinned,
                        pinned_version=pinned_ver,
                        source_file=rel_path,
                        line_number=idx,
                        raw_line=item_str,
                        is_dev=False,
                    )
                )

        # Also optional-dependencies if any
        opt_deps = data.get("project", {}).get("optional-dependencies", {})
        if isinstance(opt_deps, dict):
            for group, deps in opt_deps.items():
                if isinstance(deps, list):
                    for idx, item in enumerate(deps, start=1):
                        item_str = str(item).strip()
                        match = self.DEP_PATTERN.match(item_str)
                        if not match:
                            continue
                        raw_name, raw_spec = match.group(1), match.group(2) or ""
                        norm = normalize_name(raw_name)
                        spec = raw_spec.strip()
                        is_pinned = spec.startswith("==")
                        pinned_ver = spec[2:].strip() if is_pinned else None

                        declarations.append(
                            DependencyDeclaration(
                                name=raw_name,
                                normalized_name=norm,
                                specifier=spec,
                                is_pinned=is_pinned,
                                pinned_version=pinned_ver,
                                source_file=f"{rel_path} [{group}]",
                                line_number=idx,
                                raw_line=item_str,
                                is_dev=True,
                            )
                        )

        return declarations

    def scan(self) -> ManifestReport:
        found_files: List[str] = []
        all_decls: List[DependencyDeclaration] = []

        req_txt = self.repo_dir / "requirements.txt"
        if req_txt.exists():
            found_files.append(str(req_txt.relative_to(self.repo_dir)))
            all_decls.extend(self.parse_requirements_file(req_txt, is_dev=False))

        req_dev = self.repo_dir / "requirements-dev.txt"
        if req_dev.exists():
            found_files.append(str(req_dev.relative_to(self.repo_dir)))
            all_decls.extend(self.parse_requirements_file(req_dev, is_dev=True))

        pyproject = self.repo_dir / "pyproject.toml"
        if pyproject.exists():
            found_files.append(str(pyproject.relative_to(self.repo_dir)))
            all_decls.extend(self.parse_pyproject_toml(pyproject))

        # Group declarations by normalized package name
        grouped: Dict[str, List[DependencyDeclaration]] = {}
        for decl in all_decls:
            grouped.setdefault(decl.normalized_name, []).append(decl)

        # Detect conflicts across files
        conflicts: List[ManifestConflict] = []
        for pkg, decls in grouped.items():
            specs = set(d.specifier for d in decls)
            if len(specs) > 1:
                spec_list = [f"{d.source_file}: '{d.specifier}'" for d in decls]
                # Check for direct pinned vs unpinned or range mismatch
                has_strict_pin = any(d.is_pinned for d in decls)
                has_major_diff = False
                versions = [d.pinned_version for d in decls if d.is_pinned]
                unpinned_specs = [d.specifier for d in decls if not d.is_pinned]

                if has_strict_pin and unpinned_specs:
                    conflicts.append(
                        ManifestConflict(
                            package=pkg,
                            sources=[d.source_file for d in decls],
                            specifiers=[d.specifier for d in decls],
                            conflict_type="PIN_VS_RANGE_MISMATCH",
                            description=(
                                f"Package '{pkg}' is strictly pinned in some manifests "
                                f"({', '.join(spec_list)}) but loose or constrained differently elsewhere."
                            ),
                        )
                    )
                elif len(set(versions)) > 1:
                    conflicts.append(
                        ManifestConflict(
                            package=pkg,
                            sources=[d.source_file for d in decls],
                            specifiers=[d.specifier for d in decls],
                            conflict_type="CONTRADICTING_PINNED_VERSIONS",
                            description=(
                                f"Package '{pkg}' has contradicting pinned versions: "
                                f"{', '.join(spec_list)}."
                            ),
                        )
                    )

        return ManifestReport(
            manifest_files_found=found_files,
            dependencies=grouped,
            conflicts=conflicts,
            total_unique_dependencies=len(grouped),
        )


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "LinkWatch"
    parser = ManifestParser(target)
    report = parser.scan()
    import json
    print(json.dumps(report.to_dict(), indent=2))
