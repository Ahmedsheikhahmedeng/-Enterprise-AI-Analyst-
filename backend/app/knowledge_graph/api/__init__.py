"""Knowledge Graph API package exports."""

from app.knowledge_graph.api.routes import router as graph_router

__all__ = ["graph_router"]
