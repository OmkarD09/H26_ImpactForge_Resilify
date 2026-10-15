"""
Risk Evaluation Gate for Resilify (Member 2).

Enforces the core hackathon principle:
"Do not invent risk. If no evidence of risk or usage exists, record as unknown / unverified."

Evaluates static analysis, AST scan, manifest, and test evidence collected by Member 1
to classify dependencies into actionable categories without hallucinating risks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class RiskCategory(str, Enum):
    ACTIONABLE_RISK = "ACTIONABLE_RISK"
    BENIGN_ACTIVE = "BENIGN_ACTIVE"
    UNVERIFIED_UNKNOWN = "UNVERIFIED_UNKNOWN"


class RiskFactorType(str, Enum):
    RUNTIME_EXECUTION_FAILURE = "RUNTIME_EXECUTION_FAILURE"
    BROKEN_DEV_TOOL = "BROKEN_DEV_TOOL"
    DEPRECATED_RUNTIME_API = "DEPRECATED_RUNTIME_API"
    GHOST_DEPENDENCY = "GHOST_DEPENDENCY"
    TRANSITIVE_PIN_RISK = "TRANSITIVE_PIN_RISK"
    MANIFEST_CONFLICT = "MANIFEST_CONFLICT"
    PYPI_DEPRECATION = "PYPI_DEPRECATION"
    OUTDATED_VERSION = "OUTDATED_VERSION"


@dataclass
class RiskEvidenceItem:
    factor_type: RiskFactorType
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, INFO
    description: str
    source: str  # "test_execution", "ast_scan", "manifest_conflict", "dynamic_inspection", "pypi"
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvaluatedDependency:
    package_name: str
    normalized_name: str
    risk_category: RiskCategory
    is_ast_used: bool
    pinned_specifiers: List[str]
    pypi_latest_version: Optional[str]
    evidence_items: List[RiskEvidenceItem] = field(default_factory=list)
    risk_summary: str = ""
    can_ai_reason: bool = False


class RiskEvaluationGate:
    """
    Strict filter gate that prevents AI hallucination by only advancing
    dependencies that have verified objective evidence of risk or obsolescence.
    """

    def __init__(self, inventory_data: Dict[str, Any]) -> None:
        self.inventory = inventory_data
        self.evaluated_dependencies: Dict[str, EvaluatedDependency] = {}

    def evaluate(self) -> Dict[str, EvaluatedDependency]:
        """
        Processes inventory data and returns evaluated dependencies.
        """
        deps_data = self.inventory.get("dependencies", {})
        manifest_deps = self.inventory.get("manifest_summary", {}).get("dependencies", {})

        all_package_names = set(deps_data.keys()) or set(manifest_deps.keys())

        for pkg in sorted(all_package_names):
            norm_pkg = pkg.lower().replace("-", "_")
            pkg_info = deps_data.get(pkg, {})

            # 1. Declarations & Specifiers
            declarations = pkg_info.get("declarations", [])
            if not declarations and pkg in manifest_deps:
                declarations = manifest_deps[pkg]
            specifiers = [d.get("specifier", "any") for d in declarations if isinstance(d, dict)]

            # 2. AST usage
            ast_entry = pkg_info.get("ast_usage", {})
            is_used = bool(ast_entry.get("is_imported") or ast_entry.get("call_sites") or ast_entry.get("import_locations"))

            # 3. PyPI metadata
            pypi_entry = pkg_info.get("pypi_metadata", {})
            latest_ver = pypi_entry.get("latest_version")

            # 4. Objective risks parsing
            evidence_items: List[RiskEvidenceItem] = []
            raw_risks = pkg_info.get("objective_risks", [])

            for r in raw_risks:
                r_str = str(r)
                if r_str.startswith("RUNTIME_EXECUTION_FAILURE:"):
                    evidence_items.append(RiskEvidenceItem(
                        factor_type=RiskFactorType.RUNTIME_EXECUTION_FAILURE,
                        severity="CRITICAL",
                        description=r_str.split(":", 1)[1].strip(),
                        source="test_execution",
                    ))
                elif r_str.startswith("BROKEN_DEV_TOOL:"):
                    evidence_items.append(RiskEvidenceItem(
                        factor_type=RiskFactorType.BROKEN_DEV_TOOL,
                        severity="HIGH",
                        description=r_str.split(":", 1)[1].strip(),
                        source="dynamic_inspection",
                    ))
                elif r_str.startswith("DEPRECATED_RUNTIME_API:"):
                    evidence_items.append(RiskEvidenceItem(
                        factor_type=RiskFactorType.DEPRECATED_RUNTIME_API,
                        severity="HIGH",
                        description=r_str.split(":", 1)[1].strip(),
                        source="dynamic_inspection",
                    ))
                elif r_str.startswith("GHOST_DEPENDENCY:"):
                    evidence_items.append(RiskEvidenceItem(
                        factor_type=RiskFactorType.GHOST_DEPENDENCY,
                        severity="MEDIUM",
                        description=r_str.split(":", 1)[1].strip(),
                        source="dynamic_inspection",
                    ))
                elif r_str.startswith("TRANSITIVE_PIN_RISK:"):
                    evidence_items.append(RiskEvidenceItem(
                        factor_type=RiskFactorType.TRANSITIVE_PIN_RISK,
                        severity="HIGH",
                        description=r_str.split(":", 1)[1].strip(),
                        source="dynamic_inspection",
                    ))
                elif r_str.startswith("MANIFEST_CONFLICT:"):
                    evidence_items.append(RiskEvidenceItem(
                        factor_type=RiskFactorType.MANIFEST_CONFLICT,
                        severity="HIGH",
                        description=r_str.split(":", 1)[1].strip(),
                        source="manifest_conflict",
                    ))
                elif r_str.startswith("PYPI_DEPRECATION:"):
                    evidence_items.append(RiskEvidenceItem(
                        factor_type=RiskFactorType.PYPI_DEPRECATION,
                        severity="HIGH",
                        description=r_str.split(":", 1)[1].strip(),
                        source="pypi",
                    ))
                elif r_str.startswith("OUTDATED:"):
                    evidence_items.append(RiskEvidenceItem(
                        factor_type=RiskFactorType.OUTDATED_VERSION,
                        severity="LOW",
                        description=r_str.split(":", 1)[1].strip(),
                        source="pypi",
                    ))

            # Filter for critical/high action triggers
            critical_high_evidence = [
                e for e in evidence_items
                if e.severity in ("CRITICAL", "HIGH") or e.factor_type in (
                    RiskFactorType.RUNTIME_EXECUTION_FAILURE,
                    RiskFactorType.GHOST_DEPENDENCY,
                    RiskFactorType.BROKEN_DEV_TOOL,
                    RiskFactorType.DEPRECATED_RUNTIME_API,
                    RiskFactorType.MANIFEST_CONFLICT,
                    RiskFactorType.TRANSITIVE_PIN_RISK,
                    RiskFactorType.PYPI_DEPRECATION,
                )
            ]

            if critical_high_evidence:
                category = RiskCategory.ACTIONABLE_RISK
                can_ai = True
                summary = f"Identified {len(evidence_items)} verified risk factor(s) requiring migration or removal."
            elif is_used:
                category = RiskCategory.BENIGN_ACTIVE
                can_ai = False  # DO NOT INVENT RISK: Actively working, no risk evidence
                summary = "Active dependency with no breaking risks or deprecations. Retain as-is."
            else:
                category = RiskCategory.UNVERIFIED_UNKNOWN
                can_ai = False
                summary = "No verified usage or breaking risk evidence found. Retaining unverified state."

            self.evaluated_dependencies[pkg] = EvaluatedDependency(
                package_name=pkg,
                normalized_name=norm_pkg,
                risk_category=category,
                is_ast_used=is_used,
                pinned_specifiers=specifiers,
                pypi_latest_version=latest_ver,
                evidence_items=evidence_items,
                risk_summary=summary,
                can_ai_reason=can_ai,
            )

        return self.evaluated_dependencies

    def get_actionable_dependencies(self) -> List[EvaluatedDependency]:
        return [
            d for d in self.evaluated_dependencies.values()
            if d.risk_category == RiskCategory.ACTIONABLE_RISK
        ]

    def get_benign_dependencies(self) -> List[EvaluatedDependency]:
        return [
            d for d in self.evaluated_dependencies.values()
            if d.risk_category == RiskCategory.BENIGN_ACTIVE
        ]

    def get_unknown_dependencies(self) -> List[EvaluatedDependency]:
        return [
            d for d in self.evaluated_dependencies.values()
            if d.risk_category == RiskCategory.UNVERIFIED_UNKNOWN
        ]
