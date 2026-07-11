from .base import OptimizedPlan, RewriteEvent
from .engine import Optimizer
from .rules import (
    BoolFlattenRule, ConstFoldRule, ConstraintMergeRule, FilterMergeRule,
    FilterPushDownRule, LimitNormalizeRule, PredicateDedupRule,
    RankContractNormalizeRule, StageNormalizeRule,
)

DEFAULT_RULES = (
    BoolFlattenRule(), ConstFoldRule(), PredicateDedupRule(), ConstraintMergeRule(),
    FilterPushDownRule(), FilterMergeRule(), StageNormalizeRule(),
    LimitNormalizeRule(), RankContractNormalizeRule(),
)

__all__ = [name for name in globals() if not name.startswith("_")]
