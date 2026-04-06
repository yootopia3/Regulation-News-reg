"""2-Tier Hybrid Analyzer package."""

from src.services.analyzer.hybrid import HybridAnalyzer

# Backward compatibility alias
RegulationAnalyzer = HybridAnalyzer

__all__ = ["HybridAnalyzer", "RegulationAnalyzer"]
