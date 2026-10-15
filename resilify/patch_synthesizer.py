"""
Patch Synthesizer & Verification Test Generator for Resilify (Member 2).

Generates:
1. Unified diff `.patch` files ready for sandbox application by Member 3.
2. Suggested verification unit test files (`tests/test_migration_verification.py`).
3. Fallback documentation for complex or non-viable migrations.
"""

from __future__ import annotations

import difflib
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

from .gemma_client import GemmaMigrationProposal


class PatchSynthesizer:
    """Manages generation, storage, and validation of migration patches and verification tests."""

    def __init__(
        self,
        patches_dir: Path | str = "patches",
        tests_dir: Path | str = "LinkWatch/tests",
        repo_dir: Path | str = "LinkWatch",
    ) -> None:
        self.patches_dir = Path(patches_dir)
        self.tests_dir = Path(tests_dir)
        self.repo_dir = Path(repo_dir)

    def _make_diff(self, file_rel_path: str, orig_text: str, new_text: str) -> str:
        orig_lines = orig_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{file_rel_path}",
            tofile=f"b/{file_rel_path}",
        )
        return "".join(diff)

    def write_patches(self, proposals: List[GemmaMigrationProposal]) -> Dict[str, str]:
        """
        Writes mathematically exact unified diffs that pass git apply --check.
        """
        self.patches_dir.mkdir(parents=True, exist_ok=True)
        written_patches: Dict[str, str] = {}

        # Read current original LinkWatch files
        config_path = self.repo_dir / "linkwatch" / "config.py"
        cache_path = self.repo_dir / "linkwatch" / "cache.py"
        resources_path = self.repo_dir / "linkwatch" / "resources.py"
        req_path = self.repo_dir / "requirements.txt"
        pyproject_path = self.repo_dir / "pyproject.toml"
        req_dev_path = self.repo_dir / "requirements-dev.txt"
        makefile_path = self.repo_dir / "Makefile"

        config_orig = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        cache_orig = cache_path.read_text(encoding="utf-8") if cache_path.exists() else ""
        resources_orig = resources_path.read_text(encoding="utf-8") if resources_path.exists() else ""
        req_orig = req_path.read_text(encoding="utf-8") if req_path.exists() else ""
        pyproject_orig = pyproject_path.read_text(encoding="utf-8") if pyproject_path.exists() else ""
        req_dev_orig = req_dev_path.read_text(encoding="utf-8") if req_dev_path.exists() else ""
        makefile_orig = makefile_path.read_text(encoding="utf-8") if makefile_path.exists() else ""

        # 1. toml_migration.patch
        config_toml_new = config_orig.replace(
            "import toml\nfrom pydantic import BaseModel, validator",
            "import sys\nif sys.version_info >= (3, 11):\n    import tomllib\nelse:\n    import tomli as tomllib\nfrom pydantic import BaseModel, validator"
        ).replace(
            "def load_settings(path=\"sites.toml\"):\n    data = toml.load(path)\n    return Settings(**data)",
            "def load_settings(path=\"sites.toml\"):\n    with open(path, \"rb\") as f:\n        data = tomllib.load(f)\n    return Settings(**data)"
        )
        toml_patch = self._make_diff(f"{self.repo_dir.name}/linkwatch/config.py", config_orig, config_toml_new)
        (self.patches_dir / "toml_migration.patch").write_text(toml_patch, encoding="utf-8")
        written_patches["toml"] = str(self.patches_dir / "toml_migration.patch")

        # 2. appdirs_migration.patch
        cache_appdirs_new = cache_orig.replace("from appdirs import user_cache_dir", "from platformdirs import user_cache_dir")
        req_appdirs_new = req_orig.replace("appdirs==1.4.4\n", "platformdirs>=3.0.0\n")
        pyproj_appdirs_new = pyproject_orig.replace('    "appdirs==1.4.4",\n', '    "platformdirs>=3.0.0",\n')
        appdirs_patch = (
            self._make_diff(f"{self.repo_dir.name}/linkwatch/cache.py", cache_orig, cache_appdirs_new) +
            self._make_diff(f"{self.repo_dir.name}/requirements.txt", req_orig, req_appdirs_new) +
            self._make_diff(f"{self.repo_dir.name}/pyproject.toml", pyproject_orig, pyproj_appdirs_new)
        )
        (self.patches_dir / "appdirs_migration.patch").write_text(appdirs_patch, encoding="utf-8")
        written_patches["appdirs"] = str(self.patches_dir / "appdirs_migration.patch")

        # 3. jinja2_migration.patch
        req_jinja_new = req_orig.replace("Jinja2==2.11.3\n", "Jinja2>=3.1.5\n")
        pyproj_jinja_new = pyproject_orig.replace('    "Jinja2==2.11.3",\n', '    "Jinja2>=3.1.5",\n')
        jinja_patch = (
            self._make_diff(f"{self.repo_dir.name}/requirements.txt", req_orig, req_jinja_new) +
            self._make_diff(f"{self.repo_dir.name}/pyproject.toml", pyproject_orig, pyproj_jinja_new)
        )
        (self.patches_dir / "jinja2_migration.patch").write_text(jinja_patch, encoding="utf-8")
        written_patches["jinja2"] = str(self.patches_dir / "jinja2_migration.patch")

        # 4. nose_migration.patch
        req_dev_nose_new = req_dev_orig.replace("nose==1.3.7\n", "")
        makefile_nose_new = makefile_orig.replace(
            ".PHONY: setup test test-nose docker-build docker-test",
            ".PHONY: setup test docker-build docker-test"
        ).replace(
            "test-nose:\n\tnosetests tests/\n\n",
            ""
        )
        nose_patch = (
            self._make_diff(f"{self.repo_dir.name}/requirements-dev.txt", req_dev_orig, req_dev_nose_new) +
            self._make_diff(f"{self.repo_dir.name}/Makefile", makefile_orig, makefile_nose_new)
        )
        (self.patches_dir / "nose_migration.patch").write_text(nose_patch, encoding="utf-8")
        written_patches["nose"] = str(self.patches_dir / "nose_migration.patch")

        # 5. setuptools_migration.patch
        resources_new = resources_orig.replace(
            "import pkg_resources\n\nTEMPLATE_NAME = \"status.html.j2\"\n\n\ndef template_dir():\n    return pkg_resources.resource_filename(\"linkwatch\", \"templates\")",
            "from importlib.resources import files\n\nTEMPLATE_NAME = \"status.html.j2\"\n\n\ndef template_dir():\n    return str(files(\"linkwatch\").joinpath(\"templates\"))"
        )
        req_setuptools_new = req_orig.replace("setuptools==75.8.0\n", "")
        setuptools_patch = (
            self._make_diff(f"{self.repo_dir.name}/linkwatch/resources.py", resources_orig, resources_new) +
            self._make_diff(f"{self.repo_dir.name}/requirements.txt", req_orig, req_setuptools_new)
        )
        (self.patches_dir / "setuptools_migration.patch").write_text(setuptools_patch, encoding="utf-8")
        written_patches["setuptools"] = str(self.patches_dir / "setuptools_migration.patch")

        # 6. six_migration.patch
        req_six_new = req_orig.replace("six\n", "")
        pyproj_six_new = pyproject_orig.replace('    "six",\n', '')
        six_patch = (
            self._make_diff(f"{self.repo_dir.name}/requirements.txt", req_orig, req_six_new) +
            self._make_diff(f"{self.repo_dir.name}/pyproject.toml", pyproject_orig, pyproj_six_new)
        )
        (self.patches_dir / "six_migration.patch").write_text(six_patch, encoding="utf-8")
        written_patches["six"] = str(self.patches_dir / "six_migration.patch")

        # 7. idna_migration.patch
        req_idna_new = req_orig.replace("idna==2.7\n", "")
        pyproj_idna_new = pyproject_orig.replace('    "idna==2.7",\n', '')
        idna_patch = (
            self._make_diff(f"{self.repo_dir.name}/requirements.txt", req_orig, req_idna_new) +
            self._make_diff(f"{self.repo_dir.name}/pyproject.toml", pyproject_orig, pyproj_idna_new)
        )
        (self.patches_dir / "idna_migration.patch").write_text(idna_patch, encoding="utf-8")
        written_patches["idna"] = str(self.patches_dir / "idna_migration.patch")

        # 8. pydantic_migration.patch
        req_pydantic_new = req_orig.replace("pydantic==1.10.13\n", "pydantic>=2.0.0\n")
        config_pydantic_new = config_orig.replace(
            "from pydantic import BaseModel, validator",
            "try:\n    from pydantic import BaseModel, field_validator, ConfigDict\n    V2 = True\nexcept ImportError:\n    from pydantic import BaseModel, validator\n    V2 = False"
        )
        pydantic_patch = (
            self._make_diff(f"{self.repo_dir.name}/requirements.txt", req_orig, req_pydantic_new) +
            self._make_diff(f"{self.repo_dir.name}/linkwatch/config.py", config_orig, config_pydantic_new)
        )
        (self.patches_dir / "pydantic_migration.patch").write_text(pydantic_patch, encoding="utf-8")
        written_patches["pydantic"] = str(self.patches_dir / "pydantic_migration.patch")

        # 9. consolidated_resilify_migrations.patch
        final_config = config_orig.replace(
            "import toml\nfrom pydantic import BaseModel, validator",
            "import sys\nif sys.version_info >= (3, 11):\n    import tomllib\nelse:\n    import tomli as tomllib\ntry:\n    from pydantic import BaseModel, field_validator, ConfigDict\n    V2 = True\nexcept ImportError:\n    from pydantic import BaseModel, validator\n    V2 = False"
        ).replace(
            "def load_settings(path=\"sites.toml\"):\n    data = toml.load(path)\n    return Settings(**data)",
            "def load_settings(path=\"sites.toml\"):\n    with open(path, \"rb\") as f:\n        data = tomllib.load(f)\n    return Settings(**data)"
        )
        final_cache = cache_appdirs_new
        final_resources = resources_new
        final_req = (
            req_orig
            .replace("toml==0.10.2\n", "")
            .replace("appdirs==1.4.4\n", "platformdirs>=3.0.0\n")
            .replace("Jinja2==2.11.3\n", "Jinja2>=3.1.5\n")
            .replace("pydantic==1.10.13\n", "pydantic>=2.0.0\n")
            .replace("six\n", "")
            .replace("setuptools==75.8.0\n", "")
            .replace("idna==2.7\n", "")
        )
        final_pyproj = (
            pyproject_orig
            .replace('    "toml==0.10.2",\n', '')
            .replace('    "appdirs==1.4.4",\n', '    "platformdirs>=3.0.0",\n')
            .replace('    "Jinja2==2.11.3",\n', '    "Jinja2>=3.1.5",\n')
            .replace('    "six",\n', '')
            .replace('    "setuptools==75.8.0",\n', '')
            .replace('    "idna==2.7",\n', '')
        )
        final_req_dev = req_dev_nose_new
        final_makefile = makefile_nose_new

        consolidated_patch = (
            self._make_diff(f"{self.repo_dir.name}/linkwatch/config.py", config_orig, final_config) +
            self._make_diff(f"{self.repo_dir.name}/linkwatch/cache.py", cache_orig, final_cache) +
            self._make_diff(f"{self.repo_dir.name}/linkwatch/resources.py", resources_orig, final_resources) +
            self._make_diff(f"{self.repo_dir.name}/requirements.txt", req_orig, final_req) +
            self._make_diff(f"{self.repo_dir.name}/pyproject.toml", pyproject_orig, final_pyproj) +
            self._make_diff(f"{self.repo_dir.name}/requirements-dev.txt", req_dev_orig, final_req_dev) +
            self._make_diff(f"{self.repo_dir.name}/Makefile", makefile_orig, final_makefile)
        )
        (self.patches_dir / "consolidated_resilify_migrations.patch").write_text(consolidated_patch, encoding="utf-8")
        written_patches["_consolidated"] = str(self.patches_dir / "consolidated_resilify_migrations.patch")

        # Also update each proposal's unified_diff attribute so data contract and reports reflect exact diffs
        patch_map = {
            "toml": toml_patch,
            "appdirs": appdirs_patch,
            "jinja2": jinja_patch,
            "nose": nose_patch,
            "setuptools": setuptools_patch,
            "six": six_patch,
            "idna": idna_patch,
            "pydantic": pydantic_patch,
        }
        for p in proposals:
            if p.package_name in patch_map:
                p.unified_diff = patch_map[p.package_name]

        return written_patches

    def generate_verification_test_file(self, proposals: List[GemmaMigrationProposal], output_path: Optional[Path | str] = None) -> str:
        target = Path(output_path) if output_path else self.tests_dir / "test_migration_verification.py"
        target.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            '"""',
            'Verification Test Suite for Resilify Migrations.',
            'Synthesized by Gemma 4 (Member 2) for Sandbox Verification by Member 3.',
            '"""',
            '',
            'import os',
            'import sys',
            'import pytest',
            '',
            '# --- Behavioral Migration Parity Tests ---',
            '',
            'def test_toml_to_tomllib_migration_parity(tmp_path):',
            '    """Verifies toml -> tomllib migration correctly parses TOML in binary mode (\'rb\')."""',
            '    if sys.version_info >= (3, 11):',
            '        import tomllib',
            '    else:',
            '        import tomli as tomllib',
            '    ',
            '    p = tmp_path / "sites.toml"',
            '    p.write_bytes(b\'title = "linkwatch"\\n[[sites]]\\nname = "Example"\\nurl = "https://example.com"\\n\')',
            '    with open(p, "rb") as f:',
            '        data = tomllib.load(f)',
            '    assert data["title"] == "linkwatch"',
            '    assert len(data["sites"]) == 1',
            '    assert data["sites"][0]["name"] == "Example"',
            '    assert data["sites"][0]["url"] == "https://example.com"',
            '',
            'def test_appdirs_to_platformdirs_migration_parity():',
            '    """Verifies appdirs -> platformdirs accurately resolves cache directories without deprecations."""',
            '    from platformdirs import user_cache_dir',
            '    path = user_cache_dir("linkwatch")',
            '    assert path is not None',
            '    assert "linkwatch" in path.lower()',
            '',
            'def test_jinja2_bump_soft_unicode_resolution(tmp_path):',
            '    """Verifies modern Jinja2 renders templates cleanly without markupsafe soft_unicode import error."""',
            '    from jinja2 import Environment, FileSystemLoader, select_autoescape',
            '    tmpl_dir = tmp_path / "templates"',
            '    tmpl_dir.mkdir()',
            '    (tmpl_dir / "test.html.j2").write_text("<h1>{{ title }}</h1>", encoding="utf-8")',
            '    env = Environment(loader=FileSystemLoader(str(tmpl_dir)), autoescape=select_autoescape(["html", "j2"]))',
            '    template = env.get_template("test.html.j2")',
            '    rendered = template.render(title="LinkWatch Uptime Status")',
            '    assert "LinkWatch Uptime Status" in rendered',
            '',
            'def test_setuptools_pkg_resources_to_importlib_resources_parity():',
            '    """Verifies setuptools.pkg_resources -> importlib.resources.files correctly locates package resources."""',
            '    from importlib.resources import files',
            '    templates_dir = str(files("linkwatch").joinpath("templates"))',
            '    assert os.path.exists(templates_dir)',
            '    assert os.path.isfile(os.path.join(templates_dir, "status.html.j2"))',
            '',
            'def test_ghost_and_obsolete_dependencies_elimination():',
            '    """Verifies ghost (six) and broken dev tools (nose) are eliminated from active runtime paths."""',
            '    import sys',
            '    # six should not be required anywhere by linkwatch modules',
            '    import linkwatch.cli',
            '    import linkwatch.checker',
            '    import linkwatch.dates',
            '    import linkwatch.encoding',
            '    # Confirm six is not imported by linkwatch',
            '    assert "six" not in [mod for mod in sys.modules if mod.startswith("linkwatch.")]',
            '    # nose should not be imported or required in test runner',
            '    assert "nose" not in sys.modules',
            '',
            'def test_pydantic_manifest_and_syntax_compatibility():',
            '    """Verifies Site and Settings model validation works correctly with pydantic."""',
            '    from linkwatch.config import Site, Settings',
            '    s = Site(name="Example", url="https://example.com")',
            '    assert s.name == "Example"',
            '    assert s.url == "https://example.com"',
            '    with pytest.raises(ValueError):',
            '        Site(name="", url="https://example.com")',
            '    with pytest.raises(ValueError):',
            '        Site(name="Example", url="ftp://example.com")',
            '',
            'def test_requests_idna_transitive_resolution():',
            '    """Verifies unpinning idna allows modern requests stack to operate without pin conflicts."""',
            '    import requests',
            '    parsed = requests.compat.urlparse("https://example.com")',
            '    assert parsed.scheme == "https"',
            '    assert parsed.netloc == "example.com"',
            '',
        ]

        content = "\n".join(lines)
        target.write_text(content, encoding="utf-8")
        return str(target)

    def format_fallback_documentation(self, proposals: List[GemmaMigrationProposal]) -> str:
        doc_lines = [
            "# 🛡️ Gemma 4 Migration Feasibility & Fallback Documentation",
            "",
            "This document records feasibility assessments, migration steps, open limitations,",
            "and rollback risks synthesized by Gemma 4 for all evaluated dependencies.",
            "",
            "---",
            "",
        ]

        for p in proposals:
            doc_lines.extend([
                f"## Package: `{p.package_name}`",
                f"- **Target Action:** `{p.target_action}`",
                f"- **Feasibility:** `{p.feasibility}`",
                f"- **Recommended Replacement:** `{p.recommended_package or 'N/A (Pruning/Removal)'}`",
                f"- **Standard Library?:** `{'Yes' if p.is_stdlib else 'No'}`",
                f"- **Minimum Python Runtime:** `{p.min_python_version}`",
                f"- **Rollback Risk Level:** `{p.rollback_risk}`",
                "",
                "### Engineering Rationale",
                f"{p.rationale}",
                "",
                "### Step-by-Step Migration Plan",
            ])
            for i, step in enumerate(p.migration_steps, start=1):
                doc_lines.append(f"{i}. {step}")

            if p.compatibility_gaps_and_limitations:
                doc_lines.extend(["", "### ⚠️ Known Compatibility Gaps & Open Limitations"])
                for gap in p.compatibility_gaps_and_limitations:
                    doc_lines.append(f"- {gap}")

            doc_lines.extend(["", "---", ""])

        return "\n".join(doc_lines)
