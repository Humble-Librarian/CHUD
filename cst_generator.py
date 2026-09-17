# ─────────────────────────────────────────────
#  CHUD — cst_generator.py
#  Concrete Syntax Tree (Parse Tree) Generator.
#  Reuses Parser grammar rules without duplication
#  by wrapping rule dispatches and capturing tokens.
# ─────────────────────────────────────────────

from parser import Parser
from lexer import Lexer


class CSTParser(Parser):
    """Subclasses Parser to generate a Concrete Syntax Tree (Parse Tree)
    showing grammar derivations and all concrete tokens (braces, keywords, etc.)
    without rewriting the grammar logic.
    """
    def __init__(self, tokens):
        super().__init__(tokens)
        self.root = {"name": "<program>", "type": "rule", "children": []}
        self.stack = [self.root]

    def _enter(self, name):
        node = {"name": f"<{name}>", "type": "rule", "children": []}
        self.stack[-1]["children"].append(node)
        self.stack.append(node)

    def _exit(self):
        return self.stack.pop()

    def advance(self):
        tok = self.peek()
        result = super().advance()
        if tok.type != 'EOF':
            val_display = repr(tok.value) if isinstance(tok.value, str) else tok.value
            self.stack[-1]["children"].append({
                "name": f"{tok.type} ({val_display})",
                "type": "terminal",
                "token": tok.type,
                "value": tok.value,
                "line": tok.line
            })
        return result


RULE_MAPPING = {
    'parse_statement': 'statement',
    'parse_let': 'let_stmt',
    'parse_assign': 'assign_stmt',
    'parse_yap': 'yap_stmt',
    'parse_check': 'check_stmt',
    'parse_keep': 'keep_stmt',
    'parse_loop': 'loop_stmt',
    'parse_function': 'make_stmt',
    'parse_return': 'return_stmt',
    'parse_block': 'block',
    'parse_expression': 'expression',
    'parse_comparison': 'comparison',
    'parse_term': 'term',
    'parse_factor': 'factor',
    'parse_unary': 'unary',
    'parse_primary': 'primary',
}

def _add_rule_trackers(cls):
    for method_name, rule_name in RULE_MAPPING.items():
        orig = getattr(Parser, method_name)
        def make_wrapper(orig_fn, r_name):
            def wrapped(self, *args, **kwargs):
                self._enter(r_name)
                try:
                    return orig_fn(self, *args, **kwargs)
                finally:
                    self._exit()
            return wrapped
        setattr(cls, method_name, make_wrapper(orig, rule_name))
    return cls

_add_rule_trackers(CSTParser)


def generate_cst(source_or_tokens):
    """Generates CST (Parse Tree) dict from source code or tokens."""
    if isinstance(source_or_tokens, str):
        tokens = Lexer(source_or_tokens).tokenize()
    else:
        tokens = source_or_tokens

    cst_parser = CSTParser(tokens)
    cst_parser.parse()
    return cst_parser.root


if __name__ == '__main__':
    import json
    src = 'let x = 5 + 2'
    cst = generate_cst(src)
    print(json.dumps(cst, indent=2))
