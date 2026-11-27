"""
SIV864/CSM011 - Assignment 2: Huffman Coding (paper-based questions)
M.Tech level implementation.

This module implements a GENERALIZED (D-ary) Huffman coding routine,
directly following Huffman's 1952 paper "A Method for the Construction of
Minimum-Redundancy Codes" (section: "Generalization of the Method"), to
concretely demonstrate the answer to the assignment's third question:
"Is it possible to extend the binary coding (0,1) to more digits, say
three (0,1,2)?" -> Yes, and this script proves it constructively.

Key idea from the paper (D-ary case):
  - At every merge step, combine D (not just 2) least-probable nodes into
    one composite node.
  - If the total number of original symbols N does not allow the *last*
    merge to be a full group of D, the paper shows that (N - n0) must be
    divisible by (D-1), where n0 (2 <= n0 <= D) is the number of symbols
    combined in the *first* merge. We therefore pad the symbol set with
    zero-probability dummy symbols so this divisibility condition holds
    (this is the standard, textbook way to make any N compatible with a
    D-ary Huffman tree).

Author: Saurabh
"""

import heapq
from collections import Counter
from itertools import count


class Node:
    __slots__ = ("freq", "symbol", "children")

    def __init__(self, freq, symbol=None, children=None):
        self.freq = freq
        self.symbol = symbol
        self.children = children or []

    def is_leaf(self):
        return not self.children


def pad_for_dary(freq_table: dict, D: int) -> dict:
    """Add zero-probability dummy symbols so that a full D-ary Huffman tree
    can be built with every internal node having exactly D children.

    Each merge step reduces the node count by (D-1): D nodes go in, 1
    composite node comes out. Starting from N leaves and ending at a
    single root requires
        (N - 1) % (D - 1) == 0.
    If this does not hold, we pad with zero-probability dummy symbols
    until it does. Since their probability is zero they never affect the
    average code length -- they only influence which *real* low-probability
    symbols get merged first, exactly analogous to Huffman's n0 < D initial
    merge in the 1952 paper's D=4 example (Table III)."""
    freq_table = dict(freq_table)
    N = len(freq_table)
    if D == 2:
        return freq_table  # binary case never needs padding
    dummy_idx = 0
    while (N - 1) % (D - 1) != 0:
        freq_table[f"_dummy{dummy_idx}_"] = 0
        dummy_idx += 1
        N += 1
    return freq_table


def build_dary_huffman_tree(freq_table: dict, D: int) -> Node:
    tie = count()
    heap = [(freq, next(tie), Node(freq, symbol=sym)) for sym, freq in freq_table.items()]
    heapq.heapify(heap)

    if len(heap) == 1:
        return heap[0][2]

    while len(heap) > 1:
        group = []
        take = min(D, len(heap))
        for _ in range(take):
            group.append(heapq.heappop(heap))
        merged_freq = sum(f for f, _, _ in group)
        merged = Node(merged_freq, children=[n for _, _, n in group])
        heapq.heappush(heap, (merged_freq, next(tie), merged))

    return heap[0][2]


def build_dary_codes(node: Node, prefix="", codebook=None) -> dict:
    if codebook is None:
        codebook = {}
    if node.is_leaf():
        if node.symbol is not None and not str(node.symbol).startswith("_dummy"):
            codebook[node.symbol] = prefix or "0"
        return codebook
    for digit, child in enumerate(node.children):
        build_dary_codes(child, prefix + str(digit), codebook)
    return codebook


def dary_huffman_encode(message: list, D: int = 3) -> dict:
    freq_table = Counter(message)
    padded = pad_for_dary(freq_table, D)
    tree = build_dary_huffman_tree(padded, D)
    codebook = build_dary_codes(tree)
    encoded = "".join(codebook[s] for s in message)
    avg_len = sum(freq_table[s] * len(codebook[s]) for s in freq_table) / len(message)
    return {
        "D": D,
        "freq_table": dict(freq_table),
        "codebook": codebook,
        "encoded": encoded,
        "avg_code_length_D_ary_digits": avg_len,
    }


if __name__ == "__main__":
    # Reproduce Huffman's own D=4 example from Table III of the 1952 paper
    # (message probabilities 0.22, 0.20, 0.18, 0.15, 0.10, 0.08, 0.05, 0.02)
    # scaled to integer "counts" out of 100 for a frequency-table demo.
    paper_probs = {
        "m1": 22, "m2": 20, "m3": 18, "m4": 15,
        "m5": 10, "m6": 8, "m7": 5, "m8": 2,
    }
    print("=" * 70)
    print("Reproducing Huffman (1952) Table III example with D = 4")
    print("=" * 70)
    result4 = dary_huffman_encode(
        [sym for sym, cnt in paper_probs.items() for _ in range(cnt)], D=4
    )
    for sym, code in sorted(result4["codebook"].items()):
        print(f"  {sym}: code={code}  length={len(code)}")
    print(f"  Average code length (D=4 digits/symbol): {result4['avg_code_length_D_ary_digits']:.3f}")

    print()
    print("=" * 70)
    print("Ternary (D = 3) Huffman coding demo, answering Q3 of the assignment")
    print("=" * 70)
    # Message: reuse the contact-number-derived message from Assignment 1
    # (0703888598 -> digit // 2) to show the SAME source encoded in ternary.
    message = [0, 3, 0, 1, 4, 4, 4, 2, 4, 4]
    result3 = dary_huffman_encode(message, D=3)
    print(f"  Message: {message}")
    print(f"  Frequency table: {result3['freq_table']}")
    print("  Ternary Huffman codebook (digits from {0,1,2}):")
    for sym, code in sorted(result3["codebook"].items()):
        print(f"    symbol {sym}: code = {code}  (length {len(code)} ternary digits)")
    print(f"  Encoded (ternary) stream: {result3['encoded']}")
    print(f"  Average code length: {result3['avg_code_length_D_ary_digits']:.3f} ternary digits/symbol")
    print()
    print("  => Confirms the paper's generalization: Huffman's optimal-code")
    print("     construction works for any radix D >= 2, not just D = 2.")
