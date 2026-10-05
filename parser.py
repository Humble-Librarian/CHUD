# ─────────────────────────────────────────────
#  CHUD — parser.py (Compatibility Alias)
#  Re-exports Parser and ParseError from chud_parser.py
#  to avoid naming collisions with Python 3.9's built-in 'parser' module.
# ─────────────────────────────────────────────

from chud_parser import Parser, ParseError
