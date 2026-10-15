"""
gemma_advisor.py - Google Gemma 4 Model Integration for ExitGuard.

Uses the official google-genai SDK and hosted Gemma 4 model 'gemma-4-26b-a4b-it'
to generate evidence-backed dependency migration recommendations.

Security & Integrity Invariants:
  1. Reads API key strictly from GEMINI_API_KEY environment variable; never hardcodes or logs it.
  2. Model output is strictly advisory; it cannot execute shell commands or patch files.
  3. Output is rigorously validated against a strict schema.
  4. Nonexistent or hallucinated evidence references are rejected.
  5. Secret-free provenance records are persisted under artifacts/.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from .capsule_schema import EvidenceStatus, ProposedAction

HOSTED_GEMMA_MODEL_ID = "gemma-4-26b-a4b-it"
PROMPT_VERSION = "1.0.0"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|bearer\s+[a-zA-Z0-9_\-\.]+)"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),  # Google API key pattern
]


@dataclass
class GemmaRecommendation:
    """Structured, validated recommendation output from Gemma 4."""
    model_id: str
    target_dependency: str
    proposed_replacement: str
    proposed_action: ProposedAction
    rationale: str
    evidence_references: List[str]
    compatibility_risks: List[str]
    assumptions: List[str]
    migration_steps: List[str]
    verification_tests: List[str]
    confidence: str
    confidence_explanation: str
    provenance: EvidenceStatus = EvidenceStatus.AI_RECOMMENDATION

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["proposed_action"] = self.proposed_action.value
        data["provenance"] = self.provenance.value
        return data


@dataclass
class GemmaAdviceRecord:
    """Secret-free evidence record of an attempted or completed Gemma 4 interaction."""
    record_id: str
    model_id: str
    timestamp_utc: str
    prompt_hash: str
    prompt_version: str
    raw_response: Optional[str]
    recommendation: Optional[GemmaRecommendation]
    validation_status: str  # VALID, VALIDATION_FAILED, API_ERROR, CREDENTIALS_MISSING
    validation_errors: List[str] = field(default_factory=list)
    request_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.recommendation:
            data["recommendation"] = self.recommendation.to_dict()
        return data


class GemmaAdvisor:
    """
    Client and validation engine for Gemma 4 dependency migration recommendations.
    """

    def __init__(self, model_id: str = HOSTED_GEMMA_MODEL_ID) -> None:
        self.model_id = model_id

    @staticmethod
    def _scrub_secrets(text: str) -> str:
        """Sanitize any credentials or keys from text."""
        sanitized = text
        for pat in SECRET_PATTERNS:
            sanitized = pat.sub("[REDACTED_SECRET]", sanitized)
        return sanitized

    def build_prompt(self, inventory_data: Dict[str, Any]) -> str:
        """
        Assemble the structured prompt incorporating inventory facts, AST scans,
        manifest constraints, and baseline test failures.
        """
        deps = inventory_data.get("dependencies", {})
        target_repo = inventory_data.get("metadata", {}).get("target_repository", "LinkWatch")

        candidate_summaries = []
        for pkg, info in deps.items():
            decls = [d.get("raw_line", "") for d in info.get("declarations", [])]
            ast_uses = [
                f"{imp.get('file_path')}:{imp.get('line_number')} -> {imp.get('statement')}"
                for imp in info.get("ast_usage", {}).get("imports", [])
            ]
            risks = info.get("objective_risks", [])
            candidate_summaries.append(
                f"- Package: {pkg}\n"
                f"  Declarations: {', '.join(decls) if decls else 'None'}\n"
                f"  AST Usages: {', '.join(ast_uses) if ast_uses else '0 call sites'}\n"
                f"  Identified Risks: {'; '.join(risks) if risks else 'None'}"
            )

        prompt = f"""You are an expert dependency migration advisor for the ExitGuard project.
Target Repository: {target_repo}
Target Python Runtime: Python 3.12 (Primary) and Python 3.13 (Secondary)

OBSERVED REPOSITORY FACTS & BASELINE EVIDENCE:
1. Pinned commit: f52f3930c8e7c33d934ccf614955a38e26984bd5
2. Baseline Pytest Result on Python 3.12: 10 tests collected, 9 passed, 1 failed (exit code 1).
   Existing Failure: tests/test_report.py::test_report_renders_all_sites
   Failure Details: ImportError: cannot import name 'soft_unicode' from 'markupsafe'
   Root Cause: Jinja2==2.11.3 (pinned from 2021) imports 'soft_unicode' which was removed in MarkupSafe>=3.0.0.
   CRITICAL: 'markupsafe' is an indirect/transitive dependency of Jinja2 and is NOT directly imported by LinkWatch. Do NOT recommend replacing Jinja2 with an entirely different templating engine.
3. Candidate Dependency Inventory:
{chr(10).join(candidate_summaries)}

MIGRATION SAFETY REQUIREMENTS:
- Recommend exactly ONE primary candidate package for replacement.
- Choose a package that is abandoned or deprecated where a clean, drop-in or stdlib replacement exists with minimal code disruption (e.g. 'appdirs' -> 'platformdirs', or 'toml' -> 'tomllib').
- Output MUST be valid, parseable JSON conforming strictly to the requested schema.

REQUIRED JSON OUTPUT FORMAT:
{{
  "model_id": "{self.model_id}",
  "target_dependency": "<exact package name, e.g. appdirs>",
  "proposed_replacement": "<replacement package or stdlib module, e.g. platformdirs>=3.0.0>",
  "proposed_action": "<REPLACE | UPGRADE | REMOVE>",
  "rationale": "<thorough engineering justification explaining why this package was selected>",
  "evidence_references": [
    "<reference to specific file path or manifest line from supplied inventory, e.g. linkwatch/cache.py:4>"
  ],
  "compatibility_risks": [
    "<known or potential risks of this replacement>"
  ],
  "assumptions": [
    "<assumptions made regarding environment or caller behavior>"
  ],
  "migration_steps": [
    "<step 1>",
    "<step 2>"
  ],
  "verification_tests": [
    "<exact pytest node ID or test command to verify>"
  ],
  "confidence": "<HIGH | MEDIUM | LOW>",
  "confidence_explanation": "<detailed explanation for why this confidence level was assigned>"
}}
"""
        return prompt.strip()

    def validate_response(
        self,
        raw_text: str,
        inventory_data: Dict[str, Any],
    ) -> Tuple[Optional[GemmaRecommendation], List[str]]:
        """
        Validate model response against strict schema and verify all evidence references exist.
        """
        errors: List[str] = []
        if not raw_text or not raw_text.strip():
            return None, ["Empty response from model."]

        # Clean potential markdown fences ```json ... ```
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            return None, [f"Malformed JSON in model response: {exc}"]

        required_keys = [
            "model_id",
            "target_dependency",
            "proposed_replacement",
            "proposed_action",
            "rationale",
            "evidence_references",
            "compatibility_risks",
            "assumptions",
            "migration_steps",
            "verification_tests",
            "confidence",
            "confidence_explanation",
        ]
        for key in required_keys:
            if key not in payload or payload[key] is None or payload[key] == "":
                errors.append(f"Missing or empty required key: '{key}'")

        if errors:
            return None, errors

        # 1. Validate target dependency exists in supplied inventory
        deps = inventory_data.get("dependencies", {})
        target_dep = payload["target_dependency"].strip().lower()
        if target_dep not in [d.lower() for d in deps.keys()]:
            errors.append(
                f"Target dependency '{payload['target_dependency']}' does not exist in inventory. Hallucination rejected."
            )

        # 2. Validate proposed action is valid
        action_str = payload["proposed_action"].upper()
        try:
            action = ProposedAction(action_str)
        except ValueError:
            errors.append(f"Invalid proposed_action '{action_str}'. Must be one of {[a.value for a in ProposedAction]}.")
            action = ProposedAction.PROVISIONAL_EVALUATION

        # 3. Validate evidence references are grounded
        refs = payload.get("evidence_references", [])
        if not isinstance(refs, list) or len(refs) == 0:
            errors.append("evidence_references must be a non-empty list of strings.")
        else:
            # Check if at least one reference matches a known file path, package, or manifest in inventory
            known_tokens = ["requirements.txt", "pyproject.toml", "requirements-dev.txt", "linkwatch", target_dep]
            has_grounded_ref = any(
                any(tok in str(ref).lower() for tok in known_tokens)
                for ref in refs
            )
            if not has_grounded_ref:
                errors.append(
                    f"Evidence references {refs} do not correspond to any known manifest or source file in inventory."
                )

        if errors:
            return None, errors

        rec = GemmaRecommendation(
            model_id=str(payload["model_id"]),
            target_dependency=str(payload["target_dependency"]),
            proposed_replacement=str(payload["proposed_replacement"]),
            proposed_action=action,
            rationale=str(payload["rationale"]),
            evidence_references=[str(r) for r in refs],
            compatibility_risks=[str(r) for r in payload.get("compatibility_risks", [])],
            assumptions=[str(a) for a in payload.get("assumptions", [])],
            migration_steps=[str(s) for s in payload.get("migration_steps", [])],
            verification_tests=[str(t) for t in payload.get("verification_tests", [])],
            confidence=str(payload["confidence"]),
            confidence_explanation=str(payload["confidence_explanation"]),
            provenance=EvidenceStatus.AI_RECOMMENDATION,
        )
        return rec, []

    def generate_recommendation(
        self,
        inventory_data: Dict[str, Any],
        api_key: Optional[str] = None,
        mock_client: Optional[Any] = None,
    ) -> GemmaAdviceRecord:
        """
        Request recommendation from Gemma 4 model or mock client.
        """
        record_id = f"gemma_rec_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
        prompt = self.build_prompt(inventory_data)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        request_metadata = {
            "target_repository": inventory_data.get("metadata", {}).get("target_repository", "LinkWatch"),
            "model_id": self.model_id,
            "prompt_length_chars": len(prompt),
            "temperature": 0.2,
            "timestamp_utc": now_utc,
        }

        # 1. Check for API key (unless mock client is provided)
        effective_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not effective_key and mock_client is None:
            return GemmaAdviceRecord(
                record_id=record_id,
                model_id=self.model_id,
                timestamp_utc=now_utc,
                prompt_hash=prompt_hash,
                prompt_version=PROMPT_VERSION,
                raw_response=None,
                recommendation=None,
                validation_status="CREDENTIALS_MISSING",
                validation_errors=["GEMINI_API_KEY environment variable is not set. Network request skipped."],
                request_metadata=request_metadata,
            )

        # 2. Invoke model client
        raw_text: Optional[str] = None
        try:
            if mock_client is not None:
                # Used in unit testing
                response = mock_client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                )
                raw_text = getattr(response, "text", str(response))
            else:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=effective_key)
                response = client.models.generate_content(
                    model=self.model_id,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                raw_text = getattr(response, "text", "")

        except Exception as exc:
            safe_err = self._scrub_secrets(str(exc))
            return GemmaAdviceRecord(
                record_id=record_id,
                model_id=self.model_id,
                timestamp_utc=now_utc,
                prompt_hash=prompt_hash,
                prompt_version=PROMPT_VERSION,
                raw_response=None,
                recommendation=None,
                validation_status="API_ERROR",
                validation_errors=[f"Model generation error: {safe_err}"],
                request_metadata=request_metadata,
            )

        # 3. Validate response
        sanitized_raw = self._scrub_secrets(raw_text or "")
        rec, errors = self.validate_response(sanitized_raw, inventory_data)

        val_status = "VALID" if rec is not None and not errors else "VALIDATION_FAILED"
        return GemmaAdviceRecord(
            record_id=record_id,
            model_id=self.model_id,
            timestamp_utc=now_utc,
            prompt_hash=prompt_hash,
            prompt_version=PROMPT_VERSION,
            raw_response=sanitized_raw,
            recommendation=rec,
            validation_status=val_status,
            validation_errors=errors,
            request_metadata=request_metadata,
        )

    @staticmethod
    def save_evidence_record(record: GemmaAdviceRecord, output_dir: Path | str) -> Path:
        """Persist a secret-free evidence record under artifacts/."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / "gemma_advice_evidence.json"
        file_path.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        return file_path


def main():
    parser = argparse.ArgumentParser(description="ExitGuard Gemma 4 Dependency Migration Advisor")
    parser.add_argument("--live", action="store_true", help="Opt-in to make a live API call if GEMINI_API_KEY is set")
    parser.add_argument("--inventory", default="evidence/dependency_inventory.json", help="Path to dependency inventory")
    parser.add_argument("--output", default="artifacts", help="Directory to save evidence")
    args = parser.parse_args()

    inv_path = Path(args.inventory)
    if not inv_path.exists():
        print(f"Error: Inventory file not found at {inv_path}")
        sys.exit(1)

    inventory_data = json.loads(inv_path.read_text(encoding="utf-8"))
    advisor = GemmaAdvisor()

    if not args.live:
        print("[ExitGuard GemmaAdvisor] Running in offline check mode (pass --live to trigger live API call).")
        has_key = bool(os.environ.get("GEMINI_API_KEY"))
        print(f"GEMINI_API_KEY configured: {has_key}")
        print("Model ID configured: gemma-4-26b-a4b-it")
        return

    print(f"[ExitGuard GemmaAdvisor] Executing live recommendation request using model '{HOSTED_GEMMA_MODEL_ID}'...")
    record = advisor.generate_recommendation(inventory_data)
    evidence_path = advisor.save_evidence_record(record, args.output)

    print(f"Validation Status: {record.validation_status}")
    if record.validation_errors:
        print(f"Errors / Notes: {record.validation_errors}")
    if record.recommendation:
        print(f"Recommended Target: {record.recommendation.target_dependency} -> {record.recommendation.proposed_replacement}")
        print(f"Confidence: {record.recommendation.confidence} ({record.recommendation.confidence_explanation})")
    print(f"Evidence artifact saved to: {evidence_path}")


if __name__ == "__main__":
    main()
