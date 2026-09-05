# ─────────────────────────────────────────────
#  CHUD — ast_serializer.py
#  Converts CHUD AST into a hierarchical dict
#  structure ready for D3.js visualization.
# ─────────────────────────────────────────────

from ast_nodes import (
    ProgramNode, AssignNode, YapNode, CheckNode,
    KeepNode, StopNode, BinOpNode, UnaryOpNode,
    NumberNode, StringNode, BoolNode, IdentifierNode, HearNode
)


def ast_to_d3(node):
    """Recursively converts an AST node to D3-compatible tree JSON."""
    if node is None:
        return None

    if isinstance(node, ProgramNode):
        return {
            "name": f"Program ({len(node.statements)} stmts)",
            "type": "Program",
            "children": [ast_to_d3(stmt) for stmt in node.statements]
        }

    if isinstance(node, AssignNode):
        action = "let " if node.is_declaration else "reassign "
        return {
            "name": f"{action}{node.name}",
            "type": "Assign",
            "line": node.line,
            "children": [
                {"name": f"target: {node.name}", "type": "Identifier"},
                ast_to_d3(node.value)
            ]
        }

    if isinstance(node, YapNode):
        return {
            "name": "yap",
            "type": "Yap",
            "line": node.line,
            "children": [ast_to_d3(node.value)]
        }

    if isinstance(node, CheckNode):
        children = [
            {"name": "condition", "type": "Label", "children": [ast_to_d3(node.condition)]},
            {"name": f"then ({len(node.body)} stmts)", "type": "Block", "children": [ast_to_d3(s) for s in node.body]}
        ]
        if node.else_body is not None:
            children.append({
                "name": f"otherwise ({len(node.else_body)} stmts)",
                "type": "Block",
                "children": [ast_to_d3(s) for s in node.else_body]
            })
        return {
            "name": "check",
            "type": "Check",
            "line": node.line,
            "children": children
        }

    if isinstance(node, KeepNode):
        return {
            "name": "keep",
            "type": "Keep",
            "line": node.line,
            "children": [
                {"name": "condition", "type": "Label", "children": [ast_to_d3(node.condition)]},
                {"name": f"loop_body ({len(node.body)} stmts)", "type": "Block", "children": [ast_to_d3(s) for s in node.body]}
            ]
        }

    if isinstance(node, StopNode):
        return {
            "name": "stop",
            "type": "Stop",
            "line": node.line
        }

    if isinstance(node, BinOpNode):
        return {
            "name": f"op ({node.op})",
            "type": "BinOp",
            "line": node.line,
            "children": [
                ast_to_d3(node.left),
                ast_to_d3(node.right)
            ]
        }

    if isinstance(node, UnaryOpNode):
        return {
            "name": f"unary ({node.op})",
            "type": "UnaryOp",
            "line": node.line,
            "children": [ast_to_d3(node.operand)]
        }

    if isinstance(node, NumberNode):
        return {
            "name": f"num: {node.value}",
            "type": "Number",
            "value": node.value,
            "line": node.line
        }

    if isinstance(node, StringNode):
        return {
            "name": f'str: "{node.value}"',
            "type": "String",
            "value": node.value,
            "line": node.line
        }

    if isinstance(node, BoolNode):
        val_str = "W" if node.value else "L"
        return {
            "name": f"bool: {val_str}",
            "type": "Bool",
            "value": val_str,
            "line": node.line
        }

    if isinstance(node, IdentifierNode):
        return {
            "name": f"id: {node.name}",
            "type": "Identifier",
            "line": node.line
        }

    if isinstance(node, HearNode):
        label = f'hear ("{node.prompt}")' if node.prompt else "hear"
        return {
            "name": label,
            "type": "Hear",
            "line": node.line
        }

    return {"name": str(node), "type": "Unknown"}
