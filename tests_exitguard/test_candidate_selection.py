"""
test_candidate_selection.py - Unit tests for CandidateEvaluator and Candidate Selection Logic.

NOTE: All tests in this file test deterministic candidate evaluation and evidence validation.
LinkWatch source code is NEVER modified or targeted by these tests.
"""

from pathlib import Path
import pytest

from exitguard.candidate_evaluator import CandidateEvaluation, CandidateEvaluator
from exitguard.capsule_schema import EvidenceStatus, ProposedAction


@pytest.fixture
def sample_inventory_data():
    """Synthetic inventory fixture modeling Member 1's dependency inventory."""
    return {
        "metadata": {
            "target_repository": "LinkWatch",
            "collector_role": "Member 1",
        },
        "dependencies": {
            "appdirs": {
                "declarations": [
                    {"source_file": "requirements.txt", "specifier": "==1.4.4"},
                    {"source_file": "pyproject.toml", "specifier": "==1.4.4"},
                ],
                "ast_usage": {
                    "is_used": True,
                    "imports": [
                        {
                            "file_path": "linkwatch/cache.py",
                            "line_number": 4,
                            "imported_symbols": ["user_cache_dir"],
                        }
                    ],
                },
                "objective_risks": [
                    "Upstream repository archived and unmaintained since 2017.",
                ],
            },
            "toml": {
                "declarations": [
                    {"source_file": "requirements.txt", "specifier": "==0.10.2"},
                ],
                "ast_usage": {
                    "is_used": True,
                    "imports": [
                        {
                            "file_path": "linkwatch/config.py",
                            "line_number": 3,
                            "imported_symbols": ["toml"],
                        }
                    ],
                },
                "objective_risks": [
                    "Unmaintained on PyPI since November 2020.",
                ],
            },
            "jinja2": {
                "declarations": [
                    {"source_file": "requirements.txt", "specifier": "==2.11.3"},
                ],
                "ast_usage": {
                    "is_used": True,
                    "imports": [
                        {
                            "file_path": "linkwatch/report.py",
                            "line_number": 3,
                            "imported_symbols": ["Environment"],
                        }
                    ],
                },
                "objective_risks": [
                    "Pinned to obsolete version 2.11.3.",
                    "Incompatible with MarkupSafe 3.0+.",
                ],
            },
        },
    }


def test_evaluate_appdirs_candidate(sample_inventory_data):
    """Verifies that appdirs is correctly evaluated as the primary candidate."""
    candidates = CandidateEvaluator.evaluate_candidates(sample_inventory_data, member2_recommendations=None)
    appdirs_cand = next((c for c in candidates if c.package_name == "appdirs"), None)

    assert appdirs_cand is not None
    assert appdirs_cand.is_recommended is True
    assert appdirs_cand.proposed_action == ProposedAction.REPLACE
    assert appdirs_cand.proposed_replacement == "platformdirs"
    assert appdirs_cand.migration_effort == "LOW"
    assert appdirs_cand.confidence_score >= 0.9
    assert len(appdirs_cand.ast_locations) == 1
    assert appdirs_cand.ast_locations[0].file_path == "linkwatch/cache.py"
    assert appdirs_cand.ast_locations[0].ast_symbol == "user_cache_dir"


def test_evaluate_toml_candidate(sample_inventory_data):
    """Verifies that toml is evaluated as stdlib migration alternative."""
    candidates = CandidateEvaluator.evaluate_candidates(sample_inventory_data, member2_recommendations=None)
    toml_cand = next((c for c in candidates if c.package_name == "toml"), None)

    assert toml_cand is not None
    assert toml_cand.is_recommended is False  # Alternative, not primary
    assert toml_cand.proposed_action == ProposedAction.REPLACE
    assert toml_cand.proposed_replacement == "tomllib"
    assert toml_cand.migration_effort == "MEDIUM"


def test_evaluate_jinja2_markupsafe_distinction(sample_inventory_data):
    """Verifies that Jinja2/MarkupSafe is correctly classified as a version constraint, NOT a replacement."""
    candidates = CandidateEvaluator.evaluate_candidates(sample_inventory_data, member2_recommendations=None)
    jinja_cand = next((c for c in candidates if c.package_name == "Jinja2"), None)

    assert jinja_cand is not None
    assert jinja_cand.is_recommended is False
    assert jinja_cand.proposed_action == ProposedAction.UPGRADE
    assert "not a dependency replacement" in " ".join(jinja_cand.contradicting_evidence).lower()
    assert "MarkupSafe is an indirect dependency" in jinja_cand.api_compatibility_risks


def test_missing_member2_evidence_is_explicitly_flagged(sample_inventory_data):
    """Verifies that missing Member 2 evidence is explicitly recorded as MISSING_FROM_MEMBER_2."""
    candidates = CandidateEvaluator.evaluate_candidates(sample_inventory_data, member2_recommendations=None)
    for c in candidates:
        assert c.gemma_recommendation_status == "MISSING_FROM_MEMBER_2"


def test_get_primary_candidate_selection(sample_inventory_data):
    """Verifies that get_primary_candidate returns appdirs."""
    candidates = CandidateEvaluator.evaluate_candidates(sample_inventory_data, member2_recommendations=None)
    primary = CandidateEvaluator.get_primary_candidate(candidates)

    assert primary is not None
    assert primary.package_name == "appdirs"
    assert primary.proposed_replacement == "platformdirs"


def test_candidate_to_dict_serialization(sample_inventory_data):
    """Verifies candidate to_dict serialization adheres to schema types."""
    candidates = CandidateEvaluator.evaluate_candidates(sample_inventory_data, member2_recommendations=None)
    primary = CandidateEvaluator.get_primary_candidate(candidates)
    data = primary.to_dict()

    assert data["package_name"] == "appdirs"
    assert data["proposed_action"] == "REPLACE"
    assert data["proposed_replacement"] == "platformdirs"
    assert isinstance(data["ast_locations"], list)
    assert data["ast_locations"][0]["status"] == "OBSERVED"
