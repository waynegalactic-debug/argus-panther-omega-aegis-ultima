"""Phoenix Shield unique engines integrated into US IPFORCE / AEGIS.

Sourced from the Kimi Agent full-chain Python package after exhaustive review.
Modules that duplicated existing monolith forensics, IP/blockchain clients,
evidence hardening, or text report generators were intentionally excluded.
Placeholder community API keys were stripped; credentials resolve from env.
"""

from .binance_enhanced import BinanceEnhancedEngine
from .document_generation_engine import DocumentGenerationEngine
from .genius_act_smart_contracts import GeniusActSmartContractEngine
from .gildata_a_share_engine import GildataAShareEngine
from .intelligence_analysis_engine import IntelligenceAnalysisEngine
from .macro_intelligence import MacroIntelligenceEngine
from .neon_persistence import NeonPersistenceEngine
from .prosecutorial_gap_analyzer import ProsecutorialGapAnalyzer
from .scholar_ip_engine import ScholarIPEngine

__all__ = [
    "BinanceEnhancedEngine",
    "DocumentGenerationEngine",
    "GeniusActSmartContractEngine",
    "GildataAShareEngine",
    "IntelligenceAnalysisEngine",
    "MacroIntelligenceEngine",
    "NeonPersistenceEngine",
    "ProsecutorialGapAnalyzer",
    "ScholarIPEngine",
]
