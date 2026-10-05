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
    ArrayLiteralNode, IndexAccessNode, IndexAssignNode,
    DictLiteralNode, UseNode
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
#include <stdint.h>
#include <ctype.h>
#include <math.h>

typedef enum {
    CHUD_TYPE_NUMBER,
    CHUD_TYPE_STRING,
    CHUD_TYPE_BOOL,
    CHUD_TYPE_ARRAY,
    CHUD_TYPE_MAP,
    CHUD_TYPE_NONE
} CHUD_Type;

struct CHUD_Array;
struct CHUD_Map;

typedef struct CHUD_Value {
    CHUD_Type type;
    union {
        double number;
        char* string;
        bool boolean;
        struct CHUD_Array* array;
        struct CHUD_Map* map;
    } as;
} CHUD_Value;

typedef struct CHUD_Array {
    CHUD_Value* items;
    int count;
    int capacity;
} CHUD_Array;

typedef struct CHUD_MapEntry {
    char* key;
    CHUD_Value value;
    struct CHUD_MapEntry* next;
} CHUD_MapEntry;

typedef struct CHUD_Map {
    CHUD_MapEntry** buckets;
    int bucket_count;
    int size;
} CHUD_Map;

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

/* Dedicated Tracker for Dynamic Arrays (prevents double-free when realloc moves items) */
static CHUD_Array** g_arrays = NULL;
static int g_array_count = 0;
static int g_array_cap = 0;

static void chud_track_array(CHUD_Array* arr) {
    if (!arr) return;
    if (g_array_count >= g_array_cap) {
        g_array_cap = (g_array_cap == 0) ? 32 : g_array_cap * 2;
        g_arrays = (CHUD_Array**)realloc(g_arrays, sizeof(CHUD_Array*) * g_array_cap);
    }
    g_arrays[g_array_count++] = arr;
}

/* Dedicated Tracker for Maps */
static CHUD_Map** g_maps = NULL;
static int g_map_count = 0;
static int g_map_cap = 0;

static void chud_track_map(CHUD_Map* map) {
    if (!map) return;
    if (g_map_count >= g_map_cap) {
        g_map_cap = (g_map_cap == 0) ? 32 : g_map_cap * 2;
        g_maps = (CHUD_Map**)realloc(g_maps, sizeof(CHUD_Map*) * g_map_cap);
    }
    g_maps[g_map_count++] = map;
}

static void chud_runtime_init(void) {}

static void chud_runtime_cleanup(void) {
    /* 1. Cleanly free all dynamic array items and array headers */
    for (int i = 0; i < g_array_count; i++) {
        if (g_arrays[i]) {
            if (g_arrays[i]->items) {
                free(g_arrays[i]->items);
                g_arrays[i]->items = NULL;
            }
            free(g_arrays[i]);
            g_arrays[i] = NULL;
        }
    }
    if (g_arrays) {
        free(g_arrays);
        g_arrays = NULL;
        g_array_count = 0;
        g_array_cap = 0;
    }

    /* 2. Cleanly free all hash maps */
    for (int i = 0; i < g_map_count; i++) {
        if (g_maps[i]) {
            for (int b = 0; b < g_maps[i]->bucket_count; b++) {
                CHUD_MapEntry* cur = g_maps[i]->buckets[b];
                while (cur) {
                    CHUD_MapEntry* next = cur->next;
                    if (cur->key) free(cur->key);
                    free(cur);
                    cur = next;
                }
            }
            if (g_maps[i]->buckets) free(g_maps[i]->buckets);
            free(g_maps[i]);
            g_maps[i] = NULL;
        }
    }
    if (g_maps) {
        free(g_maps);
        g_maps = NULL;
        g_map_count = 0;
        g_map_cap = 0;
    }

    /* 3. Free all tracked scalar heap allocations */
    for (int i = 0; i < g_alloc_count; i++) {
        if (g_allocs[i]) {
            free(g_allocs[i]);
            g_allocs[i] = NULL;
        }
    }
    if (g_allocs) {
        free(g_allocs);
        g_allocs = NULL;
        g_alloc_count = 0;
        g_alloc_cap = 0;
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
    chud_track_array(arr);
    arr->count = count;
    arr->capacity = (count > 4) ? count : 4;
    arr->items = (CHUD_Value*)malloc(sizeof(CHUD_Value) * arr->capacity);
    for (int i = 0; i < count; i++) {
        arr->items[i] = items[i];
    }
    CHUD_Value v;
    v.type = CHUD_TYPE_ARRAY;
    v.as.array = arr;
    return v;
}

/* Hash Map Support */
static unsigned int chud_hash_str(const char* s) {
    unsigned int hash = 5381;
    int c;
    while ((c = (unsigned char)*s++)) {
        hash = ((hash << 5) + hash) + c;
    }
    return hash;
}

static CHUD_Value chud_build_map(int pair_count, char** keys, CHUD_Value* values) {
    CHUD_Map* map = (CHUD_Map*)malloc(sizeof(CHUD_Map));
    chud_track_map(map);
    map->bucket_count = (pair_count > 8) ? pair_count * 2 : 16;
    map->size = 0;
    map->buckets = (CHUD_MapEntry**)calloc(map->bucket_count, sizeof(CHUD_MapEntry*));
    for (int i = 0; i < pair_count; i++) {
        unsigned int h = chud_hash_str(keys[i]) % map->bucket_count;
        CHUD_MapEntry* entry = (CHUD_MapEntry*)malloc(sizeof(CHUD_MapEntry));
        entry->key = (char*)malloc(strlen(keys[i]) + 1);
        strcpy(entry->key, keys[i]);
        entry->value = values[i];
        entry->next = map->buckets[h];
        map->buckets[h] = entry;
        map->size++;
    }
    CHUD_Value v;
    v.type = CHUD_TYPE_MAP;
    v.as.map = map;
    return v;
}

static char* chud_stringify(CHUD_Value v);

static CHUD_Value chud_map_get(CHUD_Value target, CHUD_Value key) {
    if (target.type != CHUD_TYPE_MAP) chud_panic("Cannot map-get non-map type.");
    char* kstr = chud_stringify(key);
    CHUD_Map* map = target.as.map;
    unsigned int h = chud_hash_str(kstr) % map->bucket_count;
    CHUD_MapEntry* cur = map->buckets[h];
    while (cur) {
        if (strcmp(cur->key, kstr) == 0) {
            return cur->value;
        }
        cur = cur->next;
    }
    char buf[256];
    snprintf(buf, sizeof(buf), "Key '%s' not found in dictionary.", kstr);
    chud_panic(buf);
    return chud_none();
}

static void chud_map_set(CHUD_Value target, CHUD_Value key, CHUD_Value val) {
    if (target.type != CHUD_TYPE_MAP) chud_panic("Cannot map-set non-map type.");
    char* kstr = chud_stringify(key);
    CHUD_Map* map = target.as.map;
    unsigned int h = chud_hash_str(kstr) % map->bucket_count;
    CHUD_MapEntry* cur = map->buckets[h];
    while (cur) {
        if (strcmp(cur->key, kstr) == 0) {
            cur->value = val;
            return;
        }
        cur = cur->next;
    }
    CHUD_MapEntry* entry = (CHUD_MapEntry*)malloc(sizeof(CHUD_MapEntry));
    entry->key = (char*)malloc(strlen(kstr) + 1);
    strcpy(entry->key, kstr);
    entry->value = val;
    entry->next = map->buckets[h];
    map->buckets[h] = entry;
    map->size++;
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
    if (v.type == CHUD_TYPE_MAP) {
        CHUD_Map* map = v.as.map;
        size_t cap = 256;
        char* out = (char*)malloc(cap);
        chud_track_alloc(out);
        strcpy(out, "{");
        int count = 0;
        for (int b = 0; b < map->bucket_count; b++) {
            CHUD_MapEntry* cur = map->buckets[b];
            while (cur) {
                char* val_str = chud_stringify(cur->value);
                size_t needed = strlen(out) + strlen(cur->key) + strlen(val_str) + 8;
                if (needed > cap) {
                    cap = needed * 2;
                    out = (char*)realloc(out, cap);
                }
                strcat(out, cur->key);
                strcat(out, ": ");
                strcat(out, val_str);
                count++;
                if (count < map->size) {
                    strcat(out, ", ");
                }
                cur = cur->next;
            }
        }
        strcat(out, "}");
        return out;
    }
    return "None";
}

static inline bool chud_is_truthy(CHUD_Value v) {
    if (v.type == CHUD_TYPE_BOOL) return v.as.boolean;
    if (v.type == CHUD_TYPE_NUMBER) return v.as.number != 0;
    if (v.type == CHUD_TYPE_STRING) return strlen(v.as.string) > 0;
    if (v.type == CHUD_TYPE_ARRAY) return v.as.array->count > 0;
    if (v.type == CHUD_TYPE_MAP) return v.as.map->size > 0;
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
    if (a.type == CHUD_TYPE_MAP) return chud_bool(a.as.map == b.as.map);
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

/* Arrays & Maps Access */
static CHUD_Value chud_array_get(CHUD_Value target, CHUD_Value index) {
    if (target.type == CHUD_TYPE_MAP) {
        return chud_map_get(target, index);
    }
    if (target.type != CHUD_TYPE_ARRAY && target.type != CHUD_TYPE_STRING) {
        chud_panic("Cannot index into non-array/string/map type.");
    }
    if (index.type != CHUD_TYPE_NUMBER) {
        chud_panic("Array/String index must be an integer.");
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
    if (target.type == CHUD_TYPE_MAP) {
        chud_map_set(target, index, val);
        return;
    }
    if (target.type != CHUD_TYPE_ARRAY) {
        chud_panic("Cannot assign index to non-array/map type.");
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

/* Builtins: len, push, pop */
static CHUD_Value chud_builtin_len(CHUD_Value target) {
    if (target.type == CHUD_TYPE_ARRAY) {
        return chud_num(target.as.array->count);
    }
    if (target.type == CHUD_TYPE_STRING) {
        return chud_num(strlen(target.as.string));
    }
    if (target.type == CHUD_TYPE_MAP) {
        return chud_num(target.as.map->size);
    }
    chud_panic("'len' expects array, string, or map argument.");
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

/* Builtins: keys, values, has */
static CHUD_Value chud_builtin_keys(CHUD_Value target) {
    if (target.type != CHUD_TYPE_MAP) chud_panic("'keys' argument must be a map.");
    CHUD_Map* map = target.as.map;
    CHUD_Value* items = (CHUD_Value*)malloc(sizeof(CHUD_Value) * (map->size > 0 ? map->size : 1));
    int idx = 0;
    for (int b = 0; b < map->bucket_count; b++) {
        CHUD_MapEntry* cur = map->buckets[b];
        while (cur) {
            items[idx++] = chud_str(cur->key);
            cur = cur->next;
        }
    }
    CHUD_Value res = chud_build_array(map->size, items);
    free(items);
    return res;
}

static CHUD_Value chud_builtin_values(CHUD_Value target) {
    if (target.type != CHUD_TYPE_MAP) chud_panic("'values' argument must be a map.");
    CHUD_Map* map = target.as.map;
    CHUD_Value* items = (CHUD_Value*)malloc(sizeof(CHUD_Value) * (map->size > 0 ? map->size : 1));
    int idx = 0;
    for (int b = 0; b < map->bucket_count; b++) {
        CHUD_MapEntry* cur = map->buckets[b];
        while (cur) {
            items[idx++] = cur->value;
            cur = cur->next;
        }
    }
    CHUD_Value res = chud_build_array(map->size, items);
    free(items);
    return res;
}

static CHUD_Value chud_builtin_has(CHUD_Value target, CHUD_Value key) {
    if (target.type == CHUD_TYPE_MAP) {
        char* kstr = chud_stringify(key);
        CHUD_Map* map = target.as.map;
        unsigned int h = chud_hash_str(kstr) % map->bucket_count;
        CHUD_MapEntry* cur = map->buckets[h];
        while (cur) {
            if (strcmp(cur->key, kstr) == 0) return chud_bool(true);
            cur = cur->next;
        }
        return chud_bool(false);
    }
    if (target.type == CHUD_TYPE_ARRAY) {
        CHUD_Array* arr = target.as.array;
        for (int i = 0; i < arr->count; i++) {
            if (chud_eq(arr->items[i], key).as.boolean) return chud_bool(true);
        }
        return chud_bool(false);
    }
    if (target.type == CHUD_TYPE_STRING && key.type == CHUD_TYPE_STRING) {
        return chud_bool(strstr(target.as.string, key.as.string) != NULL);
    }
    chud_panic("'has' expects map, array, or string target.");
    return chud_bool(false);
}

/* Builtins: File I/O */
static CHUD_Value chud_builtin_read_file(CHUD_Value path_val) {
    if (path_val.type != CHUD_TYPE_STRING) chud_panic("'read_file' path must be a string.");
    FILE* fp = fopen(path_val.as.string, "rb");
    if (!fp) chud_panic("Failed to open file for reading.");
    fseek(fp, 0, SEEK_END);
    long sz = ftell(fp);
    fseek(fp, 0, SEEK_SET);
    char* buf = (char*)malloc(sz + 1);
    size_t read_bytes = fread(buf, 1, sz, fp);
    buf[read_bytes] = '\0';
    fclose(fp);
    chud_track_alloc(buf);
    CHUD_Value res;
    res.type = CHUD_TYPE_STRING;
    res.as.string = buf;
    return res;
}

static CHUD_Value chud_builtin_write_file(CHUD_Value path_val, CHUD_Value content_val) {
    if (path_val.type != CHUD_TYPE_STRING) chud_panic("'write_file' path must be a string.");
    char* cstr = chud_stringify(content_val);
    FILE* fp = fopen(path_val.as.string, "wb");
    if (!fp) chud_panic("Failed to open file for writing.");
    fputs(cstr, fp);
    fclose(fp);
    return chud_none();
}

static CHUD_Value chud_builtin_file_exists(CHUD_Value path_val) {
    if (path_val.type != CHUD_TYPE_STRING) chud_panic("'file_exists' path must be a string.");
    FILE* fp = fopen(path_val.as.string, "rb");
    if (fp) {
        fclose(fp);
        return chud_bool(true);
    }
    return chud_bool(false);
}

/* Builtins: String Utilities */
static CHUD_Value chud_builtin_slice(CHUD_Value target, CHUD_Value s_val, CHUD_Value e_val) {
    if (s_val.type != CHUD_TYPE_NUMBER || e_val.type != CHUD_TYPE_NUMBER) {
        chud_panic("'slice' indices must be numbers.");
    }
    int total_len = (target.type == CHUD_TYPE_ARRAY) ? target.as.array->count :
                    (target.type == CHUD_TYPE_STRING) ? (int)strlen(target.as.string) : -1;
    if (total_len == -1) chud_panic("'slice' target must be array or string.");

    int start = (int)s_val.as.number;
    int end = (int)e_val.as.number;
    if (start < 0) start += total_len;
    if (end < 0) end += total_len;
    if (start < 0) start = 0;
    if (end > total_len) end = total_len;
    if (start > end) start = end;

    if (target.type == CHUD_TYPE_ARRAY) {
        int count = end - start;
        CHUD_Value* slice_items = (CHUD_Value*)malloc(sizeof(CHUD_Value) * (count > 0 ? count : 1));
        for (int i = 0; i < count; i++) {
            slice_items[i] = target.as.array->items[start + i];
        }
        CHUD_Value res = chud_build_array(count, slice_items);
        free(slice_items);
        return res;
    } else {
        int count = end - start;
        char* buf = (char*)malloc(count + 1);
        memcpy(buf, target.as.string + start, count);
        buf[count] = '\0';
        chud_track_alloc(buf);
        CHUD_Value res;
        res.type = CHUD_TYPE_STRING;
        res.as.string = buf;
        return res;
    }
}

static CHUD_Value chud_builtin_split(CHUD_Value target, CHUD_Value delim_val) {
    if (target.type != CHUD_TYPE_STRING || delim_val.type != CHUD_TYPE_STRING) {
        chud_panic("'split' requires string arguments.");
    }
    char* src = target.as.string;
    char* delim = delim_val.as.string;
    size_t dlen = strlen(delim);

    CHUD_Value* items = NULL;
    int count = 0;
    int cap = 0;

    if (dlen == 0) {
        /* Split by char */
        count = (int)strlen(src);
        items = (CHUD_Value*)malloc(sizeof(CHUD_Value) * (count > 0 ? count : 1));
        for (int i = 0; i < count; i++) {
            char cbuf[2] = { src[i], '\0' };
            items[i] = chud_str(cbuf);
        }
    } else {
        char* cur = src;
        while (1) {
            char* next = strstr(cur, delim);
            int part_len = next ? (int)(next - cur) : (int)strlen(cur);
            char* part = (char*)malloc(part_len + 1);
            memcpy(part, cur, part_len);
            part[part_len] = '\0';

            if (count >= cap) {
                cap = (cap == 0) ? 8 : cap * 2;
                items = (CHUD_Value*)realloc(items, sizeof(CHUD_Value) * cap);
            }
            items[count++] = chud_str(part);
            free(part);

            if (!next) break;
            cur = next + dlen;
        }
    }
    CHUD_Value res = chud_build_array(count, items);
    if (items) free(items);
    return res;
}

static CHUD_Value chud_builtin_trim(CHUD_Value target) {
    if (target.type != CHUD_TYPE_STRING) chud_panic("'trim' argument must be string.");
    char* s = target.as.string;
    while (*s && isspace((unsigned char)*s)) s++;
    int len = (int)strlen(s);
    while (len > 0 && isspace((unsigned char)s[len - 1])) len--;
    char* buf = (char*)malloc(len + 1);
    memcpy(buf, s, len);
    buf[len] = '\0';
    chud_track_alloc(buf);
    CHUD_Value res;
    res.type = CHUD_TYPE_STRING;
    res.as.string = buf;
    return res;
}

static CHUD_Value chud_builtin_lower(CHUD_Value target) {
    if (target.type != CHUD_TYPE_STRING) chud_panic("'lower' argument must be string.");
    int len = (int)strlen(target.as.string);
    char* buf = (char*)malloc(len + 1);
    for (int i = 0; i < len; i++) {
        buf[i] = tolower((unsigned char)target.as.string[i]);
    }
    buf[len] = '\0';
    chud_track_alloc(buf);
    CHUD_Value res;
    res.type = CHUD_TYPE_STRING;
    res.as.string = buf;
    return res;
}

static CHUD_Value chud_builtin_upper(CHUD_Value target) {
    if (target.type != CHUD_TYPE_STRING) chud_panic("'upper' argument must be string.");
    int len = (int)strlen(target.as.string);
    char* buf = (char*)malloc(len + 1);
    for (int i = 0; i < len; i++) {
        buf[i] = toupper((unsigned char)target.as.string[i]);
    }
    buf[len] = '\0';
    chud_track_alloc(buf);
    CHUD_Value res;
    res.type = CHUD_TYPE_STRING;
    res.as.string = buf;
    return res;
}

static CHUD_Value chud_builtin_replace(CHUD_Value target, CHUD_Value old_val, CHUD_Value new_val) {
    if (target.type != CHUD_TYPE_STRING || old_val.type != CHUD_TYPE_STRING || new_val.type != CHUD_TYPE_STRING) {
        chud_panic("'replace' arguments must be strings.");
    }
    char* src = target.as.string;
    char* old_s = old_val.as.string;
    char* new_s = new_val.as.string;
    size_t old_len = strlen(old_s);
    size_t new_len = strlen(new_s);

    if (old_len == 0) return target;

    size_t cap = strlen(src) * 2 + 1;
    char* out = (char*)malloc(cap);
    out[0] = '\0';

    char* cur = src;
    while (1) {
        char* next = strstr(cur, old_s);
        if (!next) {
            strcat(out, cur);
            break;
        }
        size_t part_len = next - cur;
        size_t needed = strlen(out) + part_len + new_len + 1;
        if (needed > cap) {
            cap = needed * 2;
            out = (char*)realloc(out, cap);
        }
        strncat(out, cur, part_len);
        strcat(out, new_s);
        cur = next + old_len;
    }
    chud_track_alloc(out);
    CHUD_Value res;
    res.type = CHUD_TYPE_STRING;
    res.as.string = out;
    return res;
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

    def _flatten_ast(self, statements, visited=None):
        if visited is None:
            visited = set()
        flat = []
        for stmt in statements:
            if isinstance(stmt, UseNode):
                mod_path = os.path.abspath(stmt.module_path)
                if mod_path not in visited:
                    visited.add(mod_path)
                    if not os.path.exists(mod_path):
                        # Try relative to cwd
                        if os.path.exists(stmt.module_path):
                            mod_path = os.path.abspath(stmt.module_path)
                        else:
                            raise RuntimeError(f"Cannot use module '{stmt.module_path}': File not found.")
                    with open(mod_path, 'r', encoding='utf-8') as f:
                        mod_code = f.read()
                    mod_ast = Parser(Lexer(mod_code).tokenize()).parse()
                    flat.extend(self._flatten_ast(mod_ast.statements, visited))
            else:
                flat.append(stmt)
        return flat

    def generate(self, ast):
        all_stmts = self._flatten_ast(ast.statements)

        # 1. Forward declare functions and separate top-level statements
        fn_protos = []
        fn_definitions = []
        main_body_stmts = []

        for stmt in all_stmts:
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
            # Native C for loop scoped block (preserves update on continue/skip)
            self.indent_level += 1
            init_code = self.generate_statement(node.initializer).strip() if node.initializer else ""
            cond_code = self.generate_expr(node.condition)
            update_code = self.generate_statement(node.update).strip() if node.update else ""
            if update_code.endswith(";"):
                update_code = update_code[:-1].strip()
            body_code = "\n".join(self.generate_statement(s) for s in node.body)
            self.indent_level -= 1
            return (
                f"{ind}{{\n"
                f"{ind}    {init_code}\n"
                f"{ind}    for (; chud_is_truthy({cond_code}); {update_code}) {{\n"
                f"{body_code}\n"
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

        if isinstance(node, UseNode):
            return f"{ind}/* Inlined use '{node.module_path}' */"

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

        if isinstance(node, DictLiteralNode):
            if not node.pairs:
                return "chud_build_map(0, NULL, NULL)"
            keys_c = ", ".join(self.generate_expr(k) + ".as.string" if isinstance(k, StringNode) else f"chud_stringify({self.generate_expr(k)})" for k, v in node.pairs)
            vals_c = ", ".join(self.generate_expr(v) for k, v in node.pairs)
            return f"chud_build_map({len(node.pairs)}, (char*[]){{{keys_c}}}, (CHUD_Value[]){{{vals_c}}})"

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
            if node.name == 'keys':
                arg = self.generate_expr(node.arguments[0])
                return f"chud_builtin_keys({arg})"
            if node.name == 'values':
                arg = self.generate_expr(node.arguments[0])
                return f"chud_builtin_values({arg})"
            if node.name == 'has':
                arg0 = self.generate_expr(node.arguments[0])
                arg1 = self.generate_expr(node.arguments[1])
                return f"chud_builtin_has({arg0}, {arg1})"
            if node.name == 'read_file':
                arg = self.generate_expr(node.arguments[0])
                return f"chud_builtin_read_file({arg})"
            if node.name == 'write_file':
                arg0 = self.generate_expr(node.arguments[0])
                arg1 = self.generate_expr(node.arguments[1])
                return f"chud_builtin_write_file({arg0}, {arg1})"
            if node.name == 'file_exists':
                arg = self.generate_expr(node.arguments[0])
                return f"chud_builtin_file_exists({arg})"
            if node.name == 'slice':
                arg0 = self.generate_expr(node.arguments[0])
                arg1 = self.generate_expr(node.arguments[1])
                arg2 = self.generate_expr(node.arguments[2])
                return f"chud_builtin_slice({arg0}, {arg1}, {arg2})"
            if node.name == 'split':
                arg0 = self.generate_expr(node.arguments[0])
                arg1 = self.generate_expr(node.arguments[1])
                return f"chud_builtin_split({arg0}, {arg1})"
            if node.name == 'trim':
                arg = self.generate_expr(node.arguments[0])
                return f"chud_builtin_trim({arg})"
            if node.name == 'lower':
                arg = self.generate_expr(node.arguments[0])
                return f"chud_builtin_lower({arg})"
            if node.name == 'upper':
                arg = self.generate_expr(node.arguments[0])
                return f"chud_builtin_upper({arg})"
            if node.name == 'replace':
                arg0 = self.generate_expr(node.arguments[0])
                arg1 = self.generate_expr(node.arguments[1])
                arg2 = self.generate_expr(node.arguments[2])
                return f"chud_builtin_replace({arg0}, {arg1}, {arg2})"

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


def find_c_compiler() -> str:
    """Finds an available C compiler on the system (gcc, clang, cc)."""
    import shutil
    # 1. Check standard PATH
    for comp in ["gcc", "clang", "cc"]:
        found = shutil.which(comp)
        if found:
            return found

    # 2. Check common Windows MinGW / MSYS2 paths
    if sys.platform == "win32":
        common_paths = [
            r"C:\msys64\mingw64\bin\gcc.exe",
            r"C:\msys64\ucrt64\bin\gcc.exe",
            r"C:\msys64\usr\bin\gcc.exe",
            r"C:\Program Files\Git\mingw64\bin\gcc.exe",
            r"C:\MinGW\bin\gcc.exe",
        ]
        for p in common_paths:
            if os.path.isfile(p):
                return p

    return None


def compile_chud_to_executable(source_code: str, output_exe_path: str, compiler_cmd: str = None) -> str:
    """Transpiles CHUD source code to C and compiles it directly into a standalone executable across OSes."""
    if compiler_cmd is None:
        compiler_cmd = find_c_compiler()

    if not compiler_cmd:
        raise RuntimeError("No working C compiler (gcc, clang, cc) was found on the system.")

    c_source = transpile_source_to_c(source_code)
    c_temp_file = output_exe_path + ".c"

    with open(c_temp_file, "w", encoding="utf-8") as f:
        f.write(c_source)

    try:
        cmd = [compiler_cmd, "-std=c99", "-O2", c_temp_file, "-o", output_exe_path]
        # Link math library on Linux/Unix systems (required for fmod, floor in libm)
        if sys.platform != "win32":
            cmd.append("-lm")

        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"C Compilation failed with {compiler_cmd}:\n{res.stderr}")
        return output_exe_path
    finally:
        pass


if __name__ == '__main__':
    src = '''
let user = { "name": "Chad", "level": 9000 }
yap user["name"]
user["level"] = 9001
yap user["level"]
yap keys(user)
'''
    print(transpile_source_to_c(src))
