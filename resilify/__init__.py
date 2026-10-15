"""
Resilify - AI-Assisted Dependency Resilience and Exit Capsule Generator
Track 1: Gemma 4 Dependency Resilience

Member 1: Static Analysis, Manifests & Baseline Evidence Collector
Member 2: Gemma 4 AI Reasoning & Migration Patch Builder
"""

from .collector import BaselineEvidenceCollector
from .risk_gate import RiskEvaluationGate, RiskCategory, RiskEvidenceItem
from .gemma_client import GemmaMigrationClient, GemmaMigrationProposal
from .patch_synthesizer import PatchSynthesizer
from .gemma_orchestrator import GemmaMigrationOrchestrator

__version__ = "0.2.0"

__all__ = [
    "BaselineEvidenceCollector",
    "RiskEvaluationGate",
    "RiskCategory",
    "RiskEvidenceItem",
    "GemmaMigrationClient",
    "GemmaMigrationProposal",
    "PatchSynthesizer",
    "GemmaMigrationOrchestrator",
]
