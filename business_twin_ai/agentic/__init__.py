"""Agentic AI layer — multi-agent orchestration with a visible reasoning trace.

The orchestrator runs specialized agents (financial, market, supply chain,
strategy) through a plan → act → observe → reflect loop. Every tool call and
observation is recorded in a `steps` trace so the UI can show *how* the AI
arrived at its answer — the centerpiece for agentic-AI demos.

When an LLM API key is configured the agents use real LLM reasoning; otherwise
they degrade gracefully to rule-based + news-powered intelligence so the demo
never breaks.
"""

from business_twin_ai.agentic.orchestrator import AgenticOrchestrator

__all__ = ["AgenticOrchestrator"]
