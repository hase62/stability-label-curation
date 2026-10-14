"""DTU 2016 byte acquisition and structural audit; never scientific row labeling."""

from collections import Counter, defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import ssl
import stat
from typing import Any
from urllib.parse import urlsplit
from urllib.request import HTTPSHandler, Request, HTTPRedirectHandler, build_opener

from .data_sources import SourceMetadata, load_manifest
from .paths import PROJECT_NAME, StoragePaths, resolve_paths

SOURCE_ID = "netmhcstabpan_2016"
CHUNK_SIZE = 1024 * 1024
CANONICAL_AMINO_ACIDS = frozenset("ACDEFGHIKLMNPQRSTVWY")
ALLELE_PATTERN = re.compile(r"HLA-([ABC])\*[0-9]{2,3}:[0-9]{2,3}(?::[0-9]{2,3}){0,2}[NLSCAQ]?")
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


@contextmanager
def _directory(path: Path, *, create: bool = False) -> Iterator[int]:
    """No-follow traversal, including ancestors, on macOS/Linux."""
    descriptor = os.open(path.anchor, DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, DIR_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def _read_file(path: str | Path) -> Iterator[io.BufferedReader]:
    target = Path(os.path.abspath(Path(path).expanduser()))
    with _directory(target.parent) as descriptor:
        with os.fdopen(os.open(target.name, FILE_FLAGS, dir_fd=descriptor), "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("Input must be a regular file")
            yield stream


def _identity(stream: io.BufferedReader) -> tuple[int, ...]:
    value = os.fstat(stream.fileno())
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


def _hash_stream(stream: io.BufferedReader) -> tuple[int, str]:
    before = _identity(stream)
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(CHUNK_SIZE):
        digest.update(chunk)
        size += len(chunk)
    if before != _identity(stream) or size != before[2]:
        raise ValueError("Input changed while hashing")
    return size, digest.hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash exact bytes with bounded memory and no writes/network."""
    with _read_file(path) as stream:
        return _hash_stream(stream)[1]


@dataclass(frozen=True)
class Record:
    source_line_number: int
    raw_line: str
    hla: str
    peptide: str
    half_life_text: str
    half_life: Decimal | None
    numeric_issue: str | None


def parse_record(raw_line: str, line_number: int) -> Record:
    """Preserve all three original fields; flag invalid numbers without relabeling."""
    fields = raw_line.split()
    if len(fields) != 3:
        raise ValueError("expected three source columns")
    hla, peptide, text = fields
    issue = None
    value = None
    # Decimal itself accepts underscores and Unicode digits; require source numeric syntax.
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", text):
        try:
            candidate = Decimal(text)
            issue = "non_finite" if not candidate.is_finite() else "non_numeric"
        except InvalidOperation:
            issue = "missing" if text.lower() in {"na", "n/a", "null", ".", "-"} else "non_numeric"
    else:
        try:
            value = Decimal(text)
        except InvalidOperation:
            issue = "non_numeric"
    return Record(line_number, raw_line, hla, peptide, text, value, issue)


def iter_records(path: str | Path) -> Iterator[Record]:
    """Read-only strict iterator; malformed rows raise. Inventory flags them instead."""
    with _read_file(path) as stream:
        with io.TextIOWrapper(stream, encoding="utf-8", errors="surrogateescape", newline="") as text:
            for number, line in enumerate(text, 1):
                if not line.strip() or (number == 1 and line.split() == ["HLA", "Pep", "Thalf"]):
                    continue
                yield parse_record(line, number)


def classify_locus(hla: str) -> str:
    match = ALLELE_PATTERN.fullmatch(hla)
    return match[1] if match else "other"


def inventory(path: str | Path, *, source: SourceMetadata | None = None) -> dict[str, Any]:
    """Deterministic structural evidence; no mutation, network, or biological inference."""
    storage_source = load_manifest().get(SOURCE_ID) if source is None else source
    alleles: Counter[str] = Counter()
    lengths: Counter[int] = Counter()
    loci = Counter({"A": 0, "B": 0, "C": 0, "other": 0})
    keys: dict[tuple[str, str], list[Record]] = defaultdict(list)
    exact: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    raw_lines: dict[str, list[int]] = defaultdict(list)
    peptides: dict[str, set[str]] = defaultdict(set)
    unexpected: dict[str, list[int]] = defaultdict(list)
    characters: dict[str, list[int]] = defaultdict(list)
    malformed = []
    numeric = Counter({"zero": 0, "positive": 0, "negative": 0,
                       "missing": 0, "non_numeric": 0, "non_finite": 0})
    minimum = maximum = None
    total = blanks = parsed = 0
    header_raw = None
    header_matches = False
    with _read_file(path) as stream:
        identity = _identity(stream)
        size, checksum = _hash_stream(stream)
        stream.seek(0)
        with io.TextIOWrapper(stream, encoding="utf-8", errors="surrogateescape", newline="") as text:
            for number, line in enumerate(text, 1):
                total = number
                if number == 1:
                    header_raw = line.rstrip("\r\n")
                    header_matches = line.split() == list(storage_source.columns)
                    if header_matches:
                        continue
                if not line.strip():
                    blanks += 1
                    continue
                try:
                    row = parse_record(line, number)
                except ValueError as error:
                    malformed.append({"line": number, "reason": str(error)})
                    if len(line.split()) == 2:
                        numeric["missing"] += 1
                    continue
                parsed += 1
                alleles[row.hla] += 1
                lengths[len(row.peptide)] += 1
                loci[classify_locus(row.hla)] += 1
                keys[row.hla, row.peptide].append(row)
                exact[row.hla, row.peptide, row.half_life_text].append(number)
                raw_lines[line.rstrip("\r\n")].append(number)
                peptides[row.peptide].add(row.hla)
                if classify_locus(row.hla) == "other":
                    unexpected[row.hla].append(number)
                for character in sorted(set(row.peptide) - CANONICAL_AMINO_ACIDS):
                    characters[character].append(number)
                if row.numeric_issue:
                    numeric[row.numeric_issue] += 1
                    malformed.append({"line": number, "reason": row.numeric_issue})
                else:
                    value = row.half_life
                    assert value is not None
                    numeric["zero" if value == 0 else "positive" if value > 0 else "negative"] += 1
                    minimum = value if minimum is None else min(minimum, value)
                    maximum = value if maximum is None else max(maximum, value)
            if identity != _identity(stream):
                raise ValueError("Input changed during inventory")
    duplicate_keys = [{"hla": hla, "peptide": peptide,
                       "lines": [r.source_line_number for r in rows]}
                      for (hla, peptide), rows in sorted(keys.items()) if len(rows) > 1]
    conflicts = [{"hla": hla, "peptide": peptide,
                  "lines": [r.source_line_number for r in rows],
                  "half_life_texts": [r.half_life_text for r in rows]}
                 for (hla, peptide), rows in sorted(keys.items())
                 if len({r.half_life for r in rows if r.half_life is not None}) > 1]
    duplicate_records = [{"hla": hla, "peptide": peptide, "half_life_text": half,
                          "lines": lines}
                         for (hla, peptide, half), lines in sorted(exact.items()) if len(lines) > 1]
    repeated_peptides = [{"peptide": peptide, "alleles": sorted(hla)}
                         for peptide, hla in sorted(peptides.items()) if len(hla) > 1]
    expected = {"basis": storage_source.count_basis,
                "observations": storage_source.expected_record_count,
                "alleles": storage_source.expected_allele_count}
    checks = {"observations_match": parsed == expected["observations"],
              "alleles_match": len(alleles) == expected["alleles"]}
    status = "structural_checks_passed" if (header_matches and not malformed
             and not unexpected and not characters and not numeric["negative"]
             and not duplicate_keys and all(checks.values())) else "structural_anomalies_flagged"
    return {"source_id": storage_source.source_id, "raw_path": str(Path(path).expanduser().absolute()),
            "raw_byte_size": size, "sha256": checksum, "total_lines": total,
            "header": {"raw_text": header_raw, "expected": list(storage_source.columns), "matches": header_matches},
            "parsed_observation_count": parsed, "blank_line_count": blanks,
            "malformed_line_count": len(malformed), "malformed_lines": malformed,
            "distinct_allele_count": len(alleles), "counts_by_allele": dict(sorted(alleles.items())),
            "counts_by_locus": dict(loci),
            "counts_by_peptide_length": {str(k): v for k, v in sorted(lengths.items())},
            "nine_mers": {"count": lengths[9], "fraction": lengths[9] / parsed if parsed else None},
            "half_life": {**numeric, "missing_or_non_numeric": numeric["missing"] + numeric["non_numeric"],
                          "minimum": str(minimum) if minimum is not None else None,
                          "maximum": str(maximum) if maximum is not None else None, "unit": storage_source.measurement_unit},
            "duplicate_key_count": len(duplicate_keys), "duplicate_keys": duplicate_keys,
            "exact_duplicate_record_groups": len(duplicate_records),
            "exact_duplicate_record_excess": sum(len(r["lines"]) - 1 for r in duplicate_records),
            "exact_duplicate_records": duplicate_records,
            "identical_raw_line_groups": sum(len(lines) > 1 for lines in raw_lines.values()),
            "conflicting_repeat_key_count": len(conflicts), "conflicting_repeats": conflicts,
            "cross_allele_peptide_count": len(repeated_peptides), "cross_allele_peptides": repeated_peptides,
            "unexpected_alleles": dict(sorted(unexpected.items())),
            "noncanonical_peptide_characters": dict(sorted(characters.items())),
            "published_expectations": expected, "expectation_checks": checks,
            "validation_status": status,
            "scientific_provenance": "Dataset-level publication evidence only; row-level measurement status unresolved. Zero and positive values do not establish experimental/synthetic origin. Defer to Task 1.2."}


def json_report(document: dict[str, Any]) -> str:
    return json.dumps(document, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n"


def _target(source: SourceMetadata, paths: StoragePaths) -> Path:
    paths.validate()
    root = paths.data_root / PROJECT_NAME
    if root != paths.project_data_dir or root.resolve() != root:
        raise ValueError("Project data directory must not be a symlink")
    relative = source.target_relative_path
    if not relative or any(p in {"", ".", ".."} for p in relative.split("/")) or "\\" in relative or ":" in relative:
        raise ValueError("Unsafe source target")
    if PurePosixPath(relative).is_absolute() or PurePosixPath(relative).name != source.artifact_name:
        raise ValueError("Unsafe source target or filename")
    return root / relative


def _official_https(url: str) -> None:
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != "services.healthtech.dtu.dk"
            or parts.port not in {None, 443} or parts.username or parts.password
            or parts.fragment or any(c.isspace() for c in url)):
        raise ValueError("Only credential-free official DTU HTTPS URLs are permitted")


class _OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> Request | None:
        _official_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(*, paths: StoragePaths | None = None, timeout: float = 30) -> dict[str, Any]:
    """Only network entry point. Stream TLS bytes; publish via atomic nonreplacing link."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be positive and finite")
    storage = resolve_paths() if paths is None else paths
    source = load_manifest(paths=storage).get(SOURCE_ID)
    if not source.download_url:
        raise ValueError("Registry has no verified download URL")
    _official_https(source.download_url)
    target = _target(source, storage)
    receipt: dict[str, Any] = {"source_id": source.source_id, "official_source_url": source.download_url,
        "original_filename": source.artifact_name, "raw_path": str(target),
        "final_resolved_url": None, "retrieved_at_utc": None, "http_status": None,
        "server_metadata": {"content_length": None, "etag": None, "last_modified": None},
        "publisher_checksum": {"sha256": source.expected_sha256,
                               "status": "registry_reference" if source.expected_sha256 else "not_available"},
        "limitations": ["Local SHA256 identifies bytes, not scientific row validity.",
                        "HTTP metadata is server-reported, not independently verified.",
                        "No row-level experimental/synthetic assignment; Task 1.2 required."]}
    with _directory(target.parent, create=True) as parent:
        try:
            metadata = os.stat(target.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            metadata = None
        if metadata is not None:
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("Existing artifact must be a regular non-symlink file")
            with os.fdopen(os.open(target.name, FILE_FLAGS, dir_fd=parent), "rb") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise ValueError("Existing artifact must remain a regular file")
                size, checksum = _hash_stream(stream)
            receipt["acquisition"] = "existing_artifact_reused"
            receipt["limitations"].append("Existing bytes were not fetched or compared with current DTU bytes; original HTTP/retrieval metadata unavailable.")
        else:
            partial = f".{target.name}.{secrets.token_hex(12)}.partial"
            descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                with os.fdopen(descriptor, "wb") as output:
                    opener = build_opener(_OfficialRedirects(), HTTPSHandler(context=ssl.create_default_context()))
                    request = Request(source.download_url, headers={"Accept-Encoding": "identity"})
                    with opener.open(request, timeout=timeout) as response:
                        final_url = response.geturl()
                        _official_https(final_url)
                        if response.status != 200:
                            raise ValueError(f"Expected complete HTTP 200 response; received {response.status}")
                        encoding = response.headers.get("Content-Encoding", "identity")
                        if encoding.lower() != "identity":
                            raise ValueError("Unexpected content encoding; refusing byte transformation")
                        content_length = response.headers.get("Content-Length")
                        if content_length is not None and not re.fullmatch(r"[0-9]+", content_length):
                            raise ValueError("Invalid server Content-Length")
                        size = 0
                        digest = hashlib.sha256()
                        while chunk := response.read(CHUNK_SIZE):
                            output.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)
                        checksum = digest.hexdigest()
                        if content_length is not None and int(content_length) != size:
                            raise ValueError("Downloaded byte size differs from server Content-Length")
                        if source.expected_sha256 and checksum != source.expected_sha256.lower():
                            raise ValueError("Publisher checksum mismatch")
                        receipt.update(final_resolved_url=final_url,
                            retrieved_at_utc=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                            http_status=response.status,
                            server_metadata={"content_length": content_length,
                                             "etag": response.headers.get("ETag"),
                                             "last_modified": response.headers.get("Last-Modified")})
                    output.flush()
                    os.fsync(output.fileno())
                # Unlike replace/rename, link cannot overwrite a concurrent existing file.
                os.link(partial, target.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                os.fsync(parent)
                receipt["acquisition"] = "downloaded"
            finally:
                os.unlink(partial, dir_fd=parent)
    matches = source.expected_sha256 is None or checksum == source.expected_sha256.lower()
    receipt.update(local_file_size=size, local_sha256=checksum,
                   local_checksum_status="verified_over_exact_local_bytes",
                   validation_status="byte_identity_verified" if matches else "publisher_checksum_mismatch")
    if source.expected_sha256:
        receipt["publisher_checksum"]["status"] = "matches_registry_reference" if matches else "mismatch"
    return receipt


def write_report(path: str | Path, document: dict[str, Any], *, paths: StoragePaths | None = None) -> None:
    """Explicit non-overwriting report publication beneath project runs only."""
    write_text_report(path, json_report(document), paths=paths)


def write_text_report(path: str | Path, text: str, *, paths: StoragePaths | None = None) -> None:
    """Publish explicit UTF-8 report text with the existing no-overwrite safeguards."""
    storage = resolve_paths() if paths is None else paths
    storage.validate()
    root = storage.runs_root / PROJECT_NAME
    target = Path(path).expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    if (".." in target.parts or root != storage.project_runs_dir or root.resolve() != root
            or not target.is_relative_to(root) or target == root):
        raise ValueError("Report must be beneath project runs without traversal or symlinks")
    with _directory(target.parent) as parent:
        partial = f".{target.name}.{secrets.token_hex(12)}.partial"
        descriptor = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(text)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(partial, target.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
            os.fsync(parent)
        finally:
            os.unlink(partial, dir_fd=parent)
