grammar OfficialSlot;

// Formal mirror of src/findsl/official_slot.py.
// The production parser is still the tested recursive-descent parser.
// This file is provided for audit, documentation, and future ANTLR migration.

program
    : limitExpression EOF
    ;

limitExpression
    : thenExpression (LIMIT signedInteger COMMA signedInteger)?
    ;

thenExpression
    : orExpression (THEN orExpression)*
    ;

orExpression
    : andExpression (OR andExpression)*
    ;

andExpression
    : comparisonExpression (AND comparisonExpression)*
    ;

comparisonExpression
    : additiveExpression (BETWEEN rangeLiteral)?
    | additiveExpression comparisonOperator additiveExpression
    ;

additiveExpression
    : multiplicativeExpression ((PLUS | MINUS) multiplicativeExpression)*
    ;

multiplicativeExpression
    : primaryExpression ((STAR | SLASH) primaryExpression)*
    ;

primaryExpression
    : LPAREN thenExpression RPAREN
    | functionCall
    | literal
    | IDENT
    ;

functionCall
    : IDENT LPAREN argumentList? RPAREN
    ;

argumentList
    : thenExpression (COMMA thenExpression)*
    ;

rangeLiteral
    : rangeBracketOpen additiveExpression COMMA additiveExpression rangeBracketClose
    | STRING
    ;

rangeBracketOpen
    : LBRACK
    | LPAREN
    ;

rangeBracketClose
    : RBRACK
    | RPAREN
    ;

literal
    : STRING
    | PERCENT
    | signedNumber
    | TRUE
    | FALSE
    ;

signedInteger
    : (PLUS | MINUS)? NUMBER
    ;

signedNumber
    : (PLUS | MINUS)? NUMBER
    ;

comparisonOperator
    : GTE
    | LTE
    | NEQ
    | APPROX
    | EQ
    | GT
    | LT
    ;

AND: [aA][nN][dD];
OR: [oO][rR];
THEN: [tT][hH][eE][nN];
BETWEEN: [bB][eE][tT][wW][eE][eE][nN];
LIMIT: [lL][iI][mM][iI][tT];
TRUE: [tT][rR][uU][eE];
FALSE: [fF][aA][lL][sS][eE];

GTE: '>=';
LTE: '<=';
NEQ: '!=';
APPROX: '~=';
EQ: '=';
GT: '>';
LT: '<';
PLUS: '+';
MINUS: '-';
STAR: '*';
SLASH: '/';
LPAREN: '(';
RPAREN: ')';
LBRACK: '[';
RBRACK: ']';
COMMA: ',';

PERCENT
    : NUMBER '%'
    ;

NUMBER
    : DIGIT+ ('.' DIGIT+)?
    ;

IDENT
    : [A-Za-z_] [A-Za-z0-9_]*
    ;

STRING
    : '\'' (ESC | ~['\\])* '\''
    | '"' (ESC | ~["\\])* '"'
    ;

fragment ESC
    : '\\' .
    ;

fragment DIGIT
    : [0-9]
    ;

WS
    : [ \t\r\n]+ -> skip
    ;
