from .base import OptimizedPlan, RewriteEvent
from .engine import Optimizer
from .rules import ConstFoldRule, FilterMergeRule, LimitNormalizeRule, PredicateDedupRule

DEFAULT_RULES = (ConstFoldRule(), PredicateDedupRule(), FilterMergeRule(), LimitNormalizeRule())

__all__ = [name for name in globals() if not name.startswith("_")]
