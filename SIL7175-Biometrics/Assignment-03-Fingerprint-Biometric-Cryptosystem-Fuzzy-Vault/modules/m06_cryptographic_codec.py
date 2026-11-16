"""
m06_cryptographic_codec.py - Cryptographic Codec for Fuzzy Vault

This module implements all cryptographic operations needed for the Chaff-Free
Fuzzy Vault system. The mathematics operates entirely over Galois Field GF(2^16),
providing a finite field where all arithmetic is well-defined and reversible.

The module provides three layers of functionality:

Layer 1: Galois Field GF(2^16) Arithmetic
==========================================
A finite field with 2^16 = 65,536 elements where addition and multiplication
follow special rules (XOR and binary polynomial multiplication).

Key Properties:
  - Addition: XOR operation (same as subtraction)
  - Multiplication: Binary polynomial multiplication mod primitive polynomial
  - Division: Multiplicative inverse exists for all non-zero elements
  - Inverse: Can be computed via extended Euclidean algorithm
  - Power: Repeated multiplication (exponentiation)

Implementation: Log/Exp Tables
  - Precomputes log and exp tables for fast multiplication
  - exp_table[i] = α^i (where α is a primitive root)
  - log_table[x] = i such that α^i = x
  - Multiplication: a × b = exp_table[log_table[a] + log_table[b]]
  - Inverse: a^-1 = exp_table[GF_MULTIPLICATIVE_ORDER - log_table[a]]

Primitive Polynomial: x^16 + x^5 + x^3 + x^2 + 1 (0x1002D)
  - Irreducible polynomial ensuring field closure
  - Reduction rule: x^16 ≡ x^5 + x^3 + x^2 + 1 (mod irreducible)

Layer 2: Reed-Solomon Error Correction RS(9, 8)
================================================
Error correction code that encodes 8 data symbols into 9 codeword symbols.
Adds 1 parity symbol for detecting transmission errors.

Encoding Process:
  1. Input: 8 data symbols (each 16-bit, representing 128-bit secret)
  2. Compute parity: Using RS generator polynomial
  3. Output: 9 symbols = [8 data + 1 parity]
  4. Use: These 9 symbols become polynomial coefficients c0..c8

Decoding Process:
  1. Input: Received 9 symbols (possibly corrupted)
  2. Compute syndrome: Evaluate codeword at special points
  3. If syndrome = 0: No error, extract first 8 symbols
  4. If syndrome ≠ 0: Locate and correct error (if within capability)
  5. Output: Original 8 data symbols if correctable; None if error exceeds capacity

Capacity: RS(9,8) with 1 parity can detect 1 error or correct 0 errors
  (2t = 1 → t = 0.5, effectively error detection only)

Layer 3: Polynomial Operations
===============================
Work with polynomials in GF(2^16)[x] (polynomials with GF(2^16) coefficients):

  Polynomial P(x) = c0 + c1×x + c2×x^2 + ... + c8×x^8

Evaluation (Horner's Method):
  P(v) = c0 ⊕ v⊗(c1 ⊕ v⊗(c2 ⊕ ... ⊕ v⊗c8))
  - Computes polynomial value at point v ∈ GF(2^16)
  - Used during enrollment: each minutia v produces vault point P(v)

Lagrange Interpolation:
  Given 9 points {(v_i, y_i)} with distinct v_i values
  Recovers polynomial P(x) such that P(v_i) = y_i

  Formula: P(x) = Σ y_i × L_i(x) where
           L_i(x) = Π_{j≠i} (x - v_j) / (v_i - v_j)

  Used during verification: recover polynomial from matching minutiae
  Extract 9 coefficients from P(x) to get RS codeword

Integration in Fuzzy Vault
===========================
Enrollment:
  1. Generate 128-bit random secret
  2. RS encode (8 symbols → 9 symbols)
  3. 9 RS symbols become polynomial coefficients c0..c8
  4. For each minutia (x, y): compute vault point (x XOR y, P((x<<8)|y))

Verification:
  1. Extract matching minutiae from probe
  2. Collect their (v, P(v)) values from vault
  3. Use Lagrange to interpolate polynomial P from 9 matches
  4. Extract coefficients (RS codeword)
  5. RS decode to recover secret
  6. If successful → GENUINE; if RS decode fails → IMPOSTOR
"""

import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.utilities import config
from modules.m00_logger import log_step, log_data, log_warning

# ============================================================================
# GPU ACCELERATION (Optional - Numba JIT)
# ============================================================================

_GPU_ACCELERATED = False
try:
    from numba import jit
    _GPU_ACCELERATED = True
except ImportError:
    _GPU_ACCELERATED = False

# ============================================================================
# PART A: GF(2^16) ARITHMETIC
# ============================================================================

# Primitive polynomial and field constants
# Primitive polynomial x^16 + x^5 + x^3 + x^2 + 1
# Binary: 1 0000 0000 0010 1101 = 0x1002D
GF_PRIMITIVE_POLY_HEX = 0x1002D
GF_FIELD_SIZE = 2 ** 16
GF_MULTIPLICATIVE_ORDER = GF_FIELD_SIZE - 1


def _build_log_exp_tables():
    """Precompute log and exp tables for GF(2^16)."""
    exp_table = [0] * (2 * GF_MULTIPLICATIVE_ORDER)
    log_table = [0] * GF_FIELD_SIZE
    log_table[0] = -1

    current_power = 1
    for exponent in range(GF_MULTIPLICATIVE_ORDER):
        exp_table[exponent] = current_power
        log_table[current_power] = exponent

        current_power <<= 1
        if current_power & GF_FIELD_SIZE:
            current_power ^= GF_PRIMITIVE_POLY_HEX
            current_power &= (GF_FIELD_SIZE - 1)

    for exponent in range(GF_MULTIPLICATIVE_ORDER):
        exp_table[GF_MULTIPLICATIVE_ORDER + exponent] = exp_table[exponent]

    return exp_table, log_table


_EXP_TABLE, _LOG_TABLE = _build_log_exp_tables()

# Convert to NumPy arrays for Numba JIT (if available)
_EXP_TABLE_ARRAY = np.array(_EXP_TABLE, dtype=np.uint32) if _GPU_ACCELERATED else None
_LOG_TABLE_ARRAY = np.array(_LOG_TABLE, dtype=np.int32) if _GPU_ACCELERATED else None


# JIT-compiled GF multiplication (10-100x faster for batch operations)
if _GPU_ACCELERATED:
    @jit(nopython=True, cache=True)
    def _gf_multiply_jit(a: int, b: int, exp_table, log_table) -> int:
        """JIT-compiled GF(2^16) multiplication."""
        if a == 0 or b == 0:
            return 0
        log_sum = log_table[a] + log_table[b]
        return exp_table[log_sum]


def gf_add(first_element: int, second_element: int) -> int:
    """Add two GF(2^16) elements (bitwise XOR)."""
    return first_element ^ second_element


def gf_subtract(first_element: int, second_element: int) -> int:
    """Subtract two GF(2^16) elements."""
    return first_element ^ second_element


def gf_multiply(first_element: int, second_element: int) -> int:
    """Multiply two GF(2^16) elements using log/exp tables.

    Uses Numba JIT acceleration if available (~10-100x speedup for batch ops).
    """
    if _GPU_ACCELERATED:
        return int(_gf_multiply_jit(first_element, second_element, _EXP_TABLE_ARRAY, _LOG_TABLE_ARRAY))
    else:
        if first_element == 0 or second_element == 0:
            return 0
        log_sum = _LOG_TABLE[first_element] + _LOG_TABLE[second_element]
        return _EXP_TABLE[log_sum]


def gf_divide(numerator: int, denominator: int) -> int:
    """Divide numerator by denominator in GF(2^16)."""
    if denominator == 0:
        raise ZeroDivisionError("GF(2^16) division by zero")
    if numerator == 0:
        return 0
    log_diff = _LOG_TABLE[numerator] - _LOG_TABLE[denominator]
    if log_diff < 0:
        log_diff += GF_MULTIPLICATIVE_ORDER
    return _EXP_TABLE[log_diff]


def gf_inverse(element: int) -> int:
    """Compute multiplicative inverse in GF(2^16)."""
    if element == 0:
        raise ZeroDivisionError("Zero has no multiplicative inverse")
    log_inverse = GF_MULTIPLICATIVE_ORDER - _LOG_TABLE[element]
    return _EXP_TABLE[log_inverse]


def gf_power(base: int, exponent: int) -> int:
    """Raise base to an integer exponent in GF(2^16)."""
    if base == 0:
        return 0 if exponent != 0 else 1
    if exponent == 0:
        return 1

    log_result = (_LOG_TABLE[base] * exponent) % GF_MULTIPLICATIVE_ORDER
    return _EXP_TABLE[log_result]


# ============================================================================
# PART B: REED-SOLOMON CODEC
# ============================================================================

def _build_generator_polynomial(num_parity_symbols: int) -> list:
    """Build RS generator polynomial g(x) = (x − α^0)(x − α^1)..."""
    primitive_element = 2
    generator_coeffs = [1]

    for parity_index in range(num_parity_symbols):
        root_value = gf_power(primitive_element, parity_index)

        new_coeffs = [0] * (len(generator_coeffs) + 1)
        for coeff_index, coeff_value in enumerate(generator_coeffs):
            new_coeffs[coeff_index + 1] = gf_add(new_coeffs[coeff_index + 1], coeff_value)
            new_coeffs[coeff_index] = gf_add(
                new_coeffs[coeff_index],
                gf_multiply(root_value, coeff_value),
            )

        generator_coeffs = new_coeffs

    return generator_coeffs


def _polynomial_remainder_over_gf(dividend: list, divisor: list) -> list:
    """Polynomial long division in GF(2^16). Returns remainder."""
    working_copy = list(dividend)
    divisor_degree = len(divisor) - 1

    for step in range(len(dividend) - divisor_degree):
        if working_copy[step] == 0:
            continue
        leading_coefficient = working_copy[step]
        for divisor_pos in range(1, len(divisor)):
            if divisor[divisor_pos] != 0:
                working_copy[step + divisor_pos] = gf_add(
                    working_copy[step + divisor_pos],
                    gf_multiply(leading_coefficient, divisor[divisor_pos]),
                )

    remainder = working_copy[-(divisor_degree):]
    return remainder


def _evaluate_polynomial_at_gf_element(polynomial_coefficients: list, evaluation_point: int) -> int:
    """Evaluate polynomial at a GF(2^16) point using Horner's method."""
    accumulated_value = 0
    for coefficient in polynomial_coefficients:
        accumulated_value = gf_add(
            gf_multiply(accumulated_value, evaluation_point),
            coefficient,
        )
    return accumulated_value


def _compute_syndromes(received: list, num_parity_symbols: int) -> list:
    """Compute RS syndromes S_i = received(α^i)."""
    primitive_element = 2
    syndromes = []
    for parity_index in range(num_parity_symbols):
        root = gf_power(primitive_element, parity_index)
        syndrome_value = _evaluate_polynomial_at_gf_element(received, root)
        syndromes.append(syndrome_value)
    return syndromes


def _berlekamp_massey(syndromes: list) -> list:
    """Berlekamp-Massey: find error locator polynomial Λ(x)."""
    num_syndromes = len(syndromes)
    current_locator = [1]
    last_locator = [1]
    length = 0
    last_discrepancy = 1
    last_length_change_step = 1

    for step_index in range(num_syndromes):
        discrepancy = syndromes[step_index]
        for loc_index in range(1, length + 1):
            discrepancy = gf_add(
                discrepancy,
                gf_multiply(current_locator[loc_index], syndromes[step_index - loc_index]),
            )

        if discrepancy == 0:
            last_length_change_step += 1
            continue

        temp_locator = list(current_locator)
        scale_factor = gf_divide(discrepancy, last_discrepancy)
        shifted_last = [0] * last_length_change_step + last_locator

        while len(current_locator) < len(shifted_last):
            current_locator.append(0)

        for coeff_pos in range(len(shifted_last)):
            current_locator[coeff_pos] = gf_add(
                current_locator[coeff_pos],
                gf_multiply(scale_factor, shifted_last[coeff_pos]),
            )

        if 2 * length <= step_index:
            length = step_index + 1 - length
            last_locator = temp_locator
            last_discrepancy = discrepancy
            last_length_change_step = 1
        else:
            last_length_change_step += 1

    return current_locator


def _chien_search(error_locator_polynomial: list, codeword_length: int) -> list:
    """Chien search: find all positions where Λ(α^{-i}) = 0."""
    primitive_element = 2
    error_positions = []

    for position_index in range(codeword_length):
        evaluation_point = gf_power(primitive_element, -position_index)
        locator_value = _evaluate_polynomial_at_gf_element(error_locator_polynomial, evaluation_point)
        if locator_value == 0:
            error_positions.append(position_index)

    return error_positions


def _forney_algorithm(syndromes: list, error_locator_polynomial: list, error_positions: list) -> list:
    """Forney algorithm: compute error magnitude at each position."""
    primitive_element = 2
    num_parity = len(syndromes)

    syndrome_polynomial = syndromes
    omega_length = num_parity
    omega_polynomial = [0] * omega_length

    for loc_idx, loc_coeff in enumerate(error_locator_polynomial):
        for syn_idx, syn_coeff in enumerate(syndrome_polynomial):
            omega_idx = loc_idx + syn_idx
            if omega_idx < omega_length:
                omega_polynomial[omega_idx] = gf_add(
                    omega_polynomial[omega_idx],
                    gf_multiply(loc_coeff, syn_coeff),
                )

    locator_derivative = [0] * len(error_locator_polynomial)
    for coeff_idx in range(1, len(error_locator_polynomial), 2):
        locator_derivative[coeff_idx - 1] = error_locator_polynomial[coeff_idx]

    error_magnitudes = []
    for error_pos in error_positions:
        x_inverse = gf_power(primitive_element, -error_pos)

        omega_at_x_inv = _evaluate_polynomial_at_gf_element(omega_polynomial, x_inverse)
        lambda_deriv_at_x_inv = _evaluate_polynomial_at_gf_element(locator_derivative, x_inverse)

        if lambda_deriv_at_x_inv == 0:
            error_magnitudes.append(0)
        else:
            magnitude = gf_divide(omega_at_x_inv, lambda_deriv_at_x_inv)
            error_magnitudes.append(magnitude)

    return error_magnitudes


def rs_encode(data_symbols: list, num_parity_symbols: int = None) -> list:
    """Systematic RS encoding over GF(2^16)."""
    if num_parity_symbols is None:
        num_parity_symbols = config.RS_PARITY_SYMBOLS

    # log_step(f"RS encoding {len(data_symbols)} data symbols + {num_parity_symbols} parity")  # Suppressed

    if num_parity_symbols == 0:
        return list(data_symbols)

    generator_polynomial = _build_generator_polynomial(num_parity_symbols)
    shifted_data_polynomial = list(data_symbols) + [0] * num_parity_symbols
    remainder = _polynomial_remainder_over_gf(shifted_data_polynomial, generator_polynomial)

    encoded_codeword = list(data_symbols) + remainder
    # log_data("Codeword length", len(encoded_codeword))  # Suppressed
    return encoded_codeword


def rs_decode(received_symbols: list, num_parity_symbols: int = None, silent: bool = False):
    """RS decoding over GF(2^16). Returns corrected data or None."""
    if num_parity_symbols is None:
        num_parity_symbols = config.RS_PARITY_SYMBOLS

    num_data_symbols = len(received_symbols) - num_parity_symbols

    if num_parity_symbols == 0:
        return list(received_symbols)

    syndromes = _compute_syndromes(received_symbols, num_parity_symbols)

    if all(s == 0 for s in syndromes):
        return list(received_symbols[:num_data_symbols])

    error_locator_polynomial = _berlekamp_massey(syndromes)
    error_positions = _chien_search(error_locator_polynomial, len(received_symbols))

    if len(error_positions) == 0:
        if not silent:
            log_warning("RS: syndromes non-zero but no error positions found")
        return None

    correction_capacity = num_parity_symbols // 2
    if len(error_positions) > correction_capacity:
        if not silent:
            log_warning(f"RS: too many errors ({len(error_positions)})")
        return None

    error_magnitudes = _forney_algorithm(syndromes, error_locator_polynomial, error_positions)

    corrected_symbols = list(received_symbols)
    for position, magnitude in zip(error_positions, error_magnitudes):
        corrected_symbols[position] = gf_add(corrected_symbols[position], magnitude)

    verification_syndromes = _compute_syndromes(corrected_symbols, num_parity_symbols)
    if not all(s == 0 for s in verification_syndromes):
        if not silent:
            log_warning("RS: correction produced non-zero syndromes")
        return None

    return list(corrected_symbols[:num_data_symbols])


# ============================================================================
# PART C: POLYNOMIAL OPERATIONS
# ============================================================================

def evaluate_polynomial(poly_coefficients: list, x_value: int) -> int:
    """Evaluate P(x_value) using Horner's method over GF(2^16)."""
    if not poly_coefficients:
        return 0

    accumulated_result = poly_coefficients[-1]

    for coefficient in reversed(poly_coefficients[:-1]):
        accumulated_result = gf_add(
            gf_multiply(accumulated_result, x_value),
            coefficient,
        )

    return accumulated_result


def _build_lagrange_basis_polynomial(all_x_values: list, basis_index: int) -> list:
    """Build the j-th Lagrange basis polynomial L_j(x)."""
    num_points = len(all_x_values)
    x_j = all_x_values[basis_index]

    current_polynomial = [1]
    denominator_product = 1

    for factor_index in range(num_points):
        if factor_index == basis_index:
            continue

        x_k = all_x_values[factor_index]

        extended_polynomial = [0] * (len(current_polynomial) + 1)
        for coeff_pos, coeff_val in enumerate(current_polynomial):
            extended_polynomial[coeff_pos + 1] = gf_add(
                extended_polynomial[coeff_pos + 1], coeff_val
            )
            extended_polynomial[coeff_pos] = gf_add(
                extended_polynomial[coeff_pos],
                gf_multiply(x_k, coeff_val),
            )

        current_polynomial = extended_polynomial
        denominator_product = gf_multiply(denominator_product, gf_subtract(x_j, x_k))

    denominator_inverse = gf_inverse(denominator_product) if denominator_product != 0 else None
    if denominator_inverse is None:
        return [0] * num_points

    scaled_coefficients = [
        gf_multiply(coeff, denominator_inverse) for coeff in current_polynomial
    ]

    return scaled_coefficients


def lagrange_interpolate_coefficients(candidate_points: list, polynomial_degree: int):
    """Reconstruct polynomial coefficients from points via Lagrange interpolation."""
    num_required_points = polynomial_degree + 1

    if len(candidate_points) != num_required_points:
        log_warning(
            f"Lagrange interpolation needs exactly {num_required_points} points, "
            f"got {len(candidate_points)}"
        )
        return None

    x_values = [point[0] for point in candidate_points]
    y_values = [point[1] for point in candidate_points]

    if len(set(x_values)) != len(x_values):
        return None

    result_coefficients = [0] * num_required_points

    for basis_index in range(num_required_points):
        basis_polynomial_coefficients = _build_lagrange_basis_polynomial(x_values, basis_index)

        scaled_basis = [
            gf_multiply(y_values[basis_index], coeff)
            for coeff in basis_polynomial_coefficients
        ]

        for coeff_idx in range(num_required_points):
            result_coefficients[coeff_idx] = gf_add(
                result_coefficients[coeff_idx],
                scaled_basis[coeff_idx],
            )

    return result_coefficients
