# ─────────────────────────────────────────────
#  CHUD — lexer.py
#  Reads raw source text → list of Token objects
#  Principle: maximal munch — always match the
#  longest possible token at each position.
# ─────────────────────────────────────────────

import re
import random

# ── Token definition ──────────────────────────

class Token:
    def __init__(self, type_, value, line):
        self.type  = type_   # str  e.g. 'NUMBER', 'CHECK', 'PLUS'
        self.value = value   # str  the actual text e.g. '42', 'check', '+'
        self.line  = line    # int  line number (1-indexed, for error messages)

    def __repr__(self):
        return f"Token({self.type}, {repr(self.value)}, line={self.line})"


# ── Keyword table ─────────────────────────────
#  Any word in this table is a keyword token,
#  NOT a plain identifier. Order doesn't matter
#  here — the lexer checks this dict after
#  matching a word with the identifier regex.

KEYWORDS = {
    'check'    : 'CHECK',       # if
    'otherwise': 'OTHERWISE',   # else
    'keep'     : 'KEEP',        # while
    'yap'      : 'YAP',         # print
    'let'      : 'LET',         # variable declaration
    'stop'     : 'STOP',        # break
    'W'        : 'W',           # true
    'L'        : 'L',           # false
    'hear'     : 'HEAR',        # input
}


# ── Token patterns ────────────────────────────
#  Listed in priority order — checked top to
#  bottom. First match wins (maximal munch for
#  multi-char operators handled explicitly).
#
#  Format: (token_type, compiled_regex)

TOKEN_PATTERNS = [
    ('FLOAT',   re.compile(r'\d+\.\d+')),        # 3.14  before INT so 3.14 isn't two tokens
    ('NUMBER',  re.compile(r'\d+')),              # 42
    ('STRING',  re.compile(r'"[^"]*"')),          # "hello bro"
    ('EQEQ',    re.compile(r'==')),               # ==   before EQ so == isn't = then =
    ('NEQ',     re.compile(r'!=')),               # !=
    ('LE',      re.compile(r'<=')),               # <=   before LT
    ('GE',      re.compile(r'>=')),               # >=   before GT
    ('EQ',      re.compile(r'=')),                # =
    ('LT',      re.compile(r'<')),                # <
    ('GT',      re.compile(r'>')),                # >
    ('PLUS',    re.compile(r'\+')),               # +
    ('MINUS',   re.compile(r'-')),                # -
    ('STAR',    re.compile(r'\*')),               # *
    ('SLASH',   re.compile(r'/')),                # /
    ('LPAREN',  re.compile(r'\(')),               # (
    ('RPAREN',  re.compile(r'\)')),               # )
    ('LBRACE',  re.compile(r'\{')),               # {
    ('RBRACE',  re.compile(r'\}')),               # }
    ('ID',      re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*')),  # variable names & keywords
]


# ── Roast error system ────────────────────────
#  Three flavours — randomly picked on error.

ROASTS = [
    # personal roast
    "bro really thought that was valid syntax 💀 absolutely not.",
    "whoever wrote this line needs to sit down and think about their life choices.",
    "this ain't it chief. this is so far from it.",
    "i have seen things. this is the worst of them.",
    "unironically cooked. not in a good way.",

    # sigma quotes
    '"the true sigma always closes his braces." — Sun Tzu, probably.',
    '"a man who cannot tokenize, cannot lead." — Confucius (trust me bro).',
    '"only the weak leave syntax errors." — Abraham Lincoln, 1863.',
    '"the sigma does not use undeclared variables." — W. Rizzerfield, 1987.',

    # wholesome gen z
    "bestie this line is giving chaos. not the fun kind. fix it pls.",
    "no cap this error is sending me. please recheck this.",
    "it's giving confusion. it's giving wrong. it's not giving correct.",
    "we do not do that here. kindly reconsider.",
]

def roast():
    return random.choice(ROASTS)


# ── CHUD Lexer ────────────────────────────────

class LexerError(Exception):
    pass

class Lexer:
    def __init__(self, source):
        self.source = source
        self.pos    = 0           # current character index
        self.line   = 1           # current line number

    # ── public entry point ──
    def tokenize(self):
        tokens = []

        while self.pos < len(self.source):
            # skip whitespace (but track newlines for line numbers)
            if self.source[self.pos] == '\n':
                self.line += 1
                self.pos  += 1
                continue

            if self.source[self.pos] in ' \t\r':
                self.pos += 1
                continue

            # skip single-line comments: // …
            if self.source[self.pos:self.pos+2] == '//':
                while self.pos < len(self.source) and self.source[self.pos] != '\n':
                    self.pos += 1
                continue

            # try every token pattern in priority order
            matched = False
            for token_type, pattern in TOKEN_PATTERNS:
                m = pattern.match(self.source, self.pos)
                if m:
                    value = m.group(0)

                    # if it matched as ID, check keyword table
                    if token_type == 'ID' and value in KEYWORDS:
                        token_type = KEYWORDS[value]

                    # strip quotes from strings
                    if token_type == 'STRING':
                        value = value[1:-1]

                    # convert number strings to actual numbers
                    if token_type == 'NUMBER':
                        value = int(value)
                    if token_type == 'FLOAT':
                        value = float(value)

                    tokens.append(Token(token_type, value, self.line))
                    self.pos += len(m.group(0))
                    matched = True
                    break

            if not matched:
                bad_char = self.source[self.pos]
                raise LexerError(
                    f"\n[CHUD LexerError] line {self.line} — "
                    f"unexpected character '{bad_char}'\n"
                    f"→ {roast()}"
                )

        tokens.append(Token('EOF', None, self.line))
        return tokens


# ── Quick test ────────────────────────────────
if __name__ == '__main__':
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
    lexer  = Lexer(src)
    tokens = lexer.tokenize()
    for tok in tokens:
        print(tok)
