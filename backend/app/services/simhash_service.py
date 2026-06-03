"""
Deterministic SimHash / random-projection LSH.

This is the bridge between the off-chain embedding world and the on-chain search.
An embedding (any dimension) is projected onto a fixed set of random hyperplanes;
the sign of each projection is one bit. 256 bits -> 32 bytes -> stored on-chain as
`BytesN<32>` and compared with Hamming distance inside the Soroban contract.

CRITICAL — determinism: every node (publisher and searcher) MUST produce the same
hash for the same embedding, or on-chain Hamming distances are meaningless. We do
NOT rely on Faiss's internal RNG (not reproducible across versions/platforms).
Instead we generate the projection matrix from a fixed seed with NumPy's PCG64
generator, which is deterministic across platforms and versions. The seed and bit
count are part of the protocol: changing either invalidates all existing hashes.

The byte/bit packing order is irrelevant to correctness as long as it is identical
on both sides — the contract only XORs bytes and counts bits, which is order-agnostic.
"""

import numpy as np
from functools import lru_cache

from app.core.config import get_settings

settings = get_settings()

SIMHASH_BITS = 256
SIMHASH_BYTES = SIMHASH_BITS // 8  # 32


@lru_cache(maxsize=4)
def _projection_matrix(dim: int, bits: int, seed: int) -> np.ndarray:
    """Fixed (bits x dim) Gaussian random-projection matrix. Deterministic per seed."""
    rng = np.random.default_rng(seed)
    return rng.standard_normal((bits, dim)).astype(np.float64)


def compute_simhash(embedding: list[float]) -> bytes:
    """Return the 32-byte SimHash of an embedding vector."""
    vec = np.asarray(embedding, dtype=np.float64)
    if vec.ndim != 1 or vec.size == 0:
        raise ValueError("embedding must be a non-empty 1-D vector")

    matrix = _projection_matrix(vec.shape[0], SIMHASH_BITS, settings.simhash_seed)
    projections = matrix @ vec  # shape: (SIMHASH_BITS,)
    bit_array = projections >= 0.0  # bool per hyperplane
    packed = np.packbits(bit_array)  # (32,) uint8, MSB-first within each byte
    return packed.tobytes()


def simhash_hex(embedding: list[float]) -> str:
    """SimHash as a 64-char hex string (what the contract call expects as bytes)."""
    return compute_simhash(embedding).hex()


def hamming_distance(a: bytes, b: bytes) -> int:
    """Byte-wise Hamming distance — mirrors the on-chain computation exactly."""
    if len(a) != len(b):
        raise ValueError("hash length mismatch")
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))
