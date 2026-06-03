"""
SimHash determinism + behavior tests.

Run from backend/:  python -m pytest tests/test_simhash.py
or standalone:      python tests/test_simhash.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from app.services.simhash_service import (
    compute_simhash,
    simhash_hex,
    hamming_distance,
    SIMHASH_BYTES,
    _projection_matrix,
)


def _rand_embedding(seed: int, dim: int = 1536) -> list[float]:
    return list(np.random.default_rng(seed).standard_normal(dim))


def test_length_is_32_bytes():
    h = compute_simhash(_rand_embedding(1))
    assert len(h) == SIMHASH_BYTES == 32
    assert len(simhash_hex(_rand_embedding(1))) == 64


def test_determinism_same_input_same_hash():
    emb = _rand_embedding(7)
    assert compute_simhash(emb) == compute_simhash(emb)


def test_cross_node_determinism():
    """Two independently-built projection matrices (as on two nodes) must match."""
    _projection_matrix.cache_clear()
    m1 = _projection_matrix(1536, 256, 1337)
    _projection_matrix.cache_clear()
    m2 = _projection_matrix(1536, 256, 1337)
    assert np.array_equal(m1, m2)


def test_identical_vectors_zero_distance():
    emb = _rand_embedding(3)
    assert hamming_distance(compute_simhash(emb), compute_simhash(emb)) == 0


def test_similar_closer_than_random():
    """A small perturbation should yield a smaller Hamming distance than a random vector."""
    base = np.array(_rand_embedding(11))
    near = base + 0.01 * np.random.default_rng(99).standard_normal(base.size)
    far = np.array(_rand_embedding(22))

    h_base = compute_simhash(list(base))
    d_near = hamming_distance(h_base, compute_simhash(list(near)))
    d_far = hamming_distance(h_base, compute_simhash(list(far)))
    assert d_near < d_far


def test_orthogonal_ish_distance_near_half():
    """Two random 1536-d vectors are ~orthogonal -> Hamming distance ~128/256."""
    dists = []
    for s in range(20):
        a = compute_simhash(_rand_embedding(1000 + s))
        b = compute_simhash(_rand_embedding(2000 + s))
        dists.append(hamming_distance(a, b))
    mean = sum(dists) / len(dists)
    assert 96 < mean < 160, f"mean Hamming {mean} not near 128"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("\nAll SimHash tests passed.")
