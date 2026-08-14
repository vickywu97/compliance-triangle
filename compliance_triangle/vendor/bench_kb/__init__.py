# Fallback copy of legal-hallucination-bench knowledge_base loader.
# See compliance_triangle/kb.py for primary vs fallback loading logic.
from .loader import load_laws

__all__ = ["load_laws"]
