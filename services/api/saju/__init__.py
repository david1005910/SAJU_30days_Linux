"""
Saju calculation engine - Deterministic Korean fortune-telling calculations
"""

from .constants import GAN, ZHI, FIVE_ELEMENTS, TEN_GODS

try:
    from .engine import SajuEngine, SajuResult
except Exception:
    from .mock_engine import MockSajuEngine as SajuEngine, SajuResult  # type: ignore

__all__ = ["SajuEngine", "SajuResult", "GAN", "ZHI", "FIVE_ELEMENTS", "TEN_GODS"]