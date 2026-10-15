"""
test_gemma_advisor.py - Unit tests for GemmaAdvisor model client & validation logic.

NOTE: All tests strictly use mocked API clients and synthetic inputs.
They do NOT require GEMINI_API_KEY or make network requests.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from exitguard.capsule_schema import EvidenceStatus, ProposedAction
from exitguard.gemma_advisor import (
    HOSTED_GEMMA_MODEL_ID,
    GemmaAdviceRecord,
    GemmaAdvisor,
    GemmaRecommendation,
)


@pytest.fixture
def sample_inventory():
    return {
        "metadata": {
            "target_repository": "LinkWatch",
            "collector_role": "Member 1",
        },
        "dependencies": {
            "appdirs": {
                "declarations": [
                    {"raw_line": "appdirs==1.4.4", "source_file": "requirements.txt"}
                ],
                "ast_usage": {
                    "imports": [
                        {
                            "file_path": "linkwatch/cache.py",
                            "line_number": 4,
                            "statement": "from appdirs import user_cache_dir",
                        }
                    ]
                },
                "objective_risks": [
                    "Upstream repository archived and unmaintained since 2017."
                ],
            },
            "toml": {
                "declarations": [
                    {"raw_line": "toml==0.10.2", "source_file": "requirements.txt"}
                ],
                "ast_usage": {
                    "imports": [
                        {
                            "file_path": "linkwatch/config.py",
                            "line_number": 3,
                            "statement": "import toml",
                        }
                    ]
                },
                "objective_risks": ["Unmaintained on PyPI since 2020."],
            },
        },
    }


@pytest.fixture
def valid_gemma_json():
    return json.dumps(
        {
            "model_id": HOSTED_GEMMA_MODEL_ID,
            "target_dependency": "appdirs",
            "proposed_replacement": "platformdirs>=3.0.0",
            "proposed_action": "REPLACE",
            "rationale": "appdirs is abandoned since 2017. platformdirs is the active community fork.",
            "evidence_references": [
                "linkwatch/cache.py:4",
                "requirements.txt:2",
            ],
            "compatibility_risks": [
                "Directory convention differences if roaming is enabled."
            ],
            "assumptions": [
                "Caller only requires user_cache_dir function."
            ],
            "migration_steps": [
                "Replace import in linkwatch/cache.py",
                "Update requirements.txt to platformdirs>=3.0.0",
            ],
            "verification_tests": [
                "tests/test_cache.py::test_cache_round_trip"
            ],
            "confidence": "HIGH",
            "confidence_explanation": "Direct 1:1 drop-in replacement with identical signature.",
        }
    )


def test_gemma_prompt_assembly(sample_inventory):
    """Verifies that the prompt incorporates AST usages, repository facts, and schema constraints."""
    advisor = GemmaAdvisor()
    prompt = advisor.build_prompt(sample_inventory)

    assert "LinkWatch" in prompt
    assert "appdirs" in prompt
    assert "linkwatch/cache.py:4" in prompt
    assert "f52f3930c8e7c33d934ccf614955a38e26984bd5" in prompt
    assert "gemma-4-26b-a4b-it" in prompt
    assert "soft_unicode" in prompt


def test_gemma_missing_credentials(sample_inventory, monkeypatch):
    """Verifies that running without an API key safely returns CREDENTIALS_MISSING with no network call."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    advisor = GemmaAdvisor()
    record = advisor.generate_recommendation(sample_inventory)

    assert record.validation_status == "CREDENTIALS_MISSING"
    assert record.recommendation is None
    assert any("GEMINI_API_KEY environment variable is not set" in err for err in record.validation_errors)


def test_gemma_valid_mocked_response(sample_inventory, valid_gemma_json):
    """Verifies valid response parsing and schema validation from a mocked client."""
    advisor = GemmaAdvisor()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text=valid_gemma_json)

    record = advisor.generate_recommendation(sample_inventory, mock_client=mock_client)

    assert record.validation_status == "VALID"
    assert len(record.validation_errors) == 0
    assert record.recommendation is not None
    assert record.recommendation.target_dependency == "appdirs"
    assert record.recommendation.proposed_replacement == "platformdirs>=3.0.0"
    assert record.recommendation.proposed_action == ProposedAction.REPLACE
    assert record.recommendation.confidence == "HIGH"
    assert record.recommendation.provenance == EvidenceStatus.AI_RECOMMENDATION


def test_gemma_malformed_json_response(sample_inventory):
    """Verifies that malformed JSON is rejected with VALIDATION_FAILED."""
    advisor = GemmaAdvisor()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="Sorry, I cannot produce valid JSON {broken")

    record = advisor.generate_recommendation(sample_inventory, mock_client=mock_client)

    assert record.validation_status == "VALIDATION_FAILED"
    assert record.recommendation is None
    assert any("Malformed JSON" in err for err in record.validation_errors)


def test_gemma_missing_evidence_reference(sample_inventory, valid_gemma_json):
    """Verifies that references to nonexistent files or fabricated evidence are rejected."""
    bad_data = json.loads(valid_gemma_json)
    bad_data["evidence_references"] = ["totally_fabricated_file.xyz:999"]

    advisor = GemmaAdvisor()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text=json.dumps(bad_data))

    record = advisor.generate_recommendation(sample_inventory, mock_client=mock_client)

    assert record.validation_status == "VALIDATION_FAILED"
    assert any("do not correspond to any known manifest or source file" in err for err in record.validation_errors)


def test_gemma_hallucinated_dependency(sample_inventory, valid_gemma_json):
    """Verifies that recommendations targeting nonexistent packages are rejected as hallucinations."""
    bad_data = json.loads(valid_gemma_json)
    bad_data["target_dependency"] = "completely_hallucinated_dep_xyz"

    advisor = GemmaAdvisor()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text=json.dumps(bad_data))

    record = advisor.generate_recommendation(sample_inventory, mock_client=mock_client)

    assert record.validation_status == "VALIDATION_FAILED"
    assert any("does not exist in inventory" in err for err in record.validation_errors)


def test_gemma_api_error_handling(sample_inventory):
    """Verifies that API errors are caught safely and recorded with API_ERROR status."""
    advisor = GemmaAdvisor()
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded or backend 503 unavailable")

    record = advisor.generate_recommendation(sample_inventory, mock_client=mock_client)

    assert record.validation_status == "API_ERROR"
    assert record.recommendation is None
    assert any("Model generation error" in err for err in record.validation_errors)


def test_gemma_secret_scrubbing_in_evidence(sample_inventory):
    """Verifies that sensitive credentials are scrubbed if present in error messages or responses."""
    advisor = GemmaAdvisor()
    mock_client = MagicMock()
    fake_key = "AIzaSyDummySecretKey12345678901234567"
    mock_client.models.generate_content.side_effect = RuntimeError(f"Failed with key {fake_key}")

    record = advisor.generate_recommendation(sample_inventory, mock_client=mock_client)

    assert fake_key not in record.validation_errors[0]
    assert "[REDACTED_SECRET]" in record.validation_errors[0]


def test_save_evidence_record(sample_inventory, valid_gemma_json, tmp_path: Path):
    """Verifies that evidence records are persisted under the specified artifacts directory."""
    advisor = GemmaAdvisor()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text=valid_gemma_json)

    record = advisor.generate_recommendation(sample_inventory, mock_client=mock_client)
    evidence_path = advisor.save_evidence_record(record, tmp_path)

    assert evidence_path.exists()
    saved = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert saved["model_id"] == HOSTED_GEMMA_MODEL_ID
    assert saved["validation_status"] == "VALID"
    assert saved["recommendation"]["target_dependency"] == "appdirs"


def test_update_capsule_with_validated_recommendation(sample_inventory, valid_gemma_json, tmp_path: Path):
    """Verifies that valid Gemma recommendation updates capsule with AI_RECOMMENDATION provenance."""
    advisor = GemmaAdvisor()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text=valid_gemma_json)

    record = advisor.generate_recommendation(sample_inventory, mock_client=mock_client)

    dummy_capsule = {
        "capsule_id": "test-capsule",
        "verification": {"verdict": "VERIFIED_SUCCESS"},
        "migration_proposal": {
            "proposed_action": "REPLACE",
            "replacement_package": "old_package",
            "rationale": "old rationale",
            "status": "MANUAL_STAND_IN",
        },
    }
    capsule_file = tmp_path / "test_capsule.json"
    capsule_file.write_text(json.dumps(dummy_capsule, indent=2), encoding="utf-8")

    dummy_md = tmp_path / "TEST_CAPSULE.md"
    dummy_md.write_text("# Test Capsule\n- **AI Recommendation Provenance:** `MISSING_FROM_MEMBER_2`\n", encoding="utf-8")

    updated = advisor.update_capsule_with_recommendation(record, capsule_file, dummy_md)
    assert updated is True

    loaded_json = json.loads(capsule_file.read_text(encoding="utf-8"))
    prop = loaded_json["migration_proposal"]
    assert prop["status"] == EvidenceStatus.AI_RECOMMENDATION.value
    assert prop["replacement_package"] == "platformdirs>=3.0.0"
    assert HOSTED_GEMMA_MODEL_ID in prop["uncertainty_notes"]

    loaded_md = dummy_md.read_text(encoding="utf-8")
    assert "AI_RECOMMENDATION" in loaded_md
    assert HOSTED_GEMMA_MODEL_ID in loaded_md


def test_update_capsule_rejected_when_validation_fails(sample_inventory, tmp_path: Path):
    """Verifies that unverified or failed recommendation does NOT overwrite capsule."""
    advisor = GemmaAdvisor()
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = MagicMock(text="broken json {")

    record = advisor.generate_recommendation(sample_inventory, mock_client=mock_client)
    assert record.validation_status == "VALIDATION_FAILED"

    capsule_file = tmp_path / "test_capsule.json"
    dummy_capsule = {"migration_proposal": {"status": "HEURISTIC"}}
    capsule_file.write_text(json.dumps(dummy_capsule), encoding="utf-8")

    updated = advisor.update_capsule_with_recommendation(record, capsule_file)
    assert updated is False
    assert json.loads(capsule_file.read_text(encoding="utf-8"))["migration_proposal"]["status"] == "HEURISTIC"


def test_provenance_distinction(sample_inventory):
    """Verifies that provenance distinguishes AI_RECOMMENDATION, HEURISTIC, MANUAL_STAND_IN, and MISSING_FROM_MEMBER_2."""
    from exitguard.candidate_evaluator import CandidateEvaluator

    # 1. Missing Member 2
    cands_missing = CandidateEvaluator.evaluate_candidates(sample_inventory, member2_recommendations=None)
    assert all(c.gemma_recommendation_status == EvidenceStatus.MISSING_FROM_MEMBER_2.value for c in cands_missing)

    # 2. Heuristic
    cands_heuristic = CandidateEvaluator.evaluate_candidates(
        sample_inventory, member2_recommendations={"provenance": EvidenceStatus.HEURISTIC}
    )
    assert all(c.gemma_recommendation_status == EvidenceStatus.HEURISTIC.value for c in cands_heuristic)

    # 3. Manual stand-in
    cands_manual = CandidateEvaluator.evaluate_candidates(
        sample_inventory, member2_recommendations={"provenance": EvidenceStatus.MANUAL_STAND_IN}
    )
    assert all(c.gemma_recommendation_status == EvidenceStatus.MANUAL_STAND_IN.value for c in cands_manual)

    # 4. AI recommendation
    cands_ai = CandidateEvaluator.evaluate_candidates(
        sample_inventory, member2_recommendations={"provenance": EvidenceStatus.AI_RECOMMENDATION}
    )
    assert all(c.gemma_recommendation_status == EvidenceStatus.AI_RECOMMENDATION.value for c in cands_ai)

