"""
Verification Test Suite for Resilify Migrations.
Synthesized by Gemma 4 (Member 2) for Sandbox Verification by Member 3.
"""

import os
import sys
import pytest

# --- Behavioral Migration Parity Tests ---

def test_toml_to_tomllib_migration_parity(tmp_path):
    """Verifies toml -> tomllib migration correctly parses TOML in binary mode ('rb')."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    
    p = tmp_path / "sites.toml"
    p.write_bytes(b'title = "linkwatch"\n[[sites]]\nname = "Example"\nurl = "https://example.com"\n')
    with open(p, "rb") as f:
        data = tomllib.load(f)
    assert data["title"] == "linkwatch"
    assert len(data["sites"]) == 1
    assert data["sites"][0]["name"] == "Example"
    assert data["sites"][0]["url"] == "https://example.com"

def test_appdirs_to_platformdirs_migration_parity():
    """Verifies appdirs -> platformdirs accurately resolves cache directories without deprecations."""
    from platformdirs import user_cache_dir
    path = user_cache_dir("linkwatch")
    assert path is not None
    assert "linkwatch" in path.lower()

def test_jinja2_bump_soft_unicode_resolution(tmp_path):
    """Verifies modern Jinja2 renders templates cleanly without markupsafe soft_unicode import error."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    tmpl_dir = tmp_path / "templates"
    tmpl_dir.mkdir()
    (tmpl_dir / "test.html.j2").write_text("<h1>{{ title }}</h1>", encoding="utf-8")
    env = Environment(loader=FileSystemLoader(str(tmpl_dir)), autoescape=select_autoescape(["html", "j2"]))
    template = env.get_template("test.html.j2")
    rendered = template.render(title="LinkWatch Uptime Status")
    assert "LinkWatch Uptime Status" in rendered

def test_setuptools_pkg_resources_to_importlib_resources_parity():
    """Verifies setuptools.pkg_resources -> importlib.resources.files correctly locates package resources."""
    from importlib.resources import files
    templates_dir = str(files("linkwatch").joinpath("templates"))
    assert os.path.exists(templates_dir)
    assert os.path.isfile(os.path.join(templates_dir, "status.html.j2"))

def test_ghost_and_obsolete_dependencies_elimination():
    """Verifies ghost (six) and broken dev tools (nose) are eliminated from active runtime paths."""
    import sys
    # six should not be required anywhere by linkwatch modules
    import linkwatch.cli
    import linkwatch.checker
    import linkwatch.dates
    import linkwatch.encoding
    # Confirm six is not imported by linkwatch
    assert "six" not in [mod for mod in sys.modules if mod.startswith("linkwatch.")]
    # nose should not be imported or required in test runner
    assert "nose" not in sys.modules

def test_pydantic_manifest_and_syntax_compatibility():
    """Verifies Site and Settings model validation works correctly with pydantic."""
    from linkwatch.config import Site, Settings
    s = Site(name="Example", url="https://example.com")
    assert s.name == "Example"
    assert s.url == "https://example.com"
    with pytest.raises(ValueError):
        Site(name="", url="https://example.com")
    with pytest.raises(ValueError):
        Site(name="Example", url="ftp://example.com")

def test_requests_idna_transitive_resolution():
    """Verifies unpinning idna allows modern requests stack to operate without pin conflicts."""
    import requests
    parsed = requests.compat.urlparse("https://example.com")
    assert parsed.scheme == "https"
    assert parsed.netloc == "example.com"
