from __future__ import annotations

from typing import Any, Iterable

from antlr4 import ParserRuleContext

from ...official_slot import (
    OfficialBinaryOp,
    OfficialComparison,
    OfficialFunctionCall,
    OfficialIdentifier,
    OfficialLimit,
    OfficialLiteral,
    OfficialNode,
    OfficialRangeLiteral,
    _parse_range_text,
)
from .generated.OfficialSlotParser import OfficialSlotParser
from .generated.OfficialSlotVisitor import OfficialSlotVisitor
from .protocol import SourceMap, SourceSpan


class OfficialAstAdapter(OfficialSlotVisitor):
    def __init__(self, source: str):
        self.source = source
        self.source_map = SourceMap()

    def _record(self, node: OfficialNode, ctx: ParserRuleContext) -> OfficialNode:
        start = max(0, ctx.start.start)
        stop = ctx.stop.stop + 1 if ctx.stop is not None else start
        fragment = self.source[start:stop]
        lines = fragment.splitlines(keepends=True)
        if len(lines) <= 1:
            end_line = ctx.start.line
            end_column = ctx.start.column + len(fragment) + 1
        else:
            end_line = ctx.start.line + len(lines) - 1
            end_column = len(lines[-1].rstrip("\r\n")) + 1
        span = SourceSpan(start, stop, ctx.start.line, ctx.start.column + 1, end_line, end_column, fragment)
        return self.source_map.record(node, span)

    def _fold(self, children: Iterable[Any], ctx: ParserRuleContext) -> OfficialNode:
        items = list(children)
        node = self.visit(items[0])
        for index in range(1, len(items), 2):
            op = items[index].getText().lower()
            node = self._record(OfficialBinaryOp(op, node, self.visit(items[index + 1])), ctx)
        return node

    def visitProgram(self, ctx: OfficialSlotParser.ProgramContext):
        return self.visit(ctx.limitExpression())

    def visitLimitExpression(self, ctx: OfficialSlotParser.LimitExpressionContext):
        node = self.visit(ctx.thenExpression())
        values = ctx.signedInteger()
        if values:
            node = OfficialLimit(node, int(values[0].getText()), int(values[1].getText()))
        return self._record(node, ctx)

    def visitThenExpression(self, ctx: OfficialSlotParser.ThenExpressionContext):
        return self._fold(ctx.children, ctx)

    def visitOrExpression(self, ctx: OfficialSlotParser.OrExpressionContext):
        return self._fold(ctx.children, ctx)

    def visitAndExpression(self, ctx: OfficialSlotParser.AndExpressionContext):
        return self._fold(ctx.children, ctx)

    def visitComparisonExpression(self, ctx: OfficialSlotParser.ComparisonExpressionContext):
        left = self.visit(ctx.additiveExpression(0))
        if ctx.BETWEEN():
            right = self.visit(ctx.rangeLiteral())
            return self._record(OfficialComparison("between", left, right), ctx)
        if ctx.comparisonOperator():
            right = self.visit(ctx.additiveExpression(1))
            return self._record(OfficialComparison(ctx.comparisonOperator().getText(), left, right), ctx)
        return left

    def visitAdditiveExpression(self, ctx: OfficialSlotParser.AdditiveExpressionContext):
        return self._fold(ctx.children, ctx)

    def visitMultiplicativeExpression(self, ctx: OfficialSlotParser.MultiplicativeExpressionContext):
        return self._fold(ctx.children, ctx)

    def visitPrimaryExpression(self, ctx: OfficialSlotParser.PrimaryExpressionContext):
        if ctx.functionCall():
            return self.visit(ctx.functionCall())
        if ctx.literal():
            return self.visit(ctx.literal())
        if ctx.IDENT():
            return self._record(OfficialIdentifier(ctx.IDENT().getText()), ctx)
        return self.visit(ctx.thenExpression())

    def visitFunctionCall(self, ctx: OfficialSlotParser.FunctionCallContext):
        args = [] if ctx.argumentList() is None else [self.visit(item) for item in ctx.argumentList().thenExpression()]
        return self._record(OfficialFunctionCall(ctx.IDENT().getText(), args), ctx)

    def visitRangeLiteral(self, ctx: OfficialSlotParser.RangeLiteralContext):
        if ctx.STRING():
            value = _decode_string(ctx.STRING().getText())
            parsed = _parse_range_text(value)
            return self._record(parsed if parsed is not None else OfficialLiteral(value), ctx)
        values = ctx.additiveExpression()
        node = OfficialRangeLiteral(
            self.visit(values[0]),
            self.visit(values[1]),
            ctx.rangeBracketOpen().getText() == "[",
            ctx.rangeBracketClose().getText() == "]",
        )
        return self._record(node, ctx)

    def visitLiteral(self, ctx: OfficialSlotParser.LiteralContext):
        text = ctx.getText()
        lower = text.lower()
        if ctx.STRING():
            value: Any = _decode_string(text)
        elif ctx.signedPercent():
            value = text.lstrip("+")
        elif ctx.signedNumber():
            value = float(text) if "." in text else int(text)
        else:
            value = lower == "true"
        return self._record(OfficialLiteral(value), ctx)


def _decode_string(text: str) -> str:
    body = text[1:-1]
    result = []
    index = 0
    while index < len(body):
        if body[index] == "\\" and index + 1 < len(body):
            index += 1
        result.append(body[index])
        index += 1
    return "".join(result)
