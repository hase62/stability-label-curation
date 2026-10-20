"""Exact nearest canonical 9-mer search with bounded-size pigeonhole buckets.

No learned distance and no all-pairs matrix. Four disjoint blocks cover every
neighbor at distance <=3. A best witness <=4 is therefore exact after scanning
those buckets. If no such witness exists, a full one-query scan proves the
answer at larger distances. Returned witnesses always belong to the reference.
"""
from __future__ import annotations

from array import array
from collections.abc import Iterable

AMINO_ACIDS = 'ACDEFGHIKLMNPQRSTVWY'
ENCODING = {residue: index for index, residue in enumerate(AMINO_ACIDS)}
MISMATCH_MASK = sum(1 << (5 * position) for position in range(9))
BLOCKS = ((0, 1023), (10, 1023), (20, 1023), (30, 32767))


def valid_ninemer(sequence: str) -> bool:
    return len(sequence) == 9 and all(residue in ENCODING for residue in sequence)


def encode(sequence: str) -> int:
    if not valid_ninemer(sequence):
        raise ValueError('Hamming references and queries must be canonical exact 9-mers')
    return sum(ENCODING[residue] << (5 * i) for i, residue in enumerate(sequence))


def decode(code: int) -> str:
    return ''.join(AMINO_ACIDS[(code >> (5 * i)) & 31] for i in range(9))


def packed_distance(left: int, right: int) -> int:
    different = left ^ right
    return ((different | (different >> 1) | (different >> 2) |
             (different >> 3) | (different >> 4)) & MISMATCH_MASK).bit_count()


class NearestNineIndex:
    """Exact search, including distant/empty references; labels never enter it."""

    def __init__(self, sequences: Iterable[str]):
        self.codes = array('Q', (encode(s) for s in sorted(set(sequences))))
        self.exact = set(self.codes)
        self.buckets: list[dict[int, array]] = [{} for _ in BLOCKS]
        for code in self.codes:
            for table, (shift, mask) in zip(self.buckets, BLOCKS, strict=True):
                key = (code >> shift) & mask
                if key not in table:
                    table[key] = array('Q')
                table[key].append(code)
        self.queries = 0
        self.comparisons = 0
        self.full_scan_queries = 0

    def nearest(self, sequence: str) -> tuple[int | None, str | None]:
        query = encode(sequence)
        self.queries += 1
        if not self.codes:
            return None, None
        if query in self.exact:
            return 0, sequence
        best, witness = 10, None
        for table, (shift, mask) in zip(self.buckets, BLOCKS, strict=True):
            for code in table.get((query >> shift) & mask, ()):
                distance = packed_distance(query, code)
                self.comparisons += 1
                if distance < best:
                    best, witness = distance, code
        if best > 4:
            self.full_scan_queries += 1
            for code in self.codes:
                distance = packed_distance(query, code)
                self.comparisons += 1
                if distance < best:
                    best, witness = distance, code
        assert witness is not None
        return best, decode(witness)

    def evidence(self) -> dict:
        return {'reference_sequences': len(self.codes), 'queries': self.queries,
                'comparisons': self.comparisons, 'full_scan_queries': self.full_scan_queries,
                'algorithm': 'four disjoint 2/2/2/3-residue blocks; exact packed Hamming; distant-query full-scan fallback',
                'distances_are_exact_not_capped': True, 'all_pairs_matrix_constructed': False}
