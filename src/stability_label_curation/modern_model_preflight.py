"""Label-blind identity, input and score contracts for Task 2.39.

No predictor, outcome loader, metric implementation or filesystem writes at import.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from .sequence_hamming import AMINO_ACIDS, NearestNineIndex, valid_ninemer

IDENTITY_FIELDS = frozenset({
    "source_id", "peptide", "hla", "study", "study_DOI", "patient", "sample",
    "patient_peptide_component", "study_peptide_component", "source_row_index",
    "source_line_number", "source_row_sha256", "original_observation_id",
})
# Schema of the already outcome-free Task 2.32 artifact; reject any extra columns.
INPUT_FIELDS = IDENTITY_FIELDS | frozenset({
    "HLA_association", "assay", "dataset", "minimum_fitting_selection_distance",
    "publication_DOI", "raw_hla", "raw_peptide",
})
SMOKE_PEPTIDES = ("GILGFVFTL", "NLVPMVATV")
SMOKE_HLAS = ("HLA-A*02:01", "HLA-B*07:02")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def object_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, separators=(",", ":"),
                                    ensure_ascii=False).encode()).hexdigest()


def verify_digest(path: Path, expected: str) -> None:
    if digest(path) != expected:
        raise ValueError(f"Checksum mismatch: {path.name}")


def verify_git_tree(entries: Sequence[Mapping], expected_root: str) -> None:
    """Rebuild Git tree objects; API root `sha` may echo a commit query.

    This checks actual entry bytes against the commit's tree, without fetching
    any additional file contents (including downstream outcome/prediction files).
    """
    directories: dict[str, list] = defaultdict(list)
    expected = {"": expected_root}
    for row in entries:
        path = row['path']
        parent, _, name = path.rpartition('/')
        directories[parent].append((name, row['mode'].lstrip('0'), row['sha'], row['type']))
        if row['type'] == 'tree':
            expected[path] = row['sha']
            directories.setdefault(path, [])
    for directory, children in directories.items():
        children.sort(key=lambda r: (r[0] + ('/' if r[3] == 'tree' else '')).encode())
        content = b''.join(mode.encode() + b' ' + name.encode() + b'\0' + bytes.fromhex(sha)
                           for name, mode, sha, _ in children)
        actual = hashlib.sha1(b'tree ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        if actual != expected[directory]:
            raise ValueError('Pinned Git tree content mismatch: ' + directory)


def normalize_hla(value: str) -> str:
    """Accept exact two-field human A/B/C only; never resolve serotypes/aliases."""
    # A five/six-digit compact string is ambiguous (e.g. 12:345 vs 123:45),
    # and may actually be a three-field allele. Only four-digit compact names
    # are accepted; explicitly colon-delimited fields may each have 2/3 digits.
    pattern = (r"(?:HLA-)?([ABC])\*?(\d{2,3}):(\d{2,3})" if ':' in value
               else r"(?:HLA-)?([ABC])\*?(\d{2})(\d{2})")
    match = re.fullmatch(pattern, value.strip())
    if not match:
        raise ValueError(f"Ambiguous or unsupported allele designation: {value!r}")
    locus, first, second = match.groups()
    return f"HLA-{locus}*{first}:{second}"


def mix_allele(value: str) -> str:
    return normalize_hla(value).removeprefix("HLA-").replace("*", "").replace(":", "")


def load_identities(path: Path, expected_hash: str, expected_rows: int) -> list[dict]:
    verify_digest(path, expected_hash)
    records = []
    seen = set()
    with path.open() as stream:
        for line in stream:
            raw = json.loads(line)
            if set(raw) - INPUT_FIELDS:
                raise ValueError("Non-allowlisted columns: schema rejected without value access")
            record = {k: raw[k] for k in sorted(IDENTITY_FIELDS) if k in raw}
            if record["source_id"] in seen:
                raise ValueError("Duplicate source row key")
            seen.add(record["source_id"])
            if normalize_hla(record["hla"]) != record["hla"]:
                raise ValueError("Frozen HLA identity changed by normalization")
            if not valid_ninemer(record["peptide"]):
                raise ValueError("Unexpected frozen peptide identity")
            record["peptide_length"] = len(record["peptide"])
            records.append(record)
    if len(records) != expected_rows:
        raise ValueError("Frozen row count mismatch")
    return records


def read_identity_csv(path: Path, stage: str, split: str) -> list[dict]:
    """Source numerical labels are never looked up, converted or summarized."""
    records = []
    with path.open(newline="") as stream:
        reader = csv.DictReader(stream)
        for row_number, row in enumerate(reader, 2):
            peptide = row["peptide_sequence"].strip().upper()
            allele = normalize_hla(row["allele"])
            records.append({"stage": stage, "split": split, "source_line": row_number,
                            "peptide": peptide, "hla": allele,
                            "mhc_sha256": hashlib.sha256(row["mhc_sequence"].encode()).hexdigest(),
                            "pmid": row.get("pmid", ""), "ref_iri": row.get("ref_iri", "")})
    return records


def fasta_records(path: Path) -> Iterable[tuple[str, str, str]]:
    header, pieces = None, []
    with path.open() as stream:
        for line in stream:
            if line.startswith(">"):
                if header is not None:
                    accession, allele, *_ = header.split()
                    yield accession, allele, "".join(pieces)
                header, pieces = line[1:].strip(), []
            elif header is not None:
                pieces.append(line.strip())
    if header is not None:
        accession, allele, *_ = header.split()
        yield accession, allele, "".join(pieces)


def full_hla_reference(alleles: Sequence[str], consensus: Mapping[str, str],
                       fasta: Path) -> dict[str, dict]:
    """Authenticate the model's explicit two-field reference against IPD proteins.

    Choose an exact sequence match, never a closest allele or invented extension.
    Completeness contract includes signal, extracellular, TM and cytoplasmic chain;
    181-residue fragments are rejected, and sequences are never length-normalized.
    Three/four-field synonymous aliases are recorded, not inferred donor genotypes.
    """
    candidates: dict[str, list] = defaultdict(list)
    for accession, designation, sequence in fasta_records(fasta):
        key = "HLA-" + ":".join(designation.split(":")[:2])
        if key in alleles and consensus.get(key) == sequence:
            candidates[key].append((designation, accession))
    result = {}
    for allele in alleles:
        sequence = consensus.get(allele, "")
        matches = sorted(candidates[allele])
        valid = bool(matches) and len(sequence) >= 350 and all(a in AMINO_ACIDS for a in sequence)
        result[allele] = {"eligible": valid,
            "reason": None if valid else "unresolved_full_length_reference",
            "sequence": sequence if valid else None, "length": len(sequence),
            "sha256": hashlib.sha256(sequence.encode()).hexdigest() if valid else None,
            "ipd_designation": matches[0][0] if matches else None,
            "ipd_accession": matches[0][1] if matches else None,
            "identical_sequence_accessions": len(matches),
            "mapping": "exact two-field model reference, exact IPD protein match; no nearest allele"}
    return result


def parse_mix(text: str, peptides: Sequence[str], designated_hla: str) -> list[dict]:
    """Read exact allele columns; retain repeated peptides and original order."""
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter="\t")
    allele = mix_allele(designated_hla)
    score_column, rank_column = f"Score_{allele}", f"%Rank_{allele}"
    if not {"Peptide", score_column, rank_column}.issubset(reader.fieldnames or []):
        raise ValueError("Missing designated-HLA columns; bestAllele fallback is prohibited")
    rows = list(reader)
    if len(rows) != len(peptides):
        raise ValueError("Missing or extra MixMHCpred output rows")
    result = []
    for peptide, row in zip(peptides, rows, strict=True):
        if row["Peptide"] != peptide:
            raise ValueError("MixMHCpred source row alignment mismatch")
        score, rank = float(row[score_column]), float(row[rank_column])
        if not math.isfinite(score) or not math.isfinite(rank) or not 0 <= rank <= 100:
            raise ValueError("Invalid native score/rank")
        result.append({"peptide": peptide, "hla": normalize_hla(designated_hla),
                       "native_score": score, "published_percentile_rank": rank,
                       "selected_column": score_column})
    return result


def align_scores(keys: Sequence[str], rows: Sequence[Mapping]) -> None:
    if len(keys) != len(set(keys)) or [r["source_id"] for r in rows] != list(keys):
        raise ValueError("Duplicate, missing or reordered score identities")
    if any(not math.isfinite(float(row["score"])) for row in rows):
        raise ValueError("Nonfinite prediction")


def assay_contract(assay_types: Sequence[str], assay: str = "SPA",
                   temperature: float = 37.0) -> tuple[int, float]:
    if assay != "SPA" or temperature != 37.0 or list(assay_types) != [
            "SPA", "Purified_Fluor", "Cellular_Fluor", "Other"]:
        raise ValueError("Non-frozen assay/temperature vocabulary")
    return assay_types.index(assay), temperature


def hamming(left: str, right: str) -> int:
    if len(left) != len(right):
        raise ValueError("Hamming distance undefined for unequal lengths")
    return sum(a != b for a, b in zip(left, right, strict=True))


def audit_identities(candidates: Sequence[Mapping], reference: Sequence[Mapping]) -> list[dict]:
    """Candidate cohort is 9-mers; non-nine reference rows never get a distance."""
    pairs = {(r["peptide"], r["hla"]) for r in reference}
    peptides = {r["peptide"] for r in reference}
    index = NearestNineIndex(r["peptide"] for r in reference if valid_ninemer(r["peptide"]))
    per_hla = {a: NearestNineIndex(r["peptide"] for r in reference
                                 if r["hla"] == a and valid_ninemer(r["peptide"]))
               for a in {r["hla"] for r in candidates}}
    cache = {}
    result = []
    for row in candidates:
        peptide, allele = row["peptide"], row["hla"]
        if peptide not in cache:
            cache[peptide] = index.nearest(peptide)
        distance, witness = cache[peptide]
        same_distance, same_witness = per_hla[allele].nearest(peptide)
        result.append({"source_id": row["source_id"],
                       "exact_pair": (peptide, allele) in pairs,
                       "exact_peptide": peptide in peptides,
                       "min_hamming": distance, "witness": witness,
                       "same_hla_min_hamming": same_distance,
                       "same_hla_witness": same_witness})
    return result


def coverage(rows: Sequence[Mapping], sequences: Mapping, mix_support: Mapping) -> list[dict]:
    result = []
    for row in rows:
        canonical = all(a in AMINO_ACIDS for a in row["peptide"])
        mix = canonical and 8 <= len(row["peptide"]) <= 14 and mix_support[row["hla"]]["eligible"]
        spearmint = canonical and sequences[row["hla"]]["eligible"]
        reasons = []
        if not canonical:
            reasons.append("noncanonical_peptide")
        if not mix:
            reasons.append("mix_input_unsupported")
        if not spearmint:
            reasons.append("spearmint_full_hla_unresolved")
        result.append({"source_id": row["source_id"], "hla": row["hla"],
            "peptide_length": len(row["peptide"]), "mix_eligible": bool(mix),
            "spearmint_eligible": bool(spearmint), "common_eligible": bool(mix and spearmint),
            "reason_codes": reasons, "unknown_ancestry": True,
            "patient_peptide_component": row.get("patient_peptide_component")})
    return result


def within_hla_percentiles(scores: Sequence[float], alleles: Sequence[str]) -> list[float]:
    """Higher-is-better observation-weighted midrank (less + .5*equal)/N.

    Repeated biological observations retain their original multiplicity. Ties do
    not use labels, source order or artificial jitter; singleton rank is 0.5.
    """
    if len(scores) != len(alleles) or any(not math.isfinite(s) for s in scores):
        raise ValueError("Invalid aligned score inputs")
    groups: dict[str, list[int]] = defaultdict(list)
    for i, a in enumerate(alleles):
        groups[normalize_hla(a)].append(i)
    result = [0.0] * len(scores)
    for indices in groups.values():
        ordered = sorted(indices, key=lambda i: scores[i])
        left = 0
        while left < len(ordered):
            right = left + 1
            while right < len(ordered) and scores[ordered[right]] == scores[ordered[left]]:
                right += 1
            for i in ordered[left:right]:
                result[i] = (left + 0.5 * (right - left)) / len(ordered)
            left = right
    return result


def fixed_fusion(el: Sequence[float], stability: Sequence[float],
                 alleles: Sequence[str]) -> tuple[list[float], list[float], list[float]]:
    """Future contract only; Task 2.39 tests it on synthetic data, never cohorts."""
    a, b = within_hla_percentiles(el, alleles), within_hla_percentiles(stability, alleles)
    return a, b, [(x + y) * 0.5 for x, y in zip(a, b, strict=True)]
