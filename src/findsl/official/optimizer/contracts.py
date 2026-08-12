from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Mapping, Tuple


class RuleContractError(ValueError):
    pass


@dataclass(frozen=True)
class RuleContract:
    rule_id: str
    preconditions: Tuple[str, ...]
    semantic_invariant: str
    fallback: str
    validation_strategy: str

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["preconditions"] = list(self.preconditions)
        return payload


_CONTRACTS: Mapping[str, RuleContract] = {
    "BOOL_FLATTEN": RuleContract(
        "BOOL_FLATTEN",
        ("operator is AND or OR", "only parenthesization changes"),
        "Operand order and three-valued boolean meaning remain unchanged.",
        "Keep the original boolean tree when the shape is not associative.",
        "IR interpreter differential comparison on null-free official predicates.",
    ),
    "CONST_FOLD": RuleContract(
        "CONST_FOLD",
        ("all operands are typed literals", "operator is pure", "division denominator is non-zero"),
        "The replacement literal has the same type and value as runtime evaluation.",
        "Leave the expression intact when purity, type, or arithmetic safety is uncertain.",
        "Property cases compare folded and original interpreter results.",
    ),
    "PREDICATE_DEDUP": RuleContract(
        "PREDICATE_DEDUP",
        ("operator is idempotent AND or OR", "operand node IDs are identical"),
        "Removing a duplicate predicate preserves the candidate row set.",
        "Retain both operands unless structural identity is proven.",
        "Before/after row-set differential test.",
    ),
    "CONSTRAINT_MERGE": RuleContract(
        "CONSTRAINT_MERGE",
        ("constraints are adjacent", "market/date intersections are representable exactly"),
        "The merged market/date domain equals the intersection of both constraints.",
        "Keep separate constraints or return a proven empty plan.",
        "Set-intersection and conflicting-date cases.",
    ),
    "FILTER_PUSH_DOWN": RuleContract(
        "FILTER_PUSH_DOWN",
        ("predicate is row-local", "constraint introduces no aggregation or ordering barrier"),
        "Filtering before or after the declarative market/date restriction returns the same rows.",
        "Keep the filter above the constraint for non-local expressions.",
        "IR interpreter differential comparison.",
    ),
    "FILTER_MERGE": RuleContract(
        "FILTER_MERGE",
        ("filters are adjacent", "no stage, rank, aggregate, or set barrier intervenes"),
        "Sequential filters equal one conjunctive filter under the project boolean policy.",
        "Keep adjacent filters when a semantic barrier exists.",
        "Before/after row-set differential comparison.",
    ),
    "STAGE_NORMALIZE": RuleContract(
        "STAGE_NORMALIZE",
        ("stage index is metadata", "operation order is unchanged"),
        "Renumbering stages never changes the stage input or operation graph.",
        "Preserve the original index if the stage chain is malformed.",
        "Canonical plan hash and stage-order assertions.",
    ),
    "LIMIT_NORMALIZE": RuleContract(
        "LIMIT_NORMALIZE",
        ("limits are nested", "both counts are finite integers"),
        "The normalized offset/count identifies the same ordered slice.",
        "Keep nested limits when either count is open-ended.",
        "Boundary examples for offsets, exhaustion, and empty slices.",
    ),
    "RANK_CONTRACT_NORMALIZE": RuleContract(
        "RANK_CONTRACT_NORMALIZE",
        ("rank direction is case-insensitive", "unary plus has no numeric effect"),
        "Direction, rank population, bound, and tie policy remain unchanged.",
        "Keep the original rank contract if normalization cannot be proven local.",
        "Direct, aggregate, percentage, range, and staged-rank regressions.",
    ),
}


def contract_for(rule_id: str) -> RuleContract:
    try:
        return _CONTRACTS[rule_id]
    except KeyError as exc:
        raise RuleContractError(f"optimizer rule has no declared contract: {rule_id}") from exc


def validate_rule_contracts(rules: Iterable[Any]) -> Tuple[RuleContract, ...]:
    result = tuple(contract_for(str(rule.rule_id)) for rule in rules)
    identifiers = [item.rule_id for item in result]
    if len(identifiers) != len(set(identifiers)):
        raise RuleContractError("optimizer rule IDs must be unique")
    return result


def rule_contract_catalog() -> Tuple[RuleContract, ...]:
    return tuple(_CONTRACTS[key] for key in sorted(_CONTRACTS))
