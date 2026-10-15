"""Resilify UI module.

Provides a developer workstation dashboard for inspecting dependency resilience,
Gemma migration recommendations, baseline vs. candidate verification runs,
and Dependency Exit Capsules.
"""

from .server import start_server

__all__ = ["start_server"]
