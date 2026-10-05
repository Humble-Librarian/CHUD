# ─────────────────────────────────────────────
#  CHUD — c_codegen.py
#  Ahead-Of-Time (AOT) C99 Transpiler & Native
#  Executable Compiler Backend.
#  Converts CHUD AST into standalone C99 code
#  and compiles to native .exe binaries via GCC.
# ─────────────────────────────────────────────

import os
import subprocess
import sys
from lexer import Lexer
from parser import Parser
from ast_nodes import (
    ProgramNode, AssignNode, YapNode, CheckNode,
    KeepNode, StopNode, SkipNode, BinOpNode, UnaryOpNode,
    NumberNode, StringNode, BoolNode, IdentifierNode, HearNode,
    LoopNode, FunctionNode, CallNode, ReturnNode,
    ArrayLiteralNode, IndexAccessNode, IndexAssignNode
)


# ══════════════════════════════════════════════
#  EMBEDDED SINGLE-HEADER C RUNTIME
#  Zero external dependencies — pure C99 stdlib.
# ══════════════════════════════════════════════

CHUD_RUNTIME_HEADER = r'''/* -- CHUD Standalone C Runtime (chud_runtime.h) -- */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <math.h>

typedef enum {
    CHUD_TYPE_NUMBER,
    CHUD_TYPE_STRING,
    CHUD_TYPE_BOOL,
    CHUD_TYPE_ARRAY,
    CHUD_TYPE_NONE
} CHUD_Type;

struct CHUD_Array;

typedef struct CHUD_Value {
    CHUD_Type type;
    union {
        double number;
        char* string;
        bool boolean;
        struct CHUD_Array* array;
    } as;
} CHUD_Value;

typedef struct CHUD_Array {
    CHUD_Value* items;
    int count;
    int capacity;
} CHUD_Array;

/* Memory Tracker for Safe Cleanup */
static void** g_allocs = NULL;
static int g_alloc_count = 0;
static int g_alloc_cap = 0;

static void chud_track_alloc(void* ptr) {
    if (!ptr) return;
    if (g_alloc_count >= g_alloc_cap) {
        g_alloc_cap = (g_alloc_cap == 0) ? 64 : g_alloc_cap * 2;
        g_allocs = (void**)realloc(g_allocs, sizeof(void*) * g_alloc_cap);
    }
    g_allocs[g_alloc_count++] = ptr;
}

static void chud_runtime_init(void) {}

static void chud_runtime_cleanup(void) {
    for (int i = 0; i < g_alloc_count; i++) {
        if (g_allocs[i]) {
            free(g_allocs[i]);
        }
    }
    if (g_allocs) {
        free(g_allocs);
        g_allocs = NULL;
    }
}

static void chud_panic(const char* msg) {
    fprintf(stderr, "\n[CHUD Native Runtime Error] %s\n", msg);
    chud_runtime_cleanup();
    exit(1);
}

/* Value Constructors */
static inline CHUD_Value chud_num(double n) {
    CHUD_Value v;
    v.type = CHUD_TYPE_NUMBER;
    v.as.number = n;
    return v;
}

static inline CHUD_Value chud_str(const char* s) {
    CHUD_Value v;
    v.type = CHUD_TYPE_STRING;
    size_t len = strlen(s);
    char* copy = (char*)malloc(len + 1);
    strcpy(copy, s);
    chud_track_alloc(copy);
    v.as.string = copy;
    return v;
}

static inline CHUD_Value chud_bool(bool b) {
    CHUD_Value v;
    v.type = CHUD_TYPE_BOOL;
    v.as.boolean = b;
    return v;
}

static inline CHUD_Value chud_none(void) {
    CHUD_Value v;
    v.type = CHUD_TYPE_NONE;
    v.as.number = 0;
    return v;
}

static CHUD_Value chud_build_array(int count, CHUD_Value* items) {
    CHUD_Array* arr = (CHUD_Array*)malloc(sizeof(CHUD_Array));
    chud_track_alloc(arr);
    arr->count = count;
    arr->capacity = (count > 4) ? count : 4;
    arr->items = (CHUD_Value*)malloc(sizeof(CHUD_Value) * arr->capacity);
    chud_track_alloc(arr->items);
    for (int i = 0; i < count; i++) {
        arr->items[i] = items[i];
    }
    CHUD_Value v;
    v.type = CHUD_TYPE_ARRAY;
    v.as.array = arr;
    return v;
}

/* Value Helpers & Conversions */
static char* chud_stringify(CHUD_Value v) {
    char buf[128];
    if (v.type == CHUD_TYPE_BOOL) {
        return v.as.boolean ? "W" : "L";
    }
    if (v.type == CHUD_TYPE_NUMBER) {
        if (floor(v.as.number) == v.as.number && !isinf(v.as.number)) {
            snprintf(buf, sizeof(buf), "%lld", (long long)v.as.number);
        } else {
            snprintf(buf, sizeof(buf), "%g", v.as.number);
        }
        char* res = (char*)malloc(strlen(buf) + 1);
        strcpy(res, buf);
        chud_track_alloc(res);
        return res;
    }
    if (v.type == CHUD_TYPE_STRING) {
        return v.as.string;
    }
    if (v.type == CHUD_TYPE_ARRAY) {
        CHUD_Array* arr = v.as.array;
        size_t cap = 256;
        char* out = (char*)malloc(cap);
        chud_track_alloc(out);
        strcpy(out, "[");
        for (int i = 0; i < arr->count; i++) {
            char* elem_str = chud_stringify(arr->items[i]);
            size_t needed = strlen(out) + strlen(elem_str) + 4;
            if (needed > cap) {
                cap = needed * 2;
                out = (char*)realloc(out, cap);
            }
            strcat(out, elem_str);
            if (i < arr->count - 1) {
                strcat(out, ", ");
            }
        }
        strcat(out, "]");
        return out;
    }
    return "None";
}

static inline bool chud_is_truthy(CHUD_Value v) {
    if (v.type == CHUD_TYPE_BOOL) return v.as.boolean;
    if (v.type == CHUD_TYPE_NUMBER) return v.as.number != 0;
    if (v.type == CHUD_TYPE_STRING) return strlen(v.as.string) > 0;
    if (v.type == CHUD_TYPE_ARRAY) return v.as.array->count > 0;
    return false;
}

/* Operations */
static CHUD_Value chud_add(CHUD_Value a, CHUD_Value b) {
    if (a.type == CHUD_TYPE_STRING || b.type == CHUD_TYPE_STRING) {
        char* sa = chud_stringify(a);
        char* sb = chud_stringify(b);
        char* comb = (char*)malloc(strlen(sa) + strlen(sb) + 1);
        chud_track_alloc(comb);
        strcpy(comb, sa);
        strcat(comb, sb);
        return chud_str(comb);
    }
    if (a.type != CHUD_TYPE_NUMBER || b.type != CHUD_TYPE_NUMBER) {
        chud_panic("Operator '+' requires numbers or string concatenation.");
    }
    return chud_num(a.as.number + b.as.number);
}

static CHUD_Value chud_sub(CHUD_Value a, CHUD_Value b) {
    if (a.type != CHUD_TYPE_NUMBER || b.type != CHUD_TYPE_NUMBER) chud_panic("Operator '-' requires numbers.");
    return chud_num(a.as.number - b.as.number);
}

static CHUD_Value chud_mul(CHUD_Value a, CHUD_Value b) {
    if (a.type != CHUD_TYPE_NUMBER || b.type != CHUD_TYPE_NUMBER) chud_panic("Operator '*' requires numbers.");
    return chud_num(a.as.number * b.as.number);
}

static CHUD_Value chud_div(CHUD_Value a, CHUD_Value b) {
    if (a.type != CHUD_TYPE_NUMBER || b.type != CHUD_TYPE_NUMBER) chud_panic("Operator '/' requires numbers.");
    if (b.as.number == 0) chud_panic("Division by zero is forbidden.");
    return chud_num(a.as.number / b.as.number);
}

static CHUD_Value chud_mod(CHUD_Value a, CHUD_Value b) {
    if (a.type != CHUD_TYPE_NUMBER || b.type != CHUD_TYPE_NUMBER) chud_panic("Operator '%' requires numbers.");
    if (b.as.number == 0) chud_panic("Modulo by zero is forbidden.");
    return chud_num(fmod(a.as.number, b.as.number));
}

static CHUD_Value chud_neg(CHUD_Value a) {
    if (a.type != CHUD_TYPE_NUMBER) chud_panic("Unary '-' requires a number.");
    return chud_num(-a.as.number);
}

static CHUD_Value chud_pos(CHUD_Value a) {
    if (a.type != CHUD_TYPE_NUMBER) chud_panic("Unary '+' requires a number.");
    return a;
}

static CHUD_Value chud_not(CHUD_Value a) {
    return chud_bool(!chud_is_truthy(a));
}

static CHUD_Value chud_eq(CHUD_Value a, CHUD_Value b) {
    if (a.type != b.type) return chud_bool(false);
    if (a.type == CHUD_TYPE_NUMBER) return chud_bool(a.as.number == b.as.number);
    if (a.type == CHUD_TYPE_BOOL) return chud_bool(a.as.boolean == b.as.boolean);
    if (a.type == CHUD_TYPE_STRING) return chud_bool(strcmp(a.as.string, b.as.string) == 0);
    if (a.type == CHUD_TYPE_ARRAY) return chud_bool(a.as.array == b.as.array);
    return chud_bool(true);
}

static CHUD_Value chud_neq(CHUD_Value a, CHUD_Value b) {
    CHUD_Value eq = chud_eq(a, b);
    return chud_bool(!eq.as.boolean);
}

static CHUD_Value chud_lt(CHUD_Value a, CHUD_Value b) {
    if (a.type != CHUD_TYPE_NUMBER || b.type != CHUD_TYPE_NUMBER) chud_panic("Operator '<' requires numbers.");
    return chud_bool(a.as.number < b.as.number);
}

static CHUD_Value chud_gt(CHUD_Value a, CHUD_Value b) {
    if (a.type != CHUD_TYPE_NUMBER || b.type != CHUD_TYPE_NUMBER) chud_panic("Operator '>' requires numbers.");
    return chud_bool(a.as.number > b.as.number);
}

static CHUD_Value chud_lte(CHUD_Value a, CHUD_Value b) {
    if (a.type != CHUD_TYPE_NUMBER || b.type != CHUD_TYPE_NUMBER) chud_panic("Operator '<=' requires numbers.");
    return chud_bool(a.as.number <= b.as.number);
}

static CHUD_Value chud_gte(CHUD_Value a, CHUD_Value b) {
    if (a.type != CHUD_TYPE_NUMBER || b.type != CHUD_TYPE_NUMBER) chud_panic("Operator '>=' requires numbers.");
    return chud_bool(a.as.number >= b.as.number);
}

/* Arrays & Builtins */
static CHUD_Value chud_array_get(CHUD_Value target, CHUD_Value index) {
    if (target.type != CHUD_TYPE_ARRAY && target.type != CHUD_TYPE_STRING) {
        chud_panic("Cannot index into non-array/string type.");
    }
    if (index.type != CHUD_TYPE_NUMBER) {
        chud_panic("Array index must be an integer.");
    }
    int idx = (int)index.as.number;
    if (target.type == CHUD_TYPE_ARRAY) {
        CHUD_Array* arr = target.as.array;
        if (idx < 0 || idx >= arr->count) {
            chud_panic("Array index out of bounds.");
        }
        return arr->items[idx];
    } else {
        char* str = target.as.string;
        int len = (int)strlen(str);
        if (idx < 0 || idx >= len) {
            chud_panic("String index out of bounds.");
        }
        char char_buf[2] = { str[idx], '\0' };
        return chud_str(char_buf);
    }
}

static void chud_array_set(CHUD_Value target, CHUD_Value index, CHUD_Value val) {
    if (target.type != CHUD_TYPE_ARRAY) {
        chud_panic("Cannot assign index to non-array type.");
    }
    if (index.type != CHUD_TYPE_NUMBER) {
        chud_panic("Array index must be an integer.");
    }
    CHUD_Array* arr = target.as.array;
    int idx = (int)index.as.number;
    if (idx < 0 || idx >= arr->count) {
        chud_panic("Array index out of bounds.");
    }
    arr->items[idx] = val;
}

static CHUD_Value chud_builtin_len(CHUD_Value target) {
    if (target.type == CHUD_TYPE_ARRAY) {
        return chud_num(target.as.array->count);
    }
    if (target.type == CHUD_TYPE_STRING) {
        return chud_num(strlen(target.as.string));
    }
    chud_panic("'len' expects array or string argument.");
    return chud_none();
}

static CHUD_Value chud_builtin_push(CHUD_Value target, CHUD_Value item) {
    if (target.type != CHUD_TYPE_ARRAY) {
        chud_panic("'push' first argument must be an array.");
    }
    CHUD_Array* arr = target.as.array;
    if (arr->count >= arr->capacity) {
        arr->capacity = (arr->capacity == 0) ? 4 : arr->capacity * 2;
        arr->items = (CHUD_Value*)realloc(arr->items, sizeof(CHUD_Value) * arr->capacity);
    }
    arr->items[arr->count++] = item;
    return chud_none();
}

static CHUD_Value chud_builtin_pop(CHUD_Value target) {
    if (target.type != CHUD_TYPE_ARRAY) {
        chud_panic("'pop' argument must be an array.");
    }
    CHUD_Array* arr = target.as.array;
    if (arr->count == 0) {
        chud_panic("Cannot pop from an empty array.");
    }
    return arr->items[--arr->count];
}

/* I/O Functions */
static void chud_yap(CHUD_Value v) {
    printf("%s\n", chud_stringify(v));
    fflush(stdout);
}

static CHUD_Value chud_hear(const char* prompt) {
    if (prompt && strlen(prompt) > 0) {
        printf("%s", prompt);
        fflush(stdout);
    }
    char buf[1024];
    if (!fgets(buf, sizeof(buf), stdin)) {
        return chud_str("");
    }
    size_t len = strlen(buf);
    while (len > 0 && (buf[len - 1] == '\n' || buf[len - 1] == '\r')) {
        buf[--len] = '\0';
    }
    if (strcmp(buf, "W") == 0) return chud_bool(true);
    if (strcmp(buf, "L") == 0) return chud_bool(false);
    char* endptr = NULL;
    double n = strtod(buf, &endptr);
    if (endptr != buf && *endptr == '\0') {
        return chud_num(n);
    }
    return chud_str(buf);
}
'''


# ══════════════════════════════════════════════
#  C CODE GENERATOR (AST VISITOR)
# ══════════════════════════════════════════════

class CCodeGenerator:
    """Translates a CHUD AST into standard C99 source code."""

    def __init__(self):
        self.declared_functions = []
        self.indent_level = 1

    def _indent(self):
        return "    " * self.indent_level

    def _sanitize_id(self, name):
        return f"chud_var_{name}"

    def _sanitize_fn(self, name):
        return f"chud_fn_{name}"

    def generate(self, ast):
        # 1. Forward declare functions and separate top-level statements
        fn_protos = []
        fn_definitions = []
        main_body_stmts = []

        for stmt in ast.statements:
            if isinstance(stmt, FunctionNode):
                fn_name = self._sanitize_fn(stmt.name)
                params = ", ".join(f"CHUD_Value {self._sanitize_id(p)}" for p in stmt.parameters)
                fn_protos.append(f"CHUD_Value {fn_name}({params if params else 'void'});")
                fn_definitions.append(self.generate_function(stmt))
            else:
                main_body_stmts.append(stmt)

        # 2. Generate main() body
        self.indent_level = 1
        main_lines = []
        for stmt in main_body_stmts:
            main_lines.append(self.generate_statement(stmt))

        # 3. Assemble full C source
        c_code = [
            CHUD_RUNTIME_HEADER,
            "\n/* -- Forward Function Declarations -- */",
            "\n".join(fn_protos) if fn_protos else "/* (No user-defined functions) */",
            "\n/* -- User-Defined Function Bodies -- */",
            "\n".join(fn_definitions) if fn_definitions else "/* (None) */",
            "\n/* -- Main Entry Point -- */",
            "int main(int argc, char** argv) {",
            "    chud_runtime_init();",
            "\n".join(main_lines),
            "    chud_runtime_cleanup();",
            "    return 0;",
            "}\n"
        ]
        return "\n".join(c_code)

    def generate_function(self, node):
        fn_name = self._sanitize_fn(node.name)
        params = ", ".join(f"CHUD_Value {self._sanitize_id(p)}" for p in node.parameters)
        old_indent = self.indent_level
        self.indent_level = 1
        body_lines = [self.generate_statement(s) for s in node.body]
        self.indent_level = old_indent
        body_lines.append("    return chud_none();")
        return f"\nCHUD_Value {fn_name}({params if params else 'void'}) {{\n" + "\n".join(body_lines) + "\n}\n"

    def generate_statement(self, node):
        ind = self._indent()

        if isinstance(node, AssignNode):
            val_code = self.generate_expr(node.value)
            var_name = self._sanitize_id(node.name)
            if node.is_declaration:
                return f"{ind}CHUD_Value {var_name} = {val_code};"
            else:
                return f"{ind}{var_name} = {val_code};"

        if isinstance(node, IndexAssignNode):
            target_code = self.generate_expr(node.target)
            idx_code = self.generate_expr(node.index)
            val_code = self.generate_expr(node.value)
            return f"{ind}chud_array_set({target_code}, {idx_code}, {val_code});"

        if isinstance(node, YapNode):
            val_code = self.generate_expr(node.value)
            return f"{ind}chud_yap({val_code});"

        if isinstance(node, CheckNode):
            cond_code = self.generate_expr(node.condition)
            self.indent_level += 1
            body_code = "\n".join(self.generate_statement(s) for s in node.body)
            self.indent_level -= 1
            res = f"{ind}if (chud_is_truthy({cond_code})) {{\n{body_code}\n{ind}}}"
            if node.else_body is not None:
                self.indent_level += 1
                else_code = "\n".join(self.generate_statement(s) for s in node.else_body)
                self.indent_level -= 1
                res += f" else {{\n{else_code}\n{ind}}}"
            return res

        if isinstance(node, KeepNode):
            cond_code = self.generate_expr(node.condition)
            self.indent_level += 1
            body_code = "\n".join(self.generate_statement(s) for s in node.body)
            self.indent_level -= 1
            return f"{ind}while (chud_is_truthy({cond_code})) {{\n{body_code}\n{ind}}}"

        if isinstance(node, LoopNode):
            # C scoped block
            self.indent_level += 1
            init_code = self.generate_statement(node.initializer).strip() if node.initializer else ""
            cond_code = self.generate_expr(node.condition)
            update_code = self.generate_statement(node.update).strip() if node.update else ""
            body_code = "\n".join(self.generate_statement(s) for s in node.body)
            self.indent_level -= 1
            return (
                f"{ind}{{\n"
                f"{ind}    {init_code}\n"
                f"{ind}    while (chud_is_truthy({cond_code})) {{\n"
                f"{body_code}\n"
                f"{ind}        {update_code}\n"
                f"{ind}    }}\n"
                f"{ind}}}"
            )

        if isinstance(node, StopNode):
            return f"{ind}break;"

        if isinstance(node, SkipNode):
            return f"{ind}continue;"

        if isinstance(node, ReturnNode):
            val_code = self.generate_expr(node.value) if node.value else "chud_none()"
            return f"{ind}return {val_code};"

        if isinstance(node, CallNode):
            return f"{ind}{self.generate_expr(node)};"

        return f"{ind}/* Unknown statement {type(node).__name__} */"

    def generate_expr(self, node):
        if isinstance(node, NumberNode):
            return f"chud_num({node.value})"

        if isinstance(node, StringNode):
            # Escape quotes and backslashes for C string literals
            escaped = node.value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            return f'chud_str("{escaped}")'

        if isinstance(node, BoolNode):
            return f"chud_bool({'true' if node.value else 'false'})"

        if isinstance(node, IdentifierNode):
            return self._sanitize_id(node.name)

        if isinstance(node, ArrayLiteralNode):
            if not node.elements:
                return "chud_build_array(0, NULL)"
            elems_c = ", ".join(self.generate_expr(e) for e in node.elements)
            return f"chud_build_array({len(node.elements)}, (CHUD_Value[]){{{elems_c}}})"

        if isinstance(node, IndexAccessNode):
            target_c = self.generate_expr(node.target)
            idx_c = self.generate_expr(node.index)
            return f"chud_array_get({target_c}, {idx_c})"

        if isinstance(node, CallNode):
            if node.name == 'len':
                arg = self.generate_expr(node.arguments[0])
                return f"chud_builtin_len({arg})"
            if node.name == 'push':
                arg0 = self.generate_expr(node.arguments[0])
                arg1 = self.generate_expr(node.arguments[1])
                return f"chud_builtin_push({arg0}, {arg1})"
            if node.name == 'pop':
                arg = self.generate_expr(node.arguments[0])
                return f"chud_builtin_pop({arg})"

            fn_name = self._sanitize_fn(node.name)
            args = ", ".join(self.generate_expr(a) for a in node.arguments)
            return f"{fn_name}({args})"

        if isinstance(node, HearNode):
            prompt = f'"{node.prompt}"' if node.prompt is not None else "NULL"
            return f"chud_hear({prompt})"

        if isinstance(node, UnaryOpNode):
            operand_c = self.generate_expr(node.operand)
            if node.op == '-':
                return f"chud_neg({operand_c})"
            if node.op == '+':
                return f"chud_pos({operand_c})"
            if node.op == '!':
                return f"chud_not({operand_c})"

        if isinstance(node, BinOpNode):
            left_c = self.generate_expr(node.left)
            right_c = self.generate_expr(node.right)
            if node.op == '+':
                return f"chud_add({left_c}, {right_c})"
            if node.op == '-':
                return f"chud_sub({left_c}, {right_c})"
            if node.op == '*':
                return f"chud_mul({left_c}, {right_c})"
            if node.op == '/':
                return f"chud_div({left_c}, {right_c})"
            if node.op == '%':
                return f"chud_mod({left_c}, {right_c})"
            if node.op == '==':
                return f"chud_eq({left_c}, {right_c})"
            if node.op == '!=':
                return f"chud_neq({left_c}, {right_c})"
            if node.op == '<':
                return f"chud_lt({left_c}, {right_c})"
            if node.op == '>':
                return f"chud_gt({left_c}, {right_c})"
            if node.op == '<=':
                return f"chud_lte({left_c}, {right_c})"
            if node.op == '>=':
                return f"chud_gte({left_c}, {right_c})"
            if node.op == 'and':
                return f"chud_bool(chud_is_truthy({left_c}) && chud_is_truthy({right_c}))"
            if node.op == 'or':
                return f"chud_bool(chud_is_truthy({left_c}) || chud_is_truthy({right_c}))"

        return "chud_none()"


# ══════════════════════════════════════════════
#  HIGH-LEVEL COMPILATION DRIVER
# ══════════════════════════════════════════════

def transpile_source_to_c(source_code: str) -> str:
    """Convenience: CHUD source string -> C99 source string."""
    tokens = Lexer(source_code).tokenize()
    ast = Parser(tokens).parse()
    return CCodeGenerator().generate(ast)


def compile_chud_to_executable(source_code: str, output_exe_path: str, compiler_cmd: str = "gcc") -> str:
    """Transpiles CHUD source code to C and compiles it directly into a standalone .exe."""
    c_source = transpile_source_to_c(source_code)
    c_temp_file = output_exe_path + ".c"

    with open(c_temp_file, "w", encoding="utf-8") as f:
        f.write(c_source)

    try:
        # Invoke GCC with C99 standard and optimizations
        cmd = [compiler_cmd, "-std=c99", "-O2", c_temp_file, "-o", output_exe_path]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"C Compilation failed:\n{res.stderr}")
        return output_exe_path
    finally:
        # Keep .c file if user wants, or clean up if desired
        pass


if __name__ == '__main__':
    src = '''
make bubble_sort(arr) {
    let n = len(arr)
    loop let i = 0; i < n; i = i + 1 {
        loop let j = 0; j < n - i - 1; j = j + 1 {
            check arr[j] > arr[j + 1] {
                let temp = arr[j]
                arr[j] = arr[j + 1]
                arr[j + 1] = temp
            }
        }
    }
    return arr
}

let numbers = [64, 34, 25, 12, 22, 11, 90]
yap "Original: " + numbers
let sorted = bubble_sort(numbers)
yap "Sorted: " + sorted
'''
    print(transpile_source_to_c(src))
