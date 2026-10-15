"""
Verification Test Suite for Resilify Migrations.
Synthesized by Gemma 4 (Member 2) for Sandbox Verification by Member 3.
"""

import os
import sys
import pytest

# --- Verification tests for appdirs (REPLACE_PACKAGE) ---
def test_platformdirs_user_cache_dir():
    from linkwatch.cache import cache_dir
    path = cache_dir()
    assert os.path.exists(path)
    assert 'linkwatch' in path.lower()

# --- Verification tests for idna (REMOVE_TRANSITIVE_PIN) ---
def test_requests_idna_resolution():
    import requests
    resp = requests.compat.urlparse('https://example.com')
    assert resp.scheme == 'https'

# --- Verification tests for jinja2 (BUMP_VERSION) ---
def test_jinja2_report_rendering(tmp_path):
    from linkwatch.report import render_report
    out = tmp_path / 'out.html'
    render_report([{'name': 'Test', 'url': 'http://test', 'up': True}], output=str(out))
    assert out.exists()
    assert 'Test' in out.read_text()

# --- Verification tests for nose (REMOVE_BROKEN_DEV_TOOL) ---
def test_pytest_runs_cleanly():
    import pytest
    ret = pytest.main(['-q', 'tests/test_cli.py'])
    assert ret == 0

# --- Verification tests for pydantic (RESOLVE_MANIFEST_CONFLICT) ---
def test_pydantic_site_validation():
    from linkwatch.config import Site
    import pytest
    s = Site(name='Test', url='https://test.com')
    assert s.name == 'Test'
    with pytest.raises(ValueError):
        Site(name='', url='https://test.com')

# --- Verification tests for setuptools (MIGRATE_TO_STDLIB) ---
def test_template_dir_exists():
    from linkwatch.resources import template_dir, TEMPLATE_NAME
    import os
    td = template_dir()
    assert os.path.isdir(td)
    assert os.path.isfile(os.path.join(td, TEMPLATE_NAME))

# --- Verification tests for six (REMOVE_GHOST) ---
def test_no_six_import_dependency():
    import sys
    sys.modules.pop('six', None)
    import linkwatch.cli
    assert 'six' not in sys.modules

# --- Verification tests for toml (MIGRATE_TO_STDLIB) ---
def test_load_settings_with_tomllib(tmp_path):
    p = tmp_path / 'sites.toml'
    p.write_text('title = "test"\n[[sites]]\nname = "Example"\nurl = "https://example.com"\n')
    cfg = load_settings(str(p))
    assert cfg.title == 'test'
    assert len(cfg.sites) == 1
