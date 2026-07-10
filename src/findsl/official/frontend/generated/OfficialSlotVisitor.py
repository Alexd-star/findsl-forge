# Generated from D:/Luo_docs/竞赛/研创赛/研究生金融科技创新大赛/findsl-forge/.worktrees/architecture-hardening/grammar/OfficialSlot.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .OfficialSlotParser import OfficialSlotParser
else:
    from OfficialSlotParser import OfficialSlotParser

# This class defines a complete generic visitor for a parse tree produced by OfficialSlotParser.

class OfficialSlotVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by OfficialSlotParser#program.
    def visitProgram(self, ctx:OfficialSlotParser.ProgramContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#limitExpression.
    def visitLimitExpression(self, ctx:OfficialSlotParser.LimitExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#thenExpression.
    def visitThenExpression(self, ctx:OfficialSlotParser.ThenExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#orExpression.
    def visitOrExpression(self, ctx:OfficialSlotParser.OrExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#andExpression.
    def visitAndExpression(self, ctx:OfficialSlotParser.AndExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#comparisonExpression.
    def visitComparisonExpression(self, ctx:OfficialSlotParser.ComparisonExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#additiveExpression.
    def visitAdditiveExpression(self, ctx:OfficialSlotParser.AdditiveExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#multiplicativeExpression.
    def visitMultiplicativeExpression(self, ctx:OfficialSlotParser.MultiplicativeExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#primaryExpression.
    def visitPrimaryExpression(self, ctx:OfficialSlotParser.PrimaryExpressionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#functionCall.
    def visitFunctionCall(self, ctx:OfficialSlotParser.FunctionCallContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#argumentList.
    def visitArgumentList(self, ctx:OfficialSlotParser.ArgumentListContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#rangeLiteral.
    def visitRangeLiteral(self, ctx:OfficialSlotParser.RangeLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#rangeBracketOpen.
    def visitRangeBracketOpen(self, ctx:OfficialSlotParser.RangeBracketOpenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#rangeBracketClose.
    def visitRangeBracketClose(self, ctx:OfficialSlotParser.RangeBracketCloseContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#literal.
    def visitLiteral(self, ctx:OfficialSlotParser.LiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#signedInteger.
    def visitSignedInteger(self, ctx:OfficialSlotParser.SignedIntegerContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#signedNumber.
    def visitSignedNumber(self, ctx:OfficialSlotParser.SignedNumberContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#signedPercent.
    def visitSignedPercent(self, ctx:OfficialSlotParser.SignedPercentContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by OfficialSlotParser#comparisonOperator.
    def visitComparisonOperator(self, ctx:OfficialSlotParser.ComparisonOperatorContext):
        return self.visitChildren(ctx)



del OfficialSlotParser