"""IG-04 unified GA4 analytical plane. Compiles proven identity; does not mint IDs."""

from app.identity_graph.analytics.adapter import InMemoryAnalyticalAdapter
from app.identity_graph.analytics.compiler import compile_unified_analytics

__all__ = ["InMemoryAnalyticalAdapter", "compile_unified_analytics"]
