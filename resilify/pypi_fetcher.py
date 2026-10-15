"""
PyPI Metadata Fetcher for Resilify (Member 1).

Queries the live PyPI JSON API (https://pypi.org/pypi/<pkg>/json) to gather
the latest versions, release dates, yanked status, and deprecation markers.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


@dataclass
class PyPIDependencyMetadata:
    package_name: str
    latest_version: Optional[str]
    latest_release_date: Optional[str]
    pinned_version: Optional[str]
    pinned_release_date: Optional[str]
    days_outdated: Optional[int]
    is_yanked: bool
    yanked_reason: Optional[str]
    requires_python: Optional[str]
    license_str: Optional[str]
    home_page: Optional[str]
    project_urls: Dict[str, str]
    is_inactive_or_deprecated: bool
    deprecation_evidence: List[str]
    raw_status: str  # "FOUND", "NOT_FOUND", "NETWORK_ERROR"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PyPIFetcher:
    """Fetches and evaluates live metadata from the PyPI JSON API."""

    BASE_URL = "https://pypi.org/pypi"
    CACHE_FILE = Path(".pypi_cache.json")

    KNOWN_DEPRECATIONS = {
        "appdirs": (
            "Upstream repository is archived/unmaintained since 2017. "
            "Active fork and drop-in replacement is 'platformdirs'."
        ),
        "toml": (
            "Python 3.11+ includes standard library 'tomllib' for reading TOML. "
            "PyPI 'toml' package is unmaintained and superseded."
        ),
        "nose": (
            "Project has been unmaintained since 2015. Completely broken on Python 3.12+ "
            "due to removal of standard library 'imp' module (PEP 594)."
        ),
        "six": (
            "Python 2 and 3 compatibility library. Redundant and obsolete on Python 3.10+."
        ),
        "pkg_resources": (
            "Part of setuptools; officially deprecated in favor of standard library 'importlib.resources' / 'importlib.metadata'."
        ),
    }

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self.cache_path = (cache_dir or Path(".")) / self.CACHE_FILE
        self._cache: Dict[str, Any] = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        if self.cache_path.exists():
            try:
                return json.loads(self.cache_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")
        except Exception:
            pass

    def fetch_package(
        self, package_name: str, pinned_version: Optional[str] = None
    ) -> PyPIDependencyMetadata:
        # Check in-memory/file cache first
        cache_key = f"{package_name}@{pinned_version or 'latest'}"
        if cache_key in self._cache:
            data = self._cache[cache_key]
            return PyPIDependencyMetadata(**data)

        url = f"{self.BASE_URL}/{package_name}/json"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Resilify-Dependency-Scanner/1.0 (Hackathon-ImpactForge)"},
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            meta = PyPIDependencyMetadata(
                package_name=package_name,
                latest_version=None,
                latest_release_date=None,
                pinned_version=pinned_version,
                pinned_release_date=None,
                days_outdated=None,
                is_yanked=False,
                yanked_reason=None,
                requires_python=None,
                license_str=None,
                home_page=None,
                project_urls={},
                is_inactive_or_deprecated=False,
                deprecation_evidence=[f"PyPI returned HTTP {e.code}"],
                raw_status="NOT_FOUND" if e.code == 404 else "NETWORK_ERROR",
            )
            return meta
        except Exception as e:
            return PyPIDependencyMetadata(
                package_name=package_name,
                latest_version=None,
                latest_release_date=None,
                pinned_version=pinned_version,
                pinned_release_date=None,
                days_outdated=None,
                is_yanked=False,
                yanked_reason=None,
                requires_python=None,
                license_str=None,
                home_page=None,
                project_urls={},
                is_inactive_or_deprecated=False,
                deprecation_evidence=[f"Connection failed: {str(e)}"],
                raw_status="NETWORK_ERROR",
            )

        info = payload.get("info", {})
        releases = payload.get("releases", {})

        latest_version = info.get("version")
        yanked = info.get("yanked", False)
        yanked_reason = info.get("yanked_reason")
        requires_python = info.get("requires_python")
        license_str = info.get("license")
        home_page = info.get("home_page")
        project_urls = info.get("project_urls") or {}
        classifiers = info.get("classifiers") or []

        # Find latest release date
        latest_rel_date = None
        if latest_version and latest_version in releases and releases[latest_version]:
            latest_rel_date = releases[latest_version][0].get("upload_time_iso_8601")

        # Find pinned version release date
        pinned_rel_date = None
        if pinned_version and pinned_version in releases and releases[pinned_version]:
            pinned_rel_date = releases[pinned_version][0].get("upload_time_iso_8601")

        # Compute days outdated
        days_outdated = None
        if latest_rel_date and pinned_rel_date:
            try:
                d_latest = datetime.fromisoformat(latest_rel_date.replace("Z", "+00:00"))
                d_pinned = datetime.fromisoformat(pinned_rel_date.replace("Z", "+00:00"))
                days_outdated = (d_latest - d_pinned).days
            except Exception:
                pass

        # Inspect deprecation signals
        deprecation_evidence: List[str] = []
        is_inactive = False

        for c in classifiers:
            if "7 - Inactive" in c or "Abandoned" in c:
                is_inactive = True
                deprecation_evidence.append(f"PyPI classifier indicates inactive/abandoned: '{c}'")

        # Check description text for abandonment / deprecation keywords
        desc = (info.get("description") or "").lower()
        summary = (info.get("summary") or "").lower()
        combined_text = f"{summary}\n{desc[:2000]}"

        if "deprecated" in combined_text or "unmaintained" in combined_text or "no longer maintained" in combined_text:
            deprecation_evidence.append("Package description contains deprecation/unmaintained notice")

        # Check known ecosystem deprecations
        norm_name = package_name.lower().replace("-", "").replace("_", "")
        for known_k, reason in self.KNOWN_DEPRECATIONS.items():
            if norm_name == known_k.replace("-", "").replace("_", ""):
                deprecation_evidence.append(f"Ecosystem Advisory: {reason}")
                is_inactive = True

        # Check last release age
        if latest_rel_date:
            try:
                rel_dt = datetime.fromisoformat(latest_rel_date.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                age_days = (now - rel_dt).days
                if age_days > 365 * 4:  # > 4 years since any release
                    deprecation_evidence.append(
                        f"Stale package: Last release was {age_days // 365} years ago ({latest_rel_date[:10]})"
                    )
            except Exception:
                pass

        meta = PyPIDependencyMetadata(
            package_name=package_name,
            latest_version=latest_version,
            latest_release_date=latest_rel_date,
            pinned_version=pinned_version,
            pinned_release_date=pinned_rel_date,
            days_outdated=days_outdated,
            is_yanked=yanked,
            yanked_reason=yanked_reason,
            requires_python=requires_python,
            license_str=license_str,
            home_page=home_page,
            project_urls=project_urls,
            is_inactive_or_deprecated=is_inactive or len(deprecation_evidence) > 0,
            deprecation_evidence=deprecation_evidence,
            raw_status="FOUND",
        )

        self._cache[cache_key] = meta.to_dict()
        self._save_cache()
        return meta

    def fetch_all(
        self, dependencies: Dict[str, Optional[str]]
    ) -> Dict[str, PyPIDependencyMetadata]:
        results: Dict[str, PyPIDependencyMetadata] = {}
        for pkg, pinned_ver in dependencies.items():
            results[pkg] = self.fetch_package(pkg, pinned_ver)
        return results


if __name__ == "__main__":
    fetcher = PyPIFetcher()
    test_pkgs = {"appdirs": "1.4.4", "toml": "0.10.2", "nose": "1.3.7", "requests": "2.31.0"}
    res = fetcher.fetch_all(test_pkgs)
    for k, v in res.items():
        print(f"=== {k} ===")
        print(f"  Latest: {v.latest_version} (Release: {v.latest_release_date})")
        print(f"  Pinned: {v.pinned_version} (Release: {v.pinned_release_date})")
        print(f"  Days Outdated: {v.days_outdated}")
        print(f"  Deprecated/Inactive: {v.is_inactive_or_deprecated}")
        print(f"  Evidence: {v.deprecation_evidence}")
