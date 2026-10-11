"""Read-only source registry. Metadata validation is not scientific inclusion."""

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tomllib
from typing import Any, Literal
from urllib.parse import urlsplit

from .paths import StoragePaths, resolve_paths

SourceType = Literal['experimental_dataset', 'mixed_dataset', 'synthetic_dataset',
                     'prediction_dataset', 'model_reference', 'dataset_reference']
ResearchRole = Literal['primary_kinetic_candidate', 'historical_overlap_audit',
                       'secondary_thermal_candidate', 'downstream_immunogenicity',
                       'independent_evaluation_candidate', 'audit_only', 'model_comparison']
MeasurementType = Literal['kinetic_half_life', 'thermal_melting_temperature',
                          'immunogenicity', 'synthetic', 'prediction_only',
                          'mixed', 'not_applicable', 'unknown', 'not_yet_verified']
ProvenanceStatus = Literal['row_audit_required', 'unresolved_pending_audit',
                          'unknown', 'not_yet_verified', 'row_provenance_verified']
SpeciesScope = Literal['human_hla_i', 'mixed_species', 'mouse', 'rat',
                       'unknown', 'not_yet_verified']

SOURCE_TYPES = set(SourceType.__args__)
MEASUREMENTS = set(MeasurementType.__args__)
PROVENANCE = set(ProvenanceStatus.__args__)
SPECIES = set(SpeciesScope.__args__)
UNKNOWNS = {'unknown', 'not_yet_verified'}
# Each role constrains both the kind of source and its scientific measurement.
ROLE_COMPATIBILITY = {
    'primary_kinetic_candidate': ({'experimental_dataset'}, {'kinetic_half_life'}),
    'historical_overlap_audit': ({'experimental_dataset', 'mixed_dataset', 'dataset_reference', 'model_reference'},
                                 {'kinetic_half_life', 'mixed', 'not_applicable', 'unknown', 'not_yet_verified'}),
    'secondary_thermal_candidate': ({'experimental_dataset', 'mixed_dataset'}, {'thermal_melting_temperature'}),
    'downstream_immunogenicity': ({'experimental_dataset', 'mixed_dataset'}, {'immunogenicity'}),
    'independent_evaluation_candidate': ({'experimental_dataset', 'mixed_dataset', 'dataset_reference'}, {'immunogenicity'}),
    'audit_only': (SOURCE_TYPES, MEASUREMENTS),
    'model_comparison': ({'model_reference', 'prediction_dataset', 'dataset_reference', 'mixed_dataset'},
                         {'prediction_only', 'not_applicable', 'mixed', 'unknown', 'not_yet_verified'}),
}


class ManifestValidationError(ValueError):
    """Manifest content fails the documented schema contract."""


@dataclass(frozen=True)
class SourceMetadata:
    source_id: str
    title: str
    source_type: SourceType
    research_role: ResearchRole
    species_scope: SpeciesScope
    measurement_type: MeasurementType
    provenance_status: ProvenanceStatus
    landing_url: str
    notes: str
    publication_doi: str | None = None
    download_url: str | None = None
    target_relative_path: str | None = None
    expected_sha256: str | None = None
    license: str | None = None
    artifact_name: str | None = None
    published_version: str | None = None
    expected_record_count: int | None = None
    expected_allele_count: int | None = None
    count_basis: str | None = None
    measurement_unit: str | None = None
    assay_conditions: str | None = None
    columns: tuple[str, ...] = ()
    training_datasets: tuple[str, ...] = ()
    validation_datasets: tuple[str, ...] = ()
    evaluation_datasets: tuple[str, ...] = ()
    evidence_urls: tuple[str, ...] = ()
    verification_notes: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return JSON primitives, including lists rather than immutable tuples."""
        return {key: list(value) if isinstance(value, tuple) else value
                for key, value in asdict(self).items()}

    def target_path(self, paths: StoragePaths | None = None) -> Path | None:
        """Resolve an intended artifact beneath project data, with symlink checks."""
        if self.target_relative_path is None:
            return None
        storage = resolve_paths() if paths is None else paths
        storage.validate()
        root = storage.project_data_dir.resolve()
        target = (root / self.target_relative_path).resolve()
        if not target.is_relative_to(root) or target == root:
            raise ManifestValidationError(f'{self.source_id}: target_relative_path escapes project data storage')
        return target


@dataclass(frozen=True)
class SourceRegistry:
    schema_version: int
    sources: tuple[SourceMetadata, ...]

    def list_sources(self) -> tuple[SourceMetadata, ...]:
        return tuple(sorted(self.sources, key=lambda source: source.source_id))

    def get(self, source_id: str) -> SourceMetadata:
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise ManifestValidationError(f'Unknown source_id {source_id!r}; use sources list to see available IDs')

    def as_dict(self) -> dict[str, Any]:
        return {'schema_version': self.schema_version,
                'sources': [source.as_dict() for source in self.list_sources()]}


REQUIRED = {'source_id', 'title', 'source_type', 'research_role', 'species_scope',
            'measurement_type', 'provenance_status', 'landing_url', 'notes'}
FIELDS = set(SourceMetadata.__dataclass_fields__)
LIST_FIELDS = {'columns', 'training_datasets', 'validation_datasets', 'evaluation_datasets', 'evidence_urls'}
COUNT_FIELDS = {'expected_record_count', 'expected_allele_count'}


def _fail(context: str, message: str) -> None:
    raise ManifestValidationError(f'{context}: {message}')


def _url(value: str, context: str) -> None:
    try:
        parts = urlsplit(value)
        _ = parts.port  # Validate malformed port numbers as well.
        if (parts.scheme not in {'http', 'https'} or not parts.hostname
                or parts.username or parts.password or any(c.isspace() for c in value)):
            raise ValueError('expected an HTTP(S) URL without credentials or whitespace')
    except ValueError as error:
        _fail(context, f'invalid URL {value!r}: {error}')


def validate_manifest(document: Mapping[str, Any], *, paths: StoragePaths | None = None) -> SourceRegistry:
    """Validate schema v1 without fetching data or creating any directories."""
    if not isinstance(document, Mapping):
        _fail('manifest', 'expected a table')
    if set(document) != {'schema_version', 'sources'}:
        _fail('manifest', 'required keys are schema_version and sources; extra keys are unsupported')
    if type(document['schema_version']) is not int or document['schema_version'] != 1:
        _fail('schema_version', 'only integer version 1 is supported')
    rows = document['sources']
    if not isinstance(rows, list) or not rows:
        _fail('sources', 'expected a nonempty array of tables')
    sources = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        context = f'sources[{index}]'
        if not isinstance(row, dict):
            _fail(context, 'expected a source table')
        missing, extra = REQUIRED - set(row), set(row) - FIELDS
        if missing:
            _fail(context, f'missing required fields: {", ".join(sorted(missing))}')
        if extra:
            _fail(context, f'unsupported fields: {", ".join(sorted(extra))}')
        for key, value in row.items():
            if key in LIST_FIELDS:
                if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
                    _fail(context, f'{key} must be an array of nonempty strings')
            elif key in COUNT_FIELDS:
                if type(value) is not int or value <= 0:
                    _fail(context, f'{key} must be a positive integer published expectation')
            elif not isinstance(value, str) or not value.strip():
                _fail(context, f'{key} must be a nonempty string')
            elif value in UNKNOWNS and key not in {'species_scope', 'measurement_type', 'provenance_status',
                                                  'license', 'assay_conditions', 'published_version', 'measurement_unit'}:
                _fail(context, f'{key} does not permit unknown metadata; omit optional unverified fields')
        context += f' ({row["source_id"]})'
        if not re.fullmatch(r'[a-z][a-z0-9_]*', row['source_id']):
            _fail(context, 'source_id must be a stable lowercase identifier')
        if row['source_id'] in seen:
            _fail(context, 'duplicate source_id')
        seen.add(row['source_id'])
        for key, choices in [('source_type', SOURCE_TYPES), ('research_role', set(ROLE_COMPATIBILITY)),
                             ('species_scope', SPECIES), ('measurement_type', MEASUREMENTS), ('provenance_status', PROVENANCE)]:
            if row[key] not in choices:
                _fail(context, f'unsupported {key} {row[key]!r}; choose from {", ".join(sorted(choices))}')
        kinds, measurements = ROLE_COMPATIBILITY[row['research_role']]
        if row['source_type'] not in kinds or row['measurement_type'] not in measurements:
            _fail(context, 'incompatible research_role, source_type, and measurement_type')
        if row['research_role'] in {'primary_kinetic_candidate', 'secondary_thermal_candidate', 'downstream_immunogenicity', 'independent_evaluation_candidate'} and row['species_scope'] != 'human_hla_i':
            _fail(context, 'candidate research roles require human_hla_i scope')
        if row['source_type'] == 'synthetic_dataset' and row['measurement_type'] != 'synthetic':
            _fail(context, 'synthetic_dataset requires synthetic measurement_type')
        if row['source_type'] == 'prediction_dataset' and row['measurement_type'] != 'prediction_only':
            _fail(context, 'prediction_dataset requires prediction_only measurement_type')
        if row['source_type'] == 'experimental_dataset' and row['measurement_type'] not in {'kinetic_half_life', 'thermal_melting_temperature', 'immunogenicity'}:
            _fail(context, 'experimental_dataset requires an experimental measurement classification')
        if row['source_type'] == 'model_reference' and row['measurement_type'] not in {'not_applicable', 'prediction_only', 'mixed'}:
            _fail(context, 'model_reference cannot represent experimental measurements')
        for key in ('landing_url', 'download_url'):
            if key in row:
                _url(row[key], f'{context}.{key}')
        for url in row.get('evidence_urls', []):
            _url(url, f'{context}.evidence_urls')
        if 'publication_doi' in row and not re.fullmatch(r'10\.\d{4,9}/\S+', row['publication_doi']):
            _fail(context, 'publication_doi must be a DOI identifier beginning 10.')
        if 'expected_sha256' in row:
            if not re.fullmatch(r'[0-9a-fA-F]{64}', row['expected_sha256']):
                _fail(context, 'expected_sha256 must contain exactly 64 hexadecimal characters')
            if not {'artifact_name', 'target_relative_path', 'evidence_urls', 'verification_notes'} <= set(row):
                _fail(context, 'expected_sha256 requires artifact_name, target_relative_path, evidence_urls, and verification_notes')
        if 'download_url' in row and not {'artifact_name', 'target_relative_path', 'evidence_urls', 'verification_notes'} <= set(row):
            _fail(context, 'download_url requires identified artifact, target, and verification evidence')
        if ('download_url' in row or 'expected_sha256' in row) and not row.get('evidence_urls'):
            _fail(context, 'download_url and expected_sha256 require nonempty evidence_urls')
        if any(key in row for key in COUNT_FIELDS) and row.get('count_basis') != 'published_expectation':
            _fail(context, 'expected counts require count_basis = published_expectation')
        if 'count_basis' in row and row['count_basis'] != 'published_expectation':
            _fail(context, 'count_basis must be published_expectation')
        if 'target_relative_path' in row:
            raw = row['target_relative_path']
            posix, windows = PurePosixPath(raw), PureWindowsPath(raw)
            if (posix.is_absolute() or windows.is_absolute() or windows.drive or '\\' in raw
                    or '..' in posix.parts or ':' in raw or '\x00' in raw
                    or any(part in {'', '.'} for part in raw.split('/'))):
                _fail(context, 'target_relative_path must be a portable relative file path without .. or absolute components')
            if 'artifact_name' not in row or posix.name != row['artifact_name']:
                _fail(context, 'target_relative_path basename must match artifact_name')
        source = SourceMetadata(**{key: tuple(value) if key in LIST_FIELDS else value for key, value in row.items()})
        if source.target_relative_path is not None:
            source.target_path(paths)
        sources.append(source)
    return SourceRegistry(1, tuple(sorted(sources, key=lambda source: source.source_id)))


def load_manifest(manifest: str | Path | None = None, *, paths: StoragePaths | None = None) -> SourceRegistry:
    """Load the repository manifest or an explicit independent TOML manifest."""
    if manifest is None:
        storage = resolve_paths() if paths is None else paths
        manifest = storage.repository_root / 'configs' / 'data_sources.toml'
    path = Path(manifest)
    try:
        with path.open('rb') as handle:
            document = tomllib.load(handle)
        return validate_manifest(document, paths=paths)
    except (OSError, ValueError) as error:
        raise ManifestValidationError(f'{path}: {error}') from error
