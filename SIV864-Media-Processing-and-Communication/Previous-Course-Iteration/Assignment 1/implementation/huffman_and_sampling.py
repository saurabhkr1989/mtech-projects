"""
SIV864/CSM011 - Assignment 1: Sampling and Huffman Coding
M.Tech level implementation.

Q1: Bandwidth (bps) for a bandlimited signal, Nyquist frequency = 1 Hz, 16 quantization levels.
Q2: Storage comparison between two images (A: 100x100 @ 8 bpp, B: 200x200 @ 4 bpp).
Q3: Huffman coding of a message derived from a 10-digit contact number.

Author: Saurabh
"""

import math
import heapq
from collections import Counter
from itertools import count


# ---------------------------------------------------------------------------
# Q1: Sampling bandwidth
# ---------------------------------------------------------------------------
def q1_bandwidth(nyquist_freq_hz: float, quant_levels: int) -> dict:
    """
    Nyquist frequency f_N is the highest frequency component present in the
    band-limited signal. To avoid distortion (aliasing), the Nyquist sampling
    theorem requires a sampling rate:

        f_s >= 2 * f_N   (samples/sec)

    For distortion-free transmission we take the minimum (Nyquist) rate:

        f_s = 2 * f_N

    Each sample is quantized to one of `quant_levels` levels, requiring

        b = ceil(log2(quant_levels))  bits/sample

    The channel bit rate (bandwidth in bps) required is:

        R = f_s * b   (bits per second)
    """
    sampling_rate = 2 * nyquist_freq_hz          # Nyquist rate, samples/sec
    bits_per_sample = math.log2(quant_levels)    # exact since 16 = 2^4
    assert bits_per_sample == int(bits_per_sample), "quant_levels must be a power of 2"
    bits_per_sample = int(bits_per_sample)
    bit_rate_bps = sampling_rate * bits_per_sample
    return {
        "nyquist_freq_hz": nyquist_freq_hz,
        "sampling_rate_sps": sampling_rate,
        "bits_per_sample": bits_per_sample,
        "bandwidth_bps": bit_rate_bps,
    }


# ---------------------------------------------------------------------------
# Q2: Storage comparison
# ---------------------------------------------------------------------------
def q2_storage(width_a, height_a, bpp_a, width_b, height_b, bpp_b) -> dict:
    pixels_a = width_a * height_a
    pixels_b = width_b * height_b
    bits_a = pixels_a * bpp_a
    bits_b = pixels_b * bpp_b
    return {
        "image_A": {"pixels": pixels_a, "bpp": bpp_a, "bits": bits_a,
                     "bytes": bits_a / 8, "KB": bits_a / 8 / 1024},
        "image_B": {"pixels": pixels_b, "bpp": bpp_b, "bits": bits_b,
                     "bytes": bits_b / 8, "KB": bits_b / 8 / 1024},
        "larger": "B" if bits_b > bits_a else ("A" if bits_a > bits_b else "equal"),
        "ratio_B_over_A": bits_b / bits_a,
    }


# ---------------------------------------------------------------------------
# Q3: Huffman coding of contact-number-derived message
# ---------------------------------------------------------------------------
class Node:
    __slots__ = ("freq", "symbol", "left", "right")

    def __init__(self, freq, symbol=None, left=None, right=None):
        self.freq = freq
        self.symbol = symbol
        self.left = left
        self.right = right

    def is_leaf(self):
        return self.left is None and self.right is None


def build_huffman_tree(freq_table: dict) -> Node:
    """Standard Huffman tree construction (binary, D=2) using a min-heap.
    A tie-breaking counter guarantees a stable, reproducible tree."""
    tie = count()
    heap = [(freq, next(tie), Node(freq, symbol=sym)) for sym, freq in freq_table.items()]
    heapq.heapify(heap)

    if len(heap) == 1:
        # Degenerate single-symbol ensemble
        (freq, _, only) = heap[0]
        return Node(freq, left=only)

    while len(heap) > 1:
        f1, _, n1 = heapq.heappop(heap)
        f2, _, n2 = heapq.heappop(heap)
        merged = Node(f1 + f2, left=n1, right=n2)
        heapq.heappush(heap, (merged.freq, next(tie), merged))

    return heap[0][2]


def build_codes(node: Node, prefix="", codebook=None) -> dict:
    if codebook is None:
        codebook = {}
    if node.is_leaf():
        codebook[node.symbol] = prefix or "0"
        return codebook
    if node.left:
        build_codes(node.left, prefix + "0", codebook)
    if node.right:
        build_codes(node.right, prefix + "1", codebook)
    return codebook


def huffman_encode(message: list) -> dict:
    freq_table = Counter(message)
    tree = build_huffman_tree(freq_table)
    codebook = build_codes(tree)
    encoded_bits = "".join(codebook[sym] for sym in message)

    n_symbols = len(freq_table)
    fixed_len_bits_per_symbol = math.ceil(math.log2(n_symbols)) if n_symbols > 1 else 1
    fixed_len_total = fixed_len_bits_per_symbol * len(message)

    avg_len = sum(freq_table[s] * len(codebook[s]) for s in freq_table) / len(message)

    return {
        "message": message,
        "freq_table": dict(freq_table),
        "codebook": codebook,
        "encoded_bits": encoded_bits,
        "huffman_total_bits": len(encoded_bits),
        "fixed_length_bits_per_symbol": fixed_len_bits_per_symbol,
        "fixed_length_total_bits": fixed_len_total,
        "avg_code_length": avg_len,
        "compression_ratio": fixed_len_total / len(encoded_bits) if encoded_bits else None,
    }


def q3_contact_number_huffman(contact_number: str) -> dict:
    digits = [int(d) for d in contact_number]
    message = [d // 2 for d in digits]  # integer quotient on division by 2
    result = huffman_encode(message)
    result["contact_number"] = contact_number
    result["digits"] = digits
    result["quotients"] = message
    return result


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("Q1: Sampling bandwidth")
    print("=" * 70)
    r1 = q1_bandwidth(nyquist_freq_hz=1, quant_levels=16)
    for k, v in r1.items():
        print(f"  {k}: {v}")

    print()
    print("=" * 70)
    print("Q2: Storage comparison (Image A vs Image B)")
    print("=" * 70)
    r2 = q2_storage(100, 100, 8, 200, 200, 4)
    print(f"  Image A: {r2['image_A']}")
    print(f"  Image B: {r2['image_B']}")
    print(f"  Larger image: {r2['larger']}  (B/A ratio = {r2['ratio_B_over_A']:.2f}x)")

    print()
    print("=" * 70)
    print("Q3: Huffman coding of contact-number-derived message")
    print("=" * 70)
    CONTACT_NUMBER = "0703888598"
    r3 = q3_contact_number_huffman(CONTACT_NUMBER)
    print(f"  Contact number : {r3['contact_number']}")
    print(f"  Digits         : {r3['digits']}")
    print(f"  Quotients(/2)  : {r3['quotients']}")
    print(f"  Frequency table: {r3['freq_table']}")
    print("  Huffman codebook:")
    for sym, code in sorted(r3['codebook'].items()):
        print(f"    symbol {sym}: code = {code}  (len {len(code)})")
    print(f"  Encoded bitstream : {r3['encoded_bits']}")
    print(f"  Huffman total bits: {r3['huffman_total_bits']}")
    print(f"  Fixed-length bits/symbol: {r3['fixed_length_bits_per_symbol']}  -> total {r3['fixed_length_total_bits']} bits")
    print(f"  Average Huffman code length: {r3['avg_code_length']:.3f} bits/symbol")
    print(f"  Compression ratio vs fixed-length: {r3['compression_ratio']:.3f}x")
