from __future__ import annotations

import hashlib
import os
import math
import re
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple, Set
from tree_sitter import Language, Parser, Node, Query, QueryCursor

import tree_sitter_cpp
import tree_sitter_python
import tree_sitter_java
from analyzer.cpp_cleaner import clean_cpp_code


@dataclass(frozen=True)
class LanguageSupport:
    lang_id: str
    ts_language: Language
    cleaner_func: Optional[Callable] = None


# Language Registry implementing the Open-Closed Principle.
# To support a new language:
# 1. Add the tree-sitter package to requirements.
# 2. Add an entry to this dictionary.
# 3. Create corresponding declarative queries in queries/{lang_id}/*.scm.
LANG_REGISTRY: Dict[str, LanguageSupport] = {
    "cpp": LanguageSupport(
        lang_id="cpp",
        ts_language=Language(tree_sitter_cpp.language()),
        cleaner_func=clean_cpp_code
    ),
    "py": LanguageSupport(
        lang_id="py",
        ts_language=Language(tree_sitter_python.language()),
        cleaner_func=None
    ),
    "java": LanguageSupport(
        lang_id="java",
        ts_language=Language(tree_sitter_java.language()),
        cleaner_func=None
    ),
    # PLACEHOLDER FOR FUTURE EXTENSIONS:
    # "go": LanguageSupport(
    #     lang_id="go",
    #     ts_language=Language(tree_sitter_go.language()),
    #     cleaner_func=None
    # ),
}


def remove_ranges_from_bytes(ranges: List[Tuple[int, int]], code_bytes: bytes) -> bytes:
    """
    Safely removes byte ranges from source code.
    Tree-sitter returns AST node offsets in bytes. Slicing standard Python strings
    using byte offsets can corrupt multi-byte UTF-8 characters (e.g., Cyrillic
    characters in comments). Operating strictly on byte arrays prevents this.
    """
    if not ranges:
        return code_bytes

    ranges.sort()

    merged_ranges = []
    current_start, current_end = ranges[0]

    for start, end in ranges[1:]:
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            merged_ranges.append((current_start, current_end))
            current_start, current_end = start, end
    merged_ranges.append((current_start, current_end))

    clean_chunks = []
    last_idx = 0
    for start, end in merged_ranges:
        clean_chunks.append(code_bytes[last_idx:start])
        last_idx = end
    clean_chunks.append(code_bytes[last_idx:])

    return b"".join(clean_chunks)


def _execute_query(root: Node, ts_lang: Language, query_path: str) -> Dict[str, List[Node]]:
    """
    Reads a Scheme (.scm) query file and executes it against the AST root.
    Returns a natively formatted dictionary mapping tag names to lists of matched Nodes.
    """

    base_dir = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(base_dir, query_path)

    if not os.path.exists(full_path):
        raise FileNotFoundError(f"No scheme file provided on path: {full_path}")

    with open(full_path, "r", encoding="utf-8") as f:
        query_text = f.read()

    query = Query(ts_lang, query_text)
    return QueryCursor(query).captures(root)


def _get_subtree_hash(node: Node) -> str:
    """
    Generates a structural hash of an AST subtree.
    Ignores specific identifiers and values, focusing on structural type composition.
    """
    hasher = hashlib.md5()
    hasher.update(node.type.encode())
    for child in node.children:
        if child.is_named:
            hasher.update(_get_subtree_hash(child).encode())
    return hasher.hexdigest()


def calculate_identifiers(root: Node, ts_lang: Language, lang_id: str) -> Tuple[int, int, float]:
    captures_dict = _execute_query(root, ts_lang, f"queries/{lang_id}/identifiers.scm")
    id_nodes = captures_dict.get("id", [])

    identifiers = [node.text.decode("utf-8", errors="ignore") for node in id_nodes]

    total_length = sum(len(i) for i in identifiers)
    unique_count = len(set(identifiers))
    avg_length = total_length / len(identifiers) if identifiers else 0.0

    return total_length, unique_count, avg_length


def calculate_comments_and_sloc(root: Node, code_bytes: bytes, ts_lang: Language, lang_id: str) -> Tuple[int, int, float]:
    captures_dict = _execute_query(root, ts_lang, f"queries/{lang_id}/comments.scm")
    comment_nodes = captures_dict.get("comment", [])
    ranges = [(node.start_byte, node.end_byte) for node in comment_nodes]

    clean_bytes = remove_ranges_from_bytes(ranges, code_bytes)

    code_str = code_bytes.decode("utf-8", errors="ignore")
    clean_code_str = clean_bytes.decode("utf-8", errors="ignore")

    total_chars = len(code_str)
    comments_char_length = total_chars - len(clean_code_str)

    sloc = sum(1 for line in clean_code_str.splitlines() if line.strip())
    source_chars = sum(1 for ch in clean_code_str if ch not in {' ', '\t', '\n', '\r'})

    comment_ratio = comments_char_length / total_chars if total_chars > 0 else 0.0

    return sloc, source_chars, comment_ratio


def calculate_syntax(root: Node, code_str: str, ts_lang: Language, lang_id: str) -> Tuple[int, int]:
    captures_dict = _execute_query(root, ts_lang, f"queries/{lang_id}/syntax.scm")
    goto_count = len(captures_dict.get("goto", []))
    max_line_length = max((len(line) for line in code_str.splitlines()), default=0)

    return goto_count, max_line_length


def calculate_nesting_depth(root: Node, ts_lang: Language, lang_id: str) -> int:
    captures_dict = _execute_query(root, ts_lang, f"queries/{lang_id}/nesting.scm")
    block_nodes = captures_dict.get("block", [])

    block_node_ids: Set[int] = {node.id for node in block_nodes}
    max_depth = 0

    for node in block_nodes:
        current_depth = 1
        ancestor = node.parent
        while ancestor is not None:
            if ancestor.id in block_node_ids:
                current_depth += 1
            ancestor = ancestor.parent
        if current_depth > max_depth:
            max_depth = current_depth

    return max_depth


def calculate_complexity(root: Node, ts_lang: Language, lang_id: str) -> Tuple[int, int, int]:
    captures_dict = _execute_query(root, ts_lang, f"queries/{lang_id}/complexity.scm")

    decisions = len(captures_dict.get("decision", []))
    branches = len(captures_dict.get("branch", []))
    loops = len(captures_dict.get("loop", []))

    cyclomatic_complexity = 1 + decisions
    return cyclomatic_complexity, branches, loops


def calculate_modularity(root: Node, ts_lang: Language, lang_id: str, total_sloc: int) -> float:
    if total_sloc == 0:
        return 0.0

    captures_dict = _execute_query(root, ts_lang, f"queries/{lang_id}/functions.scm")
    func_nodes = captures_dict.get("func", [])

    max_func_sloc = 0
    for node in func_nodes:
        func_sloc = node.end_point.row - node.start_point.row + 1
        if func_sloc > max_func_sloc:
            max_func_sloc = func_sloc

    return max_func_sloc / total_sloc


def calculate_magic_numbers(root: Node, ts_lang: Language, lang_id: str) -> int:
    captures_dict = _execute_query(root, ts_lang, f"queries/{lang_id}/numbers.scm")
    num_nodes = captures_dict.get("number", [])

    allowed_values = {0.0, 1.0, 2.0, -1.0}
    magic_count = 0

    for node in num_nodes:
        text = node.text.decode("utf-8")
        
        if node.parent and node.parent.type in ("unary_operator", "unary_expression"):
            operator_node = node.parent.children[0]
            if operator_node.text == b"-":
                text = "-" + text
                
        text = text.replace("_", "") # for Python / Java
        text = text.replace("'", "") # for C++14+
        
        text = re.sub(r'[fFuUlL]+$', '', text)

        try:
            if 'j' in text.lower():
                val = float(complex(text).real)
            elif '.' in text or 'e' in text.lower():
                val = float(text)
            else:
                val = float(int(text, 0)) 
        except ValueError:
            continue 

        if val not in allowed_values:
            magic_count += 1

    return magic_count


def calculate_halstead(root: Node, ts_lang: Language, lang_id: str) -> Tuple[float, float, float]:
    captures_dict = _execute_query(root, ts_lang, f"queries/{lang_id}/halstead.scm")
    operators = [node.text for node in captures_dict.get("operator", [])]
    operands = [node.text for node in captures_dict.get("operand", [])]

    n1 = len(set(operators))
    n2 = len(set(operands))
    N1 = len(operators)
    N2 = len(operands)

    vocabulary = n1 + n2
    length = N1 + N2

    volume = length * math.log2(vocabulary) if vocabulary > 0 else 0.0
    difficulty = (n1 / 2) * (N2 / n2) if n2 > 0 else 0.0
    effort = volume * difficulty

    return volume, difficulty, effort


def calculate_duplication(root: Node, ts_lang: Language, lang_id: str) -> float:
    """
    Detects structural duplication by hashing function/block nodes.
    Returns the ratio of duplicated blocks to total blocks.
    """
    captures_dict = _execute_query(root, ts_lang, f"queries/{lang_id}/blocks.scm")
    blocks = captures_dict.get("block", [])

    if not blocks:
        return 0.0

    hashes = [_get_subtree_hash(n) for n in blocks]
    total = len(hashes)
    duplicates = total - len(set(hashes))
    return duplicates / total


def analyze_code(code: str, lang: str) -> dict:
    lang_support = LANG_REGISTRY.get(lang)
    if not lang_support:
        raise ValueError(f"Language configuration '{lang}' is not supported.")

    if lang_support.cleaner_func:
        code = lang_support.cleaner_func(code)

    code_bytes = code.encode("utf-8")

    parser = Parser(lang_support.ts_language)
    tree = parser.parse(code_bytes)
    root = tree.root_node

    total_len, unique_ids, avg_len = calculate_identifiers(root, lang_support.ts_language, lang)
    sloc, source_chars, comment_ratio = calculate_comments_and_sloc(root, code_bytes, lang_support.ts_language, lang)
    goto_count, max_line_len = calculate_syntax(root, code, lang_support.ts_language, lang)
    nesting = calculate_nesting_depth(root, lang_support.ts_language, lang)
    complexity, branches, loops = calculate_complexity(root, lang_support.ts_language, lang)
    modularity = calculate_modularity(root, lang_support.ts_language, lang, sloc)
    magic_numbers = calculate_magic_numbers(root, lang_support.ts_language, lang)
    duplication = calculate_duplication(root, lang_support.ts_language, lang)
    halstead_volume, halstead_difficulty, halstead_effort = calculate_halstead(root, lang_support.ts_language, lang)
    mi_raw = 171 - 5.2 * math.log(halstead_volume) - 0.23 * complexity - 16.2 * math.log(sloc) if halstead_volume > 0 and sloc > 0 else 0.0
    maintainability_index = max(0.0, mi_raw * 100 / 171)

    return {
        'total_var_name_length': total_len,
        'source_char_count': source_chars,
        'sloc': sloc,
        'unique_identifiers': unique_ids,
        'comment_ratio': comment_ratio,
        'keyword_goto_count': goto_count,
        'max_line_length': max_line_len,
        'avg_identifier_length': avg_len,
        'nesting_depth': nesting,
        'cyclomatic_complexity': complexity,
        'branch_count': branches,
        'loop_count': loops,
        'modularity_ratio': modularity,
        'magic_number_count': magic_numbers,
        'structural_duplication_ratio': duplication,
        'halstead_volume': halstead_volume,
        'halstead_difficulty': halstead_difficulty,
        'halstead_effort': halstead_effort,
        'maintainability_index': maintainability_index,
    }