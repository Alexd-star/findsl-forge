# Generated from D:/Luo_docs/竞赛/研创赛/研究生金融科技创新大赛/findsl-forge/.worktrees/architecture-hardening/grammar/OfficialSlot.g4 by ANTLR 4.13.2
# encoding: utf-8
from antlr4 import *
from io import StringIO
import sys
if sys.version_info[1] > 5:
	from typing import TextIO
else:
	from typing.io import TextIO

def serializedATN():
    return [
        4,1,28,155,2,0,7,0,2,1,7,1,2,2,7,2,2,3,7,3,2,4,7,4,2,5,7,5,2,6,7,
        6,2,7,7,7,2,8,7,8,2,9,7,9,2,10,7,10,2,11,7,11,2,12,7,12,2,13,7,13,
        2,14,7,14,2,15,7,15,2,16,7,16,2,17,7,17,1,0,1,0,1,0,1,1,1,1,1,1,
        1,1,1,1,1,1,3,1,46,8,1,1,2,1,2,1,2,5,2,51,8,2,10,2,12,2,54,9,2,1,
        3,1,3,1,3,5,3,59,8,3,10,3,12,3,62,9,3,1,4,1,4,1,4,5,4,67,8,4,10,
        4,12,4,70,9,4,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,1,5,3,5,81,8,5,1,6,
        1,6,1,6,5,6,86,8,6,10,6,12,6,89,9,6,1,7,1,7,1,7,5,7,94,8,7,10,7,
        12,7,97,9,7,1,8,1,8,1,8,1,8,1,8,1,8,1,8,3,8,106,8,8,1,9,1,9,1,9,
        3,9,111,8,9,1,9,1,9,1,10,1,10,1,10,5,10,118,8,10,10,10,12,10,121,
        9,10,1,11,1,11,1,11,1,11,1,11,1,11,1,11,3,11,130,8,11,1,12,1,12,
        1,13,1,13,1,14,1,14,1,14,1,14,1,14,3,14,141,8,14,1,15,3,15,144,8,
        15,1,15,1,15,1,16,3,16,149,8,16,1,16,1,16,1,17,1,17,1,17,0,0,18,
        0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,0,5,1,0,15,16,1,
        0,17,18,2,0,19,19,21,21,2,0,20,20,22,22,1,0,8,14,156,0,36,1,0,0,
        0,2,39,1,0,0,0,4,47,1,0,0,0,6,55,1,0,0,0,8,63,1,0,0,0,10,80,1,0,
        0,0,12,82,1,0,0,0,14,90,1,0,0,0,16,105,1,0,0,0,18,107,1,0,0,0,20,
        114,1,0,0,0,22,129,1,0,0,0,24,131,1,0,0,0,26,133,1,0,0,0,28,140,
        1,0,0,0,30,143,1,0,0,0,32,148,1,0,0,0,34,152,1,0,0,0,36,37,3,2,1,
        0,37,38,5,0,0,1,38,1,1,0,0,0,39,45,3,4,2,0,40,41,5,5,0,0,41,42,3,
        30,15,0,42,43,5,23,0,0,43,44,3,30,15,0,44,46,1,0,0,0,45,40,1,0,0,
        0,45,46,1,0,0,0,46,3,1,0,0,0,47,52,3,6,3,0,48,49,5,3,0,0,49,51,3,
        6,3,0,50,48,1,0,0,0,51,54,1,0,0,0,52,50,1,0,0,0,52,53,1,0,0,0,53,
        5,1,0,0,0,54,52,1,0,0,0,55,60,3,8,4,0,56,57,5,2,0,0,57,59,3,8,4,
        0,58,56,1,0,0,0,59,62,1,0,0,0,60,58,1,0,0,0,60,61,1,0,0,0,61,7,1,
        0,0,0,62,60,1,0,0,0,63,68,3,10,5,0,64,65,5,1,0,0,65,67,3,10,5,0,
        66,64,1,0,0,0,67,70,1,0,0,0,68,66,1,0,0,0,68,69,1,0,0,0,69,9,1,0,
        0,0,70,68,1,0,0,0,71,72,3,12,6,0,72,73,5,4,0,0,73,74,3,22,11,0,74,
        81,1,0,0,0,75,76,3,12,6,0,76,77,3,34,17,0,77,78,3,12,6,0,78,81,1,
        0,0,0,79,81,3,12,6,0,80,71,1,0,0,0,80,75,1,0,0,0,80,79,1,0,0,0,81,
        11,1,0,0,0,82,87,3,14,7,0,83,84,7,0,0,0,84,86,3,14,7,0,85,83,1,0,
        0,0,86,89,1,0,0,0,87,85,1,0,0,0,87,88,1,0,0,0,88,13,1,0,0,0,89,87,
        1,0,0,0,90,95,3,16,8,0,91,92,7,1,0,0,92,94,3,16,8,0,93,91,1,0,0,
        0,94,97,1,0,0,0,95,93,1,0,0,0,95,96,1,0,0,0,96,15,1,0,0,0,97,95,
        1,0,0,0,98,99,5,19,0,0,99,100,3,4,2,0,100,101,5,20,0,0,101,106,1,
        0,0,0,102,106,3,18,9,0,103,106,3,28,14,0,104,106,5,26,0,0,105,98,
        1,0,0,0,105,102,1,0,0,0,105,103,1,0,0,0,105,104,1,0,0,0,106,17,1,
        0,0,0,107,108,5,26,0,0,108,110,5,19,0,0,109,111,3,20,10,0,110,109,
        1,0,0,0,110,111,1,0,0,0,111,112,1,0,0,0,112,113,5,20,0,0,113,19,
        1,0,0,0,114,119,3,4,2,0,115,116,5,23,0,0,116,118,3,4,2,0,117,115,
        1,0,0,0,118,121,1,0,0,0,119,117,1,0,0,0,119,120,1,0,0,0,120,21,1,
        0,0,0,121,119,1,0,0,0,122,123,3,24,12,0,123,124,3,12,6,0,124,125,
        5,23,0,0,125,126,3,12,6,0,126,127,3,26,13,0,127,130,1,0,0,0,128,
        130,5,27,0,0,129,122,1,0,0,0,129,128,1,0,0,0,130,23,1,0,0,0,131,
        132,7,2,0,0,132,25,1,0,0,0,133,134,7,3,0,0,134,27,1,0,0,0,135,141,
        5,27,0,0,136,141,5,24,0,0,137,141,3,32,16,0,138,141,5,6,0,0,139,
        141,5,7,0,0,140,135,1,0,0,0,140,136,1,0,0,0,140,137,1,0,0,0,140,
        138,1,0,0,0,140,139,1,0,0,0,141,29,1,0,0,0,142,144,7,0,0,0,143,142,
        1,0,0,0,143,144,1,0,0,0,144,145,1,0,0,0,145,146,5,25,0,0,146,31,
        1,0,0,0,147,149,7,0,0,0,148,147,1,0,0,0,148,149,1,0,0,0,149,150,
        1,0,0,0,150,151,5,25,0,0,151,33,1,0,0,0,152,153,7,4,0,0,153,35,1,
        0,0,0,14,45,52,60,68,80,87,95,105,110,119,129,140,143,148
    ]

class OfficialSlotParser ( Parser ):

    grammarFileName = "OfficialSlot.g4"

    atn = ATNDeserializer().deserialize(serializedATN())

    decisionsToDFA = [ DFA(ds, i) for i, ds in enumerate(atn.decisionToState) ]

    sharedContextCache = PredictionContextCache()

    literalNames = [ "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "<INVALID>", "<INVALID>", "<INVALID>", "<INVALID>", 
                     "'>='", "'<='", "'!='", "'~='", "'='", "'>'", "'<'", 
                     "'+'", "'-'", "'*'", "'/'", "'('", "')'", "'['", "']'", 
                     "','" ]

    symbolicNames = [ "<INVALID>", "AND", "OR", "THEN", "BETWEEN", "LIMIT", 
                      "TRUE", "FALSE", "GTE", "LTE", "NEQ", "APPROX", "EQ", 
                      "GT", "LT", "PLUS", "MINUS", "STAR", "SLASH", "LPAREN", 
                      "RPAREN", "LBRACK", "RBRACK", "COMMA", "PERCENT", 
                      "NUMBER", "IDENT", "STRING", "WS" ]

    RULE_program = 0
    RULE_limitExpression = 1
    RULE_thenExpression = 2
    RULE_orExpression = 3
    RULE_andExpression = 4
    RULE_comparisonExpression = 5
    RULE_additiveExpression = 6
    RULE_multiplicativeExpression = 7
    RULE_primaryExpression = 8
    RULE_functionCall = 9
    RULE_argumentList = 10
    RULE_rangeLiteral = 11
    RULE_rangeBracketOpen = 12
    RULE_rangeBracketClose = 13
    RULE_literal = 14
    RULE_signedInteger = 15
    RULE_signedNumber = 16
    RULE_comparisonOperator = 17

    ruleNames =  [ "program", "limitExpression", "thenExpression", "orExpression", 
                   "andExpression", "comparisonExpression", "additiveExpression", 
                   "multiplicativeExpression", "primaryExpression", "functionCall", 
                   "argumentList", "rangeLiteral", "rangeBracketOpen", "rangeBracketClose", 
                   "literal", "signedInteger", "signedNumber", "comparisonOperator" ]

    EOF = Token.EOF
    AND=1
    OR=2
    THEN=3
    BETWEEN=4
    LIMIT=5
    TRUE=6
    FALSE=7
    GTE=8
    LTE=9
    NEQ=10
    APPROX=11
    EQ=12
    GT=13
    LT=14
    PLUS=15
    MINUS=16
    STAR=17
    SLASH=18
    LPAREN=19
    RPAREN=20
    LBRACK=21
    RBRACK=22
    COMMA=23
    PERCENT=24
    NUMBER=25
    IDENT=26
    STRING=27
    WS=28

    def __init__(self, input:TokenStream, output:TextIO = sys.stdout):
        super().__init__(input, output)
        self.checkVersion("4.13.2")
        self._interp = ParserATNSimulator(self, self.atn, self.decisionsToDFA, self.sharedContextCache)
        self._predicates = None




    class ProgramContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def limitExpression(self):
            return self.getTypedRuleContext(OfficialSlotParser.LimitExpressionContext,0)


        def EOF(self):
            return self.getToken(OfficialSlotParser.EOF, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_program

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitProgram" ):
                return visitor.visitProgram(self)
            else:
                return visitor.visitChildren(self)




    def program(self):

        localctx = OfficialSlotParser.ProgramContext(self, self._ctx, self.state)
        self.enterRule(localctx, 0, self.RULE_program)
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 36
            self.limitExpression()
            self.state = 37
            self.match(OfficialSlotParser.EOF)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LimitExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def thenExpression(self):
            return self.getTypedRuleContext(OfficialSlotParser.ThenExpressionContext,0)


        def LIMIT(self):
            return self.getToken(OfficialSlotParser.LIMIT, 0)

        def signedInteger(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(OfficialSlotParser.SignedIntegerContext)
            else:
                return self.getTypedRuleContext(OfficialSlotParser.SignedIntegerContext,i)


        def COMMA(self):
            return self.getToken(OfficialSlotParser.COMMA, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_limitExpression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLimitExpression" ):
                return visitor.visitLimitExpression(self)
            else:
                return visitor.visitChildren(self)




    def limitExpression(self):

        localctx = OfficialSlotParser.LimitExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 2, self.RULE_limitExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 39
            self.thenExpression()
            self.state = 45
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==5:
                self.state = 40
                self.match(OfficialSlotParser.LIMIT)
                self.state = 41
                self.signedInteger()
                self.state = 42
                self.match(OfficialSlotParser.COMMA)
                self.state = 43
                self.signedInteger()


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ThenExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def orExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(OfficialSlotParser.OrExpressionContext)
            else:
                return self.getTypedRuleContext(OfficialSlotParser.OrExpressionContext,i)


        def THEN(self, i:int=None):
            if i is None:
                return self.getTokens(OfficialSlotParser.THEN)
            else:
                return self.getToken(OfficialSlotParser.THEN, i)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_thenExpression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitThenExpression" ):
                return visitor.visitThenExpression(self)
            else:
                return visitor.visitChildren(self)




    def thenExpression(self):

        localctx = OfficialSlotParser.ThenExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 4, self.RULE_thenExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 47
            self.orExpression()
            self.state = 52
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==3:
                self.state = 48
                self.match(OfficialSlotParser.THEN)
                self.state = 49
                self.orExpression()
                self.state = 54
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class OrExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def andExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(OfficialSlotParser.AndExpressionContext)
            else:
                return self.getTypedRuleContext(OfficialSlotParser.AndExpressionContext,i)


        def OR(self, i:int=None):
            if i is None:
                return self.getTokens(OfficialSlotParser.OR)
            else:
                return self.getToken(OfficialSlotParser.OR, i)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_orExpression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitOrExpression" ):
                return visitor.visitOrExpression(self)
            else:
                return visitor.visitChildren(self)




    def orExpression(self):

        localctx = OfficialSlotParser.OrExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 6, self.RULE_orExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 55
            self.andExpression()
            self.state = 60
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==2:
                self.state = 56
                self.match(OfficialSlotParser.OR)
                self.state = 57
                self.andExpression()
                self.state = 62
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AndExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def comparisonExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(OfficialSlotParser.ComparisonExpressionContext)
            else:
                return self.getTypedRuleContext(OfficialSlotParser.ComparisonExpressionContext,i)


        def AND(self, i:int=None):
            if i is None:
                return self.getTokens(OfficialSlotParser.AND)
            else:
                return self.getToken(OfficialSlotParser.AND, i)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_andExpression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAndExpression" ):
                return visitor.visitAndExpression(self)
            else:
                return visitor.visitChildren(self)




    def andExpression(self):

        localctx = OfficialSlotParser.AndExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 8, self.RULE_andExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 63
            self.comparisonExpression()
            self.state = 68
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==1:
                self.state = 64
                self.match(OfficialSlotParser.AND)
                self.state = 65
                self.comparisonExpression()
                self.state = 70
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ComparisonExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def additiveExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(OfficialSlotParser.AdditiveExpressionContext)
            else:
                return self.getTypedRuleContext(OfficialSlotParser.AdditiveExpressionContext,i)


        def BETWEEN(self):
            return self.getToken(OfficialSlotParser.BETWEEN, 0)

        def rangeLiteral(self):
            return self.getTypedRuleContext(OfficialSlotParser.RangeLiteralContext,0)


        def comparisonOperator(self):
            return self.getTypedRuleContext(OfficialSlotParser.ComparisonOperatorContext,0)


        def getRuleIndex(self):
            return OfficialSlotParser.RULE_comparisonExpression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitComparisonExpression" ):
                return visitor.visitComparisonExpression(self)
            else:
                return visitor.visitChildren(self)




    def comparisonExpression(self):

        localctx = OfficialSlotParser.ComparisonExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 10, self.RULE_comparisonExpression)
        try:
            self.state = 80
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,4,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 71
                self.additiveExpression()
                self.state = 72
                self.match(OfficialSlotParser.BETWEEN)
                self.state = 73
                self.rangeLiteral()
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 75
                self.additiveExpression()
                self.state = 76
                self.comparisonOperator()
                self.state = 77
                self.additiveExpression()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 79
                self.additiveExpression()
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class AdditiveExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def multiplicativeExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(OfficialSlotParser.MultiplicativeExpressionContext)
            else:
                return self.getTypedRuleContext(OfficialSlotParser.MultiplicativeExpressionContext,i)


        def PLUS(self, i:int=None):
            if i is None:
                return self.getTokens(OfficialSlotParser.PLUS)
            else:
                return self.getToken(OfficialSlotParser.PLUS, i)

        def MINUS(self, i:int=None):
            if i is None:
                return self.getTokens(OfficialSlotParser.MINUS)
            else:
                return self.getToken(OfficialSlotParser.MINUS, i)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_additiveExpression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitAdditiveExpression" ):
                return visitor.visitAdditiveExpression(self)
            else:
                return visitor.visitChildren(self)




    def additiveExpression(self):

        localctx = OfficialSlotParser.AdditiveExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 12, self.RULE_additiveExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 82
            self.multiplicativeExpression()
            self.state = 87
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==15 or _la==16:
                self.state = 83
                _la = self._input.LA(1)
                if not(_la==15 or _la==16):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 84
                self.multiplicativeExpression()
                self.state = 89
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class MultiplicativeExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def primaryExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(OfficialSlotParser.PrimaryExpressionContext)
            else:
                return self.getTypedRuleContext(OfficialSlotParser.PrimaryExpressionContext,i)


        def STAR(self, i:int=None):
            if i is None:
                return self.getTokens(OfficialSlotParser.STAR)
            else:
                return self.getToken(OfficialSlotParser.STAR, i)

        def SLASH(self, i:int=None):
            if i is None:
                return self.getTokens(OfficialSlotParser.SLASH)
            else:
                return self.getToken(OfficialSlotParser.SLASH, i)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_multiplicativeExpression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitMultiplicativeExpression" ):
                return visitor.visitMultiplicativeExpression(self)
            else:
                return visitor.visitChildren(self)




    def multiplicativeExpression(self):

        localctx = OfficialSlotParser.MultiplicativeExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 14, self.RULE_multiplicativeExpression)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 90
            self.primaryExpression()
            self.state = 95
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==17 or _la==18:
                self.state = 91
                _la = self._input.LA(1)
                if not(_la==17 or _la==18):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()
                self.state = 92
                self.primaryExpression()
                self.state = 97
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class PrimaryExpressionContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LPAREN(self):
            return self.getToken(OfficialSlotParser.LPAREN, 0)

        def thenExpression(self):
            return self.getTypedRuleContext(OfficialSlotParser.ThenExpressionContext,0)


        def RPAREN(self):
            return self.getToken(OfficialSlotParser.RPAREN, 0)

        def functionCall(self):
            return self.getTypedRuleContext(OfficialSlotParser.FunctionCallContext,0)


        def literal(self):
            return self.getTypedRuleContext(OfficialSlotParser.LiteralContext,0)


        def IDENT(self):
            return self.getToken(OfficialSlotParser.IDENT, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_primaryExpression

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitPrimaryExpression" ):
                return visitor.visitPrimaryExpression(self)
            else:
                return visitor.visitChildren(self)




    def primaryExpression(self):

        localctx = OfficialSlotParser.PrimaryExpressionContext(self, self._ctx, self.state)
        self.enterRule(localctx, 16, self.RULE_primaryExpression)
        try:
            self.state = 105
            self._errHandler.sync(self)
            la_ = self._interp.adaptivePredict(self._input,7,self._ctx)
            if la_ == 1:
                self.enterOuterAlt(localctx, 1)
                self.state = 98
                self.match(OfficialSlotParser.LPAREN)
                self.state = 99
                self.thenExpression()
                self.state = 100
                self.match(OfficialSlotParser.RPAREN)
                pass

            elif la_ == 2:
                self.enterOuterAlt(localctx, 2)
                self.state = 102
                self.functionCall()
                pass

            elif la_ == 3:
                self.enterOuterAlt(localctx, 3)
                self.state = 103
                self.literal()
                pass

            elif la_ == 4:
                self.enterOuterAlt(localctx, 4)
                self.state = 104
                self.match(OfficialSlotParser.IDENT)
                pass


        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class FunctionCallContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def IDENT(self):
            return self.getToken(OfficialSlotParser.IDENT, 0)

        def LPAREN(self):
            return self.getToken(OfficialSlotParser.LPAREN, 0)

        def RPAREN(self):
            return self.getToken(OfficialSlotParser.RPAREN, 0)

        def argumentList(self):
            return self.getTypedRuleContext(OfficialSlotParser.ArgumentListContext,0)


        def getRuleIndex(self):
            return OfficialSlotParser.RULE_functionCall

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitFunctionCall" ):
                return visitor.visitFunctionCall(self)
            else:
                return visitor.visitChildren(self)




    def functionCall(self):

        localctx = OfficialSlotParser.FunctionCallContext(self, self._ctx, self.state)
        self.enterRule(localctx, 18, self.RULE_functionCall)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 107
            self.match(OfficialSlotParser.IDENT)
            self.state = 108
            self.match(OfficialSlotParser.LPAREN)
            self.state = 110
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if (((_la) & ~0x3f) == 0 and ((1 << _la) & 252281024) != 0):
                self.state = 109
                self.argumentList()


            self.state = 112
            self.match(OfficialSlotParser.RPAREN)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ArgumentListContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def thenExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(OfficialSlotParser.ThenExpressionContext)
            else:
                return self.getTypedRuleContext(OfficialSlotParser.ThenExpressionContext,i)


        def COMMA(self, i:int=None):
            if i is None:
                return self.getTokens(OfficialSlotParser.COMMA)
            else:
                return self.getToken(OfficialSlotParser.COMMA, i)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_argumentList

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitArgumentList" ):
                return visitor.visitArgumentList(self)
            else:
                return visitor.visitChildren(self)




    def argumentList(self):

        localctx = OfficialSlotParser.ArgumentListContext(self, self._ctx, self.state)
        self.enterRule(localctx, 20, self.RULE_argumentList)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 114
            self.thenExpression()
            self.state = 119
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            while _la==23:
                self.state = 115
                self.match(OfficialSlotParser.COMMA)
                self.state = 116
                self.thenExpression()
                self.state = 121
                self._errHandler.sync(self)
                _la = self._input.LA(1)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RangeLiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def rangeBracketOpen(self):
            return self.getTypedRuleContext(OfficialSlotParser.RangeBracketOpenContext,0)


        def additiveExpression(self, i:int=None):
            if i is None:
                return self.getTypedRuleContexts(OfficialSlotParser.AdditiveExpressionContext)
            else:
                return self.getTypedRuleContext(OfficialSlotParser.AdditiveExpressionContext,i)


        def COMMA(self):
            return self.getToken(OfficialSlotParser.COMMA, 0)

        def rangeBracketClose(self):
            return self.getTypedRuleContext(OfficialSlotParser.RangeBracketCloseContext,0)


        def STRING(self):
            return self.getToken(OfficialSlotParser.STRING, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_rangeLiteral

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitRangeLiteral" ):
                return visitor.visitRangeLiteral(self)
            else:
                return visitor.visitChildren(self)




    def rangeLiteral(self):

        localctx = OfficialSlotParser.RangeLiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 22, self.RULE_rangeLiteral)
        try:
            self.state = 129
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [19, 21]:
                self.enterOuterAlt(localctx, 1)
                self.state = 122
                self.rangeBracketOpen()
                self.state = 123
                self.additiveExpression()
                self.state = 124
                self.match(OfficialSlotParser.COMMA)
                self.state = 125
                self.additiveExpression()
                self.state = 126
                self.rangeBracketClose()
                pass
            elif token in [27]:
                self.enterOuterAlt(localctx, 2)
                self.state = 128
                self.match(OfficialSlotParser.STRING)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RangeBracketOpenContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def LBRACK(self):
            return self.getToken(OfficialSlotParser.LBRACK, 0)

        def LPAREN(self):
            return self.getToken(OfficialSlotParser.LPAREN, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_rangeBracketOpen

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitRangeBracketOpen" ):
                return visitor.visitRangeBracketOpen(self)
            else:
                return visitor.visitChildren(self)




    def rangeBracketOpen(self):

        localctx = OfficialSlotParser.RangeBracketOpenContext(self, self._ctx, self.state)
        self.enterRule(localctx, 24, self.RULE_rangeBracketOpen)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 131
            _la = self._input.LA(1)
            if not(_la==19 or _la==21):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class RangeBracketCloseContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def RBRACK(self):
            return self.getToken(OfficialSlotParser.RBRACK, 0)

        def RPAREN(self):
            return self.getToken(OfficialSlotParser.RPAREN, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_rangeBracketClose

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitRangeBracketClose" ):
                return visitor.visitRangeBracketClose(self)
            else:
                return visitor.visitChildren(self)




    def rangeBracketClose(self):

        localctx = OfficialSlotParser.RangeBracketCloseContext(self, self._ctx, self.state)
        self.enterRule(localctx, 26, self.RULE_rangeBracketClose)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 133
            _la = self._input.LA(1)
            if not(_la==20 or _la==22):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class LiteralContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def STRING(self):
            return self.getToken(OfficialSlotParser.STRING, 0)

        def PERCENT(self):
            return self.getToken(OfficialSlotParser.PERCENT, 0)

        def signedNumber(self):
            return self.getTypedRuleContext(OfficialSlotParser.SignedNumberContext,0)


        def TRUE(self):
            return self.getToken(OfficialSlotParser.TRUE, 0)

        def FALSE(self):
            return self.getToken(OfficialSlotParser.FALSE, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_literal

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitLiteral" ):
                return visitor.visitLiteral(self)
            else:
                return visitor.visitChildren(self)




    def literal(self):

        localctx = OfficialSlotParser.LiteralContext(self, self._ctx, self.state)
        self.enterRule(localctx, 28, self.RULE_literal)
        try:
            self.state = 140
            self._errHandler.sync(self)
            token = self._input.LA(1)
            if token in [27]:
                self.enterOuterAlt(localctx, 1)
                self.state = 135
                self.match(OfficialSlotParser.STRING)
                pass
            elif token in [24]:
                self.enterOuterAlt(localctx, 2)
                self.state = 136
                self.match(OfficialSlotParser.PERCENT)
                pass
            elif token in [15, 16, 25]:
                self.enterOuterAlt(localctx, 3)
                self.state = 137
                self.signedNumber()
                pass
            elif token in [6]:
                self.enterOuterAlt(localctx, 4)
                self.state = 138
                self.match(OfficialSlotParser.TRUE)
                pass
            elif token in [7]:
                self.enterOuterAlt(localctx, 5)
                self.state = 139
                self.match(OfficialSlotParser.FALSE)
                pass
            else:
                raise NoViableAltException(self)

        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class SignedIntegerContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NUMBER(self):
            return self.getToken(OfficialSlotParser.NUMBER, 0)

        def PLUS(self):
            return self.getToken(OfficialSlotParser.PLUS, 0)

        def MINUS(self):
            return self.getToken(OfficialSlotParser.MINUS, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_signedInteger

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSignedInteger" ):
                return visitor.visitSignedInteger(self)
            else:
                return visitor.visitChildren(self)




    def signedInteger(self):

        localctx = OfficialSlotParser.SignedIntegerContext(self, self._ctx, self.state)
        self.enterRule(localctx, 30, self.RULE_signedInteger)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 143
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==15 or _la==16:
                self.state = 142
                _la = self._input.LA(1)
                if not(_la==15 or _la==16):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()


            self.state = 145
            self.match(OfficialSlotParser.NUMBER)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class SignedNumberContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def NUMBER(self):
            return self.getToken(OfficialSlotParser.NUMBER, 0)

        def PLUS(self):
            return self.getToken(OfficialSlotParser.PLUS, 0)

        def MINUS(self):
            return self.getToken(OfficialSlotParser.MINUS, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_signedNumber

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitSignedNumber" ):
                return visitor.visitSignedNumber(self)
            else:
                return visitor.visitChildren(self)




    def signedNumber(self):

        localctx = OfficialSlotParser.SignedNumberContext(self, self._ctx, self.state)
        self.enterRule(localctx, 32, self.RULE_signedNumber)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 148
            self._errHandler.sync(self)
            _la = self._input.LA(1)
            if _la==15 or _la==16:
                self.state = 147
                _la = self._input.LA(1)
                if not(_la==15 or _la==16):
                    self._errHandler.recoverInline(self)
                else:
                    self._errHandler.reportMatch(self)
                    self.consume()


            self.state = 150
            self.match(OfficialSlotParser.NUMBER)
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx


    class ComparisonOperatorContext(ParserRuleContext):
        __slots__ = 'parser'

        def __init__(self, parser, parent:ParserRuleContext=None, invokingState:int=-1):
            super().__init__(parent, invokingState)
            self.parser = parser

        def GTE(self):
            return self.getToken(OfficialSlotParser.GTE, 0)

        def LTE(self):
            return self.getToken(OfficialSlotParser.LTE, 0)

        def NEQ(self):
            return self.getToken(OfficialSlotParser.NEQ, 0)

        def APPROX(self):
            return self.getToken(OfficialSlotParser.APPROX, 0)

        def EQ(self):
            return self.getToken(OfficialSlotParser.EQ, 0)

        def GT(self):
            return self.getToken(OfficialSlotParser.GT, 0)

        def LT(self):
            return self.getToken(OfficialSlotParser.LT, 0)

        def getRuleIndex(self):
            return OfficialSlotParser.RULE_comparisonOperator

        def accept(self, visitor:ParseTreeVisitor):
            if hasattr( visitor, "visitComparisonOperator" ):
                return visitor.visitComparisonOperator(self)
            else:
                return visitor.visitChildren(self)




    def comparisonOperator(self):

        localctx = OfficialSlotParser.ComparisonOperatorContext(self, self._ctx, self.state)
        self.enterRule(localctx, 34, self.RULE_comparisonOperator)
        self._la = 0 # Token type
        try:
            self.enterOuterAlt(localctx, 1)
            self.state = 152
            _la = self._input.LA(1)
            if not((((_la) & ~0x3f) == 0 and ((1 << _la) & 32512) != 0)):
                self._errHandler.recoverInline(self)
            else:
                self._errHandler.reportMatch(self)
                self.consume()
        except RecognitionException as re:
            localctx.exception = re
            self._errHandler.reportError(self, re)
            self._errHandler.recover(self, re)
        finally:
            self.exitRule()
        return localctx





