from sqlglot import exp

from ..physical.runtime import current_semantic_policy
from .errors import DorisBackendError


def rank_function():
    policy = current_semantic_policy()
    method = policy.ranking.method if policy else "row_number"
    if method == "row_number":
        return exp.RowNumber()
    if method == "rank":
        return exp.Rank()
    if method == "dense_rank":
        return exp.DenseRank()
    raise DorisBackendError("DORIS_RANK_POLICY_UNSUPPORTED", f"unsupported rank method {method}")


def rank_order(metric, descending: bool, table: str) -> exp.Order:
    policy = current_semantic_policy()
    method = policy.ranking.method if policy else "row_number"
    null_order = policy.ranking.metric_null_order if policy else "engine_default"
    if null_order == "exclude":
        raise DorisBackendError(
            "DORIS_RANK_NULL_POLICY_UNSUPPORTED",
            "rank NULL exclusion requires an explicit pre-rank filter",
        )
    expressions = []
    if metric is not None:
        kwargs = {"this": metric, "desc": descending}
        if null_order == "first":
            kwargs["nulls_first"] = True
        elif null_order == "last":
            kwargs["nulls_first"] = False
        expressions.append(exp.Ordered(**kwargs))
    if method == "row_number":
        tie_breakers = policy.ranking.tie_breakers if policy else ("mktcode", "tgtcode")
        expressions.extend(
            exp.Ordered(
                this=exp.column(name, table=table, quoted=True),
                desc=False,
                nulls_first=True,
            )
            for name in tie_breakers
        )
    return exp.Order(expressions=expressions)
