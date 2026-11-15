# Code Review

Correctness/quality review done before publishing (separate from the organizational cleanup
noted in the main README). All 5 assignments compile cleanly with `g++ -std=c++17`.

## Assignment 1 — Student Directory (Hashing)
- Removed leftover dead/duplicated commented-out `HashDefs.h` blocks from `LinearProbing.cpp`,
  `QuadraticProbing.cpp`, `Chaining.cpp` (clutter only, no logic touched; re-verified compile after).
- **Hash function**: `converter()` sums character ASCII values (order-independent) — two emails
  that are anagrams of each other hash identically. Works for the test data given, but weak.
- **Quadratic probing**: `(base + i*i) % 199` with a prime table size only reaches ~half the
  table's slots as `i` ranges `0..198` (since `i^2 ≡ (p-i)^2 mod p`). A known property of naive
  quadratic probing — can report "full" at ~50% occupancy. Not fixed (would change graded logic).

## Assignment 2 — Payment Network Batch Routing
No issues found. Per-segment Dijkstra through the ordered checkpoints is the correct approach
(the problem allows passing through arbitrary intermediate sites between checkpoints). MinHeap
and the access-control BFS (tracking a "permission seen" bit) are both correctly implemented.

## Assignment 3 — Social Media System + Huffman Coding
- Fixed a leftover placeholder in a file header comment (`@file 2023CS10000_2.cpp` →
  `2025JCS3011_2.cpp`), cosmetic only.
- The problem statement says custom data structures are "encouraged instead of" STL containers;
  this submission uses `unordered_map`/`unordered_set`/`std::sort` throughout. Not incorrect, but
  worth knowing if this affected grading.
- `topPosts` tie-breaking for equal counts isn't specified by the problem and `std::sort` isn't
  stable, so tied results could appear in a different order on a different run/compiler.
- Huffman single-character edge case is handled correctly (explicit check, codes to "0").

## Assignment 4 — Fractional & 0/1 Knapsack
No issues found. Fractional knapsack: correct greedy-by-density with sensible tie-break (prefer
higher value) and a correctly implemented manual merge sort. 0/1 knapsack: correct DP + backtrack
to recover the selected items, with a sound special case for zero-weight/positive-value items.

## Assignment 5 — IP Address Analysis
No functional issues found. Backtracking reconstruction, octet-trie subnet grouping, and DSU
clustering are all correctly implemented, including edge cases (empty input, no valid IPs).
Minor: `ClusterUnion` and `TrieNode` hold raw owning pointers with a destructor but no copy
constructor/assignment operator (Rule-of-Three). Never actually copied in this program, so not a
live bug — just a latent risk if the class is reused elsewhere.
