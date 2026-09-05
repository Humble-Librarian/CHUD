# ─────────────────────────────────────────────
#  CHUD — parser.py
#  Tokens → AST using recursive descent.
#  One function per grammar rule.
#
#  Grammar (reference):
#  program     → statement*
#  statement   → let_stmt | assign_stmt | check_stmt | keep_stmt | yap_stmt | stop_stmt
#  let_stmt    → LET IDENTIFIER EQ expression
#  assign_stmt → IDENTIFIER EQ expression
#  check_stmt  → CHECK expression LBRACE statement* RBRACE (OTHERWISE LBRACE statement* RBRACE)?
#  keep_stmt   → KEEP expression LBRACE statement* RBRACE
#  yap_stmt    → YAP expression
#  stop_stmt   → STOP
#  expression  → comparison
#  comparison  → term (('==' | '!=' | '<' | '>' | '<=' | '>=') term)*
#  term        → factor (('+' | '-') factor)*
#  factor      → unary (('*' | '/') unary)*
#  unary       → ('-' | '+') unary | primary
#  primary     → NUMBER | FLOAT | STRING | W | L | IDENTIFIER | '(' expression ')'
# ─────────────────────────────────────────────

from ast_nodes import *
from lexer import roast
import random


class ParseError(Exception):
    pass


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos    = 0          # index into token list

    # ══════════════════════════════════════════
    #  UTILITY METHODS — the three tools every
    #  grammar rule function will use
    # ══════════════════════════════════════════

    def peek(self):
        """Look at the current token WITHOUT consuming it.
        Like reading the next card without picking it up.
        """
        return self.tokens[self.pos]

    def advance(self):
        """Consume and return the current token, move forward.
        Like picking up the next card from the deck.
        """
        tok = self.tokens[self.pos]
        if tok.type != 'EOF':
            self.pos += 1
        return tok

    def expect(self, token_type):
        """Consume the current token IF it matches token_type.
        If it doesn't match → raise a roast error.
        This is what enforces grammar rules.
        """
        tok = self.peek()
        if tok.type != token_type:
            raise ParseError(
                f"\n[CHUD ParseError] line {tok.line} — "
                f"expected {token_type} but got {tok.type} ({repr(tok.value)})\n"
                f"→ {roast()}"
            )
        return self.advance()

    def check(self, *types):
        """Returns True if current token type matches any of the given types.
        Used for lookahead — 'is the next token one of these?'
        Does NOT consume the token.
        """
        return self.peek().type in types


    # ══════════════════════════════════════════
    #  RULE 1 — program
    #  program → statement*
    #  The top-level entry point. Keeps parsing
    #  statements until it hits EOF.
    # ══════════════════════════════════════════

    def parse(self):
        statements = []
        while not self.check('EOF'):
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        return ProgramNode(statements)


    # ══════════════════════════════════════════
    #  RULE 2 — statement dispatcher
    #  Looks at the current token to decide
    #  which specific statement rule to call.
    # ══════════════════════════════════════════

    def parse_statement(self):
        tok = self.peek()

        if tok.type == 'LET':
            return self.parse_let()
        elif tok.type == 'CHECK':
            return self.parse_check()
        elif tok.type == 'KEEP':
            return self.parse_keep()
        elif tok.type == 'YAP':
            return self.parse_yap()
        elif tok.type == 'STOP':
            self.advance()
            return StopNode(line=tok.line)
        elif tok.type == 'ID':
            return self.parse_assign()
        else:
            raise ParseError(
                f"\n[CHUD ParseError] line {tok.line} — "
                f"unexpected token {tok.type} ({repr(tok.value)}) at start of statement\n"
                f"→ {roast()}"
            )


    # ══════════════════════════════════════════
    #  RULE 3 — let statement
    #  let_stmt → LET IDENTIFIER EQ expression
    #
    #  Example: let score = 0
    #  Grammar says: keyword LET, then a name,
    #  then =, then any expression.
    # ══════════════════════════════════════════

    def parse_let(self):
        let_tok = self.expect('LET')            # consume 'let'
        name_tok = self.expect('ID')            # consume the variable name
        self.expect('EQ')                       # consume '='
        value = self.parse_expression()         # parse the right-hand side
        return AssignNode(name_tok.value, value, is_declaration=True, line=let_tok.line)


    # ══════════════════════════════════════════
    #  RULE 4 — reassignment
    #  assign_stmt → IDENTIFIER EQ expression
    #
    #  Example: score = score + 1
    #  No 'let' keyword — just name = value.
    # ══════════════════════════════════════════

    def parse_assign(self):
        name_tok = self.expect('ID')            # consume the variable name
        self.expect('EQ')                       # consume '='
        value = self.parse_expression()         # parse the right-hand side
        return AssignNode(name_tok.value, value, is_declaration=False, line=name_tok.line)


    # ══════════════════════════════════════════
    #  RULE 5 — yap statement
    #  yap_stmt → YAP expression
    #
    #  Example: yap "hello"  or  yap score
    # ══════════════════════════════════════════

    def parse_yap(self):
        yap_tok = self.expect('YAP')            # consume 'yap'
        value = self.parse_expression()         # parse what to print
        return YapNode(value, line=yap_tok.line)


    # ══════════════════════════════════════════
    #  RULE 6 — check (if/otherwise)
    #  check_stmt → CHECK expr { stmts } (OTHERWISE { stmts })?
    #
    #  Example:
    #    check age >= 18 {
    #        yap "adult"
    #    } otherwise {
    #        yap "nope"
    #    }
    #
    #  The 'otherwise' block is optional — the ?
    #  in the grammar means zero or one time.
    # ══════════════════════════════════════════

    def parse_check(self):
        check_tok = self.expect('CHECK')        # consume 'check'
        condition = self.parse_expression()     # parse the condition

        self.expect('LBRACE')                   # consume '{'
        body = self.parse_block()               # parse statements inside
        self.expect('RBRACE')                   # consume '}'

        else_body = None
        if self.check('OTHERWISE'):             # optional otherwise
            self.advance()                      # consume 'otherwise'
            self.expect('LBRACE')
            else_body = self.parse_block()
            self.expect('RBRACE')

        return CheckNode(condition, body, else_body, line=check_tok.line)


    # ══════════════════════════════════════════
    #  RULE 7 — keep (while loop)
    #  keep_stmt → KEEP expr { stmts }
    #
    #  Example:
    #    keep i < 10 {
    #        yap i
    #        i = i + 1
    #    }
    # ══════════════════════════════════════════

    def parse_keep(self):
        keep_tok = self.expect('KEEP')          # consume 'keep'
        condition = self.parse_expression()     # parse the loop condition
        self.expect('LBRACE')
        body = self.parse_block()
        self.expect('RBRACE')
        return KeepNode(condition, body, line=keep_tok.line)


    # ══════════════════════════════════════════
    #  HELPER — parse_block
    #  Parses zero or more statements until }
    #  Used by both check and keep rules.
    # ══════════════════════════════════════════

    def parse_block(self):
        statements = []
        while not self.check('RBRACE', 'EOF'):
            statements.append(self.parse_statement())
        return statements


    # ══════════════════════════════════════════
    #  EXPRESSION RULES
    #  These handle operator precedence via
    #  grammar layering — each level calls the
    #  next deeper level.
    #
    #  Order (lowest → highest precedence):
    #  expression → comparison → term → factor → unary → primary
    # ══════════════════════════════════════════

    def parse_expression(self):
        # expression is just an alias for comparison (lowest precedence)
        return self.parse_comparison()

    def parse_comparison(self):
        """comparison → term (('==' | '!=' | '<' | '>' | '<=' | '>=') term)*
        Handles: x == 5, age >= 18, i < 10
        Lower precedence than + - so  x + 1 > 5  parses as  (x+1) > 5
        """
        left = self.parse_term()
        while self.check('EQEQ', 'NEQ', 'LT', 'GT', 'LE', 'GE'):
            tok   = self.advance()
            op    = tok.value
            right = self.parse_term()
            left  = BinOpNode(left, op, right, line=tok.line)
        return left

    def parse_term(self):
        """term → factor (('+' | '-') factor)*
        Handles: a + b, x - 1
        Each factor is multiplication — so * binds tighter than +
        """
        left = self.parse_factor()
        while self.check('PLUS', 'MINUS'):
            tok   = self.advance()
            op    = tok.value
            right = self.parse_factor()
            left  = BinOpNode(left, op, right, line=tok.line)
        return left

    def parse_factor(self):
        """factor → unary (('*' | '/') unary)*
        Handles: a * b, x / 2
        Tightest binding among binary ops.
        """
        left = self.parse_unary()
        while self.check('STAR', 'SLASH'):
            tok   = self.advance()
            op    = tok.value
            right = self.parse_unary()
            left  = BinOpNode(left, op, right, line=tok.line)
        return left

    def parse_unary(self):
        """unary → ('-' | '+') unary | primary
        Handles unary operators like -5 or -x.
        """
        if self.check('MINUS', 'PLUS'):
            tok = self.advance()
            operand = self.parse_unary()
            return UnaryOpNode(tok.value, operand, line=tok.line)
        return self.parse_primary()

    def parse_primary(self):
        """primary → NUMBER | FLOAT | STRING | W | L | IDENTIFIER | '(' expression ')'
        The leaf nodes — actual values, variables, or a parenthesised sub-expression.
        Parentheses here is what makes (2 + 3) * 4 work correctly.
        """
        tok = self.peek()

        if tok.type in ('NUMBER', 'FLOAT'):
            self.advance()
            return NumberNode(tok.value, line=tok.line)

        if tok.type == 'STRING':
            self.advance()
            return StringNode(tok.value, line=tok.line)

        if tok.type == 'W':
            self.advance()
            return BoolNode(True, line=tok.line)

        if tok.type == 'L':
            self.advance()
            return BoolNode(False, line=tok.line)

        if tok.type == 'ID':
            self.advance()
            return IdentifierNode(tok.value, line=tok.line)

        if tok.type == 'HEAR':
            self.advance()                      # consume 'hear'
            prompt = None
            if self.check('STRING'):
                prompt = self.advance().value
            return HearNode(prompt, line=tok.line)

        if tok.type == 'LPAREN':
            self.advance()                      # consume '('
            expr = self.parse_expression()      # parse inside
            self.expect('RPAREN')               # consume ')'
            return expr

        raise ParseError(
            f"\n[CHUD ParseError] line {tok.line} — "
            f"expected a value (number, string, variable) but got {tok.type}\n"
            f"→ {roast()}"
        )


# ── Quick test ────────────────────────────────
if __name__ == '__main__':
    from lexer import Lexer

    src = '''
let name = "bro"
let age  = 19

check age >= 18 {
    yap "you are a real one"
} otherwise {
    yap "L behavior"
}

let i = 0
keep i < 5 {
    yap i
    i = i + 1
}
'''
    tokens = Lexer(src).tokenize()
    ast    = Parser(tokens).parse()

    print(ast)
    print()
    for stmt in ast.statements:
        print(stmt)
