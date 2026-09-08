"""Redirect module exposing agent router at app/api/v1/agents.py."""

from app.agents.router import router

__all__ = ["router"]
