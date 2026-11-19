"""Generate the stability teacher, native training files and cohorts from pinned releases."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
import gzip
from fractions import Fraction
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
import zipfile

from common import D, P, SEEDS, csvout, digest, put, read, sha
from main_study_controls import prepare as make_controls
from stability_label_curation import (
    bigmhc_el_multiepoch as el_split,
    bigmhc_independent_evaluation as neo,
    bigmhc_multiepoch as im_split,
    bigmhc_pilot_adapter as adapter,
    bigmhc_v4_audit as bigmhc,
    dtu2016_source_audit as dtu_audit,
    el_only_zero_shot_im as projection,
    hla_extended_epochs as native,
    netmhcstabpan_2016 as raw,
    observation_registry as registry,
    pseudolabel_pilot as pilot,
    stability_teacher as teacher,
    third_party_hard_split as improve,
)
from stability_label_curation.data_sources import load_manifest
from stability_label_curation.sequence_hamming import NearestNineIndex, valid_ninemer

INPUTS = D / "inputs"
EXPECTED = D / "config/expected.json"


def check(condition, message):
    if not condition:
        raise ValueError(message)


def inputs():
    return read(D / "preflight/raw_inputs.json")


def raw_path(role):
    spec = inputs()[role]
    path = Path(spec["path"])
    check(sha(path) == spec["sha256"], f"Raw source changed: {role}")
    return path


def checked_training_bytes(name):
    path = INPUTS / f"{name}.csv.gz"
    with gzip.open(path, "rb") as stream:
        observed = hashlib.file_digest(stream, "sha256").hexdigest()
    expected = read(EXPECTED)["decoded_training_sha256"][name]
    check(observed == expected, f"Decoded bytes for {name} differ from the audited experiment")


def teacher_rows(path):
    source = load_manifest(paths=P).get(raw.SOURCE_ID)
    rows = []
    archive_hash = sha(path)
    source_count = 0
    for record in raw.iter_records(path):
        source_count += 1
        category = dtu_audit.identifier_category(record.hla)
        if category not in {"ordinary_hla_a", "ordinary_hla_b"}:
            continue
        rows.append(registry.make_observation(
            source_id=raw.SOURCE_ID, sha256=archive_hash,
            locator={"kind": "text_line", "artifact": "netmhcstabpan_2016/Stability.txt",
                     "line_number": record.source_line_number},
            allele=record.hla, peptide=record.peptide, text=record.half_life_text,
            measurement_type="kinetic_half_life", unit="hours", context=registry.DTU_CONTEXT,
            provenance=registry._provenance(source, ["configs/netmhcstabpan_2016_evidence.json"],
                                             "dataset_level_experimental_kinetic_stability"),
            origin=dtu_audit.ROW_PROVENANCE, flags=[category],
            record_context={"original_source_line": record.raw_line},
        ))
    check(source_count == 28166 and len(rows) == 27031, "Unexpected DTU population")
    check(sum(registry.decimal_value(row.original_measurement_text) == 0 for row in rows) == 4711,
          "Unexpected reported zero count")
    return rows


def build_teacher():
    path = raw_path("dtu")
    archive_hash = sha(path)
    rows = teacher_rows(path)
    config = teacher.load_config(P.repository_root / "configs/stability_teacher_v0.json")
    partition = teacher.make_partition(rows, config)
    audit = teacher.verify_partition(rows, partition)
    check(audit["partition_counts"] == {"train": 21625, "validation": 5406}, "Teacher split population changed")
    partition_path = INPUTS / "teacher_partition.json"
    with partition_path.open("x", encoding="utf-8") as stream:
        stream.write(raw.json_report(partition))
    check(sha(partition_path) == read(EXPECTED)["teacher_split"]["partition_sha256"], "Teacher partition identity changed")
    projection.write_rows(INPUTS / "teacher_identities.jsonl", (
        {"observation_id": r.observation_id, "hla": r.original_allele, "peptide": r.original_peptide}
        for r in rows))
    model = teacher.fit(rows, partition, config, provenance={
        "source": "DTU Stability.txt", "raw_sha256": archive_hash,
        "partition_sha256": sha(partition_path), "registry_scope": "DTU ordinary HLA rows",
    })
    model_path = INPUTS / "teacher.json"
    put(model_path, model.document)
    trained = {a for a, fitted in model.document["alleles"].items() if fitted["status"] == "trained"}
    check(len(trained) == 67, "Unexpected Teacher fitted HLA count")
    membership = {r["observation_id"]: r["partition"] for r in partition["assignments"]}
    fitted_pairs = sorted({(row.original_peptide, row.original_allele) for row in rows
                           if membership[row.observation_id] == "train" and row.original_allele in trained})
    put(INPUTS / "teacher_fitted_pairs.json", fitted_pairs)
    put(D / "preflight/teacher_generated.json", {
        "status": "PASS", "source_sha256": archive_hash, "teacher_sha256": sha(model_path),
        "partition_sha256": sha(partition_path), "fitted_pairs_sha256": sha(INPUTS / "teacher_fitted_pairs.json"),
        "split": audit, "trained_hlas": len(trained), "validation": teacher.evaluate(model, rows, partition),
    })


def source_members(archive):
    allowed, _ = bigmhc.archive_inventory(archive)
    test_members = [entry for entry in archive.infolist()
                    if PurePosixPath(entry.filename).name == "im_test.csv"
                    and str(PurePosixPath(entry.filename).parent) in {".", "datasets"}]
    check(len(test_members) == 1, "Missing or ambiguous released im_test.csv")
    allowed["im_test.csv"] = test_members[0]
    return allowed


def allele_support(reference):
    with reference.open(encoding="utf-8-sig", newline="") as stream:
        summary, _, mapping = bigmhc._reference(enumerate(csv.reader(stream, strict=True), 1))
    check(summary["feature_count"] == 414 and not any(summary[key] for key in
          ("invalid_one_hot_rows", "duplicate_identifier_count", "sanitized_UID_collision_groups")),
          "Invalid BigMHC receptor encoding")
    return {name for name, matches in mapping.items() if len(matches) == 1}


def mapping_for(alleles):
    class ExactMapping:
        def get(self, value, default=None):
            allele = bigmhc.canonical_hla(value)
            return allele if allele in alleles else default
    return ExactMapping()


def stream_training_rows(source, member, context, reference, dev_index):
    header = next(source)[1]
    check(header == ["mhc", "pep", "tgt"] + (["rand"] if member == "im_train.csv" else []),
          f"Unexpected source header: {member}")
    prepared_index = 0
    for row_index, (line, fields) in enumerate(source, 1):
        check(len(fields) == len(header) and fields[2] in {"0", "1"}, f"Malformed {member}")
        raw_hla, peptide, label = fields[:3]
        allele = context.mapping.get(raw_hla)
        if adapter.exclusion_reason(peptide, raw_hla, context, reference) is not None:
            continue
        if dev_index.query(peptide, allele)["teacher_fit_within_one_mismatch_peptide"]:
            continue
        prepared_index += 1
        yield {"prepared_row_index": prepared_index, "hla": allele, "peptide": peptide, "original_label": label}, {
            "source_row_id": pilot.row_id(context.archive_sha256, member, row_index),
            "source_file": member, "row_index": row_index, "source_line_number": line,
            "source_row_sha256": adapter.source_hash(header, fields),
        }


def write_development(archive, members, context, supported, opened, identities):
    with (INPUTS / "historical_IM_development.csv").open("x", newline="", encoding="utf-8") as stream:
        dev = csv.DictWriter(stream, fieldnames=["mhc", "pep", "tgt"], lineterminator="\n")
        dev.writeheader()

        class UnusedLedger:
            def writerow(self, row):
                pass

        _, retained = adapter.development(
            adapter._source_rows(archive, "im_val.csv", members, opened, identities),
            context, supported, dev, UnusedLedger())
    return retained


def write_el(archive, members, context, reference, dev_index, excluded, opened, members_read):
    rows = []
    for row, provenance in stream_training_rows(
            adapter._source_rows(archive, "el_train.csv", members, opened, members_read),
            "el_train.csv", context, reference, dev_index):
        row["source_row_id"] = provenance["source_row_id"]
        rows.append(row)
    train, validation, removed = el_split.split_el(rows, excluded)
    el_split.verify_el(rows, train, validation, removed, excluded)
    check(len(rows) == 1453578 and len(removed) == 11, "Prepared EL or IM selection exclusion differs")
    # Task 2.35 vetoed exact peptide matches to every EL positive, even
    # validation and the rows excluded from the Task 2.23 EL split.
    positives = sorted({r["peptide"] for r in rows if r["original_label"] == "1"})
    with (INPUTS / "all_el_positive_peptides.txt.gz").open("xb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
            for peptide in positives:
                stream.write((peptide + "\n").encode("ascii"))
    native.write_rows(INPUTS / "EL_train.csv.gz", train)
    native.write_rows(INPUTS / "EL_validation.csv.gz", validation)
    return train, validation


def prepare_training():
    auth = read(D / "preflight/teacher_generated.json")
    model_path = INPUTS / "teacher.json"
    pairs_path = INPUTS / "teacher_fitted_pairs.json"
    check(sha(model_path) == auth["teacher_sha256"] and sha(pairs_path) == auth["fitted_pairs_sha256"],
          "Generated Teacher inputs changed")
    model = teacher.load_model(model_path)
    supported = allele_support(raw_path("reference"))
    reference = {a: [a] for a in supported}
    fit_pairs = {tuple(pair) for pair in read(pairs_path)}
    with zipfile.ZipFile(raw_path("bigmhc_v4")) as archive:
        members = source_members(archive)
        opened, members_read = [], {}
        context = pilot.Context(model, mapping_for(supported), pilot.NeighborIndex(fit_pairs, fit_pairs),
                                sha(model_path), inputs()["bigmhc_v4"]["sha256"], {})
        development = write_development(archive, members, context, reference, opened, members_read)
        check(sum(1 for line in (INPUTS / "historical_IM_development.csv").open()) == 384,
              "Unexpected historical development count")
        dev_index = pilot.NeighborIndex(development, development)
        prepared_im = list(stream_training_rows(
            adapter._source_rows(archive, "im_train.csv", members, opened, members_read),
            "im_train.csv", context, reference, dev_index))
        im = [r for r, _ in prepared_im]
        _, im_selection = im_split.grouped_split(im)
        excluded = {row["peptide"] for row in im_selection}
        check(len(im_selection) == 686 and len(excluded) == 665, "Historical IM selection changed")
        native.write_rows(INPUTS / "IM_train.csv.gz", im)
        with (INPUTS / "historical_IM_selection.txt").open("x", encoding="ascii") as stream:
            stream.writelines(p + "\n" for p in sorted(excluded))
        write_el(archive, members, context, reference, dev_index, excluded, opened, members_read)
    expected = read(P.repository_root / "configs/bigmhc_pilot_v0.json")
    for member in ("el_train.csv", "im_train.csv", "im_val.csv"):
        spec = expected["development_member"] if member == "im_val.csv" else expected["scoring_config"]["members"][member]
        check(members_read[member]["sha256"] == spec["sha256"], f"Immutable member changed: {member}")
    for name in ("EL_train", "EL_validation", "IM_train"):
        checked_training_bytes(name)
    put(D / "preflight/training_inputs_generated.json", {
        "status": "PASS", "sources": members_read, "counts": {
            name: len(native.load_rows(INPUTS / f"{name}.csv.gz"))
            for name in ("EL_train", "EL_validation", "IM_train")
        },
        "generated_sha256": {name: sha(INPUTS / name) for name in (
            "EL_train.csv.gz", "EL_validation.csv.gz", "IM_train.csv.gz",
            "historical_IM_development.csv", "historical_IM_selection.txt", "all_el_positive_peptides.txt.gz")},
    })


def controls():
    prepared = read(D / "preflight/training_inputs_generated.json")["generated_sha256"]
    check(sha(INPUTS / "EL_train.csv.gz") == prepared["EL_train.csv.gz"], "Generated EL input changed")
    model_path = INPUTS / "teacher.json"
    check(sha(model_path) == read(D / "preflight/teacher_generated.json")["teacher_sha256"], "Generated Teacher changed")
    model = teacher.load_model(model_path)
    train = native.load_rows(INPUTS / "EL_train.csv.gz")
    predictions = {}
    for row in train:
        if row["original_label"] != "1":
            continue
        prediction = model.predict_stability(row["peptide"], row["hla"])
        check(prediction["model_status"] == "ok", "Teacher did not score a retained EL positive")
        predictions[row["source_row_id"]] = SimpleNamespace(
            original_peptide=row["peptide"], resolved_hla=row["hla"],
            predicted_half_life_hours=repr(prediction["predicted_half_life_hours"]))
    _, ledger, proof = native.weights_for(train, SimpleNamespace(scores=predictions))
    check(len(ledger) == 63053 and len(proof["by_HLA"]) == 49, "Wrong EL rank reference population")
    native.write_rows(INPUTS / "training_only_weights.csv.gz", ledger)
    checked_training_bytes("training_only_weights")
    audits, fp32 = [], []
    for seed in SEEDS:
        weights, audit = make_controls(ledger, seed)
        output = D / f"controls_private/positive_control_weights_seed{seed}.csv.gz"
        native.write_rows(output, weights)
        by_hla = defaultdict(list)
        for record in weights:
            by_hla[record["hla"]].append(record)
        for group in audit:
            hla = group["hla"]
            rows = by_hla[hla]
            mean = sum(Fraction(r["L_exact"]) for r in rows) / len(rows)
            rounded_mean = math.fsum(r["L_FP32"] for r in rows) / len(rows)
            constant = rows[0]["L_const_FP32"]
            fp32.append({"seed": seed, "hla": hla, "positive_n": len(rows), "L_mean_exact": str(mean),
                         "L_const_exact": rows[0]["L_const_exact"], "original_FP32_mean": rounded_mean,
                         "constant_FP32_mean": constant, "FP32_mean_rounding_difference": constant - rounded_mean,
                         "exact_mean_match": mean == Fraction(rows[0]["L_const_exact"])})
        audits.append({"seed": seed, "sha256": sha(output), "groups": audit})
    csvout(D / "metrics/CONTROL_CONSTANT_FP32_DIAGNOSTICS.csv", fp32)
    put(D / "preflight/control_preparation_audit.json", {"status": "PASS", "rows": len(ledger), "seed_audits": audits})


def released_neo(supported, el_train, el_validation, im):
    with zipfile.ZipFile(raw_path("bigmhc_v4")) as archive:
        info = source_members(archive)["im_test.csv"]
        check(info.file_size == 279819, "Unexpected Neo source member size")
        binary = archive.read(info)
    check(hashlib.sha256(binary).hexdigest() ==
          "70ba5dbeecb0e62ccc95f2aa11a28801773893f4ebf209b5e68b58318be7b634", "Neo member hash changed")
    rows = neo.source_identities(io.BytesIO(binary))
    check(len(rows) == 937, "Unexpected Neo released population")
    classified = [neo.classify(dict(row, EL_train_peptide=row["peptide"] in el_train,
                                   EL_validation_peptide=row["peptide"] in el_validation,
                                   IM_train_peptide=row["peptide"] in im), supported) for row in rows]
    selected = [row for row in classified if row["primary"]]
    policy = {"released_rows": len(rows), "canonical_ninemers": sum(valid_ninemer(r["peptide"]) for r in rows),
              "first_exclusions": dict(Counter(r["primary_first_exclusion"] for r in classified if not r["primary"]))}
    check(policy["canonical_ninemers"] == 281 and len(selected) == 267, "Neo eligibility population changed")
    # The selection mask is persisted before the tgt field is decoded.
    put(D / "preflight/neo_selection.json", policy)
    wanted = {r["row_index"]: r for r in selected}
    outcomes = []
    reader = csv.reader(io.StringIO(binary.decode("utf-8-sig")), strict=True)
    check(next(reader)[:3] == ["mhc", "pep", "tgt"], "Neo source schema changed")
    for row_index, fields in enumerate(reader, 1):
        if row_index not in wanted:
            continue
        r = wanted[row_index]
        check(fields[:2] == [r["raw_hla"], r["raw_peptide"]] and fields[2].strip() in {"0", "1"},
              "Neo outcome could not be bound")
        outcomes.append({"source_id": r["source_id"], "label": int(fields[2].strip())})
    return [projection.compact_identity(row, "neoepitope") for row in selected], outcomes, {
        r["peptide"] for r in classified if valid_ninemer(r["peptide"])}


def released_improve(supported, references, prior_neo):
    config = read(P.repository_root / improve.CONFIG)
    with zipfile.ZipFile(raw_path("improve")) as archive:
        entries = [entry for entry in archive.infolist() if entry.filename == config["member"]]
        check(len(entries) == 1 and entries[0].file_size <= 8 * 1024 * 1024, "Missing or unbounded IMPROVE table")
        member = archive.read(entries[0])
    check(hashlib.sha256(member).hexdigest() == config["member_sha256"], "IMPROVE table identity changed")
    source = improve.parse_source(member, config)
    with raw_path("improve_crosscheck").open(encoding="utf-8", newline="") as stream:
        crosscheck = csv.DictReader(stream, delimiter="\t")
        for row, companion in zip(source, crosscheck, strict=True):
            check((row["raw_peptide"], row["raw_hla"], row["label"]) ==
                  (companion["Mut_peptide"], companion["HLA_allele"], int(companion["response"])),
                  "IMPROVE peer-source identity differs")
    conflicts = improve.conflict_ids(source)
    candidates = [r for r in source if not improve.compatible(r, supported, conflicts)]
    check((len(source), len(candidates), sum(r["label"] for r in candidates)) == (17520, 10561, 308),
          "IMPROVE curation population changed")
    union = set().union(*references.values())
    check(len(union) == 1250989, "IMPROVE development/selection reference union changed")
    index = NearestNineIndex(union)
    distances = {peptide: index.nearest(peptide)[0] for peptide in sorted({r["peptide"] for r in candidates})}
    for row in candidates:
        row["minimum_fitting_selection_distance"] = distances[row["peptide"]]
        row["exact_prior_published_benchmark_peptide"] = row["peptide"] in prior_neo
    selected = improve.select_threshold(candidates, 3)
    patients = improve.components(selected, "patient")
    studies = improve.components(selected, "study")
    for row, patient, study in zip(selected, patients, studies, strict=True):
        row.update(patient_peptide_component=patient, study_peptide_component=study)
    put(D / "preflight/improve_selection.json", {
        "released_rows": len(source), "candidate_rows": len(candidates), "reference_union": len(union),
        "reference_sizes": {name: len(peptides) for name, peptides in references.items()},
        "final_rows": len(selected), "patient_peptide_components": len(set(patients)), "study_peptide_components": len(set(studies)),
    })
    from improve_metadata import report as improve_metadata
    improve_metadata(member, source, candidates, selected, config)
    return [projection.compact_identity(r, "IMPROVE") for r in selected], [
        {key: r[key] for key in ("source_id", "label", "raw_response")} for r in selected]


def write_and_check_cohort(name, rows, outcomes):
    expected = read(EXPECTED)["cohorts"][name]
    keys = [row["source_id"] for row in rows]
    native.assert_alignment(keys, [y["source_id"] for y in outcomes])
    field = "patient_peptide_component" if name == "IMPROVE" else "cluster_id"
    positive = sum(row["label"] for row in outcomes)
    check((len(rows), positive, len({r[field] for r in rows})) ==
          (expected["n"], expected["positives"], 38 if name == "IMPROVE" else 265), f"{name} census changed")
    check(digest(keys) == expected["source_order_hash"], f"{name} source order changed")
    result = {"n": len(rows), "positives": positive, "source_order_hash": digest(keys)}
    for suffix, values, key in (("identities", rows, "identity_sha256"), ("outcomes", outcomes, "outcome_sha256")):
        path = D / f"cohorts/{name}_{suffix}.jsonl"
        projection.write_rows(path, values)
        result[key] = sha(path)
        check(result[key] == expected[key], f"{name} {suffix} bytes differ from audited source")
    return result


def build_cohorts():
    supported = allele_support(raw_path("reference"))
    for name in ("EL_train", "EL_validation", "IM_train"):
        checked_training_bytes(name)
    references = {key: {r["peptide"] for r in native.load_rows(INPUTS / f"{name}.csv.gz")}
                  for key, name in (("EL_fit", "EL_train"), ("EL_selection", "EL_validation"), ("IM_fit", "IM_train"))}
    generated = read(D / "preflight/training_inputs_generated.json")["generated_sha256"]
    for name in ("historical_IM_selection.txt", "historical_IM_development.csv"):
        check(sha(INPUTS / name) == generated[name], f"Changed reference: {name}")
    references["IM_epoch_selection"] = set((INPUTS / "historical_IM_selection.txt").read_text().splitlines())
    with (INPUTS / "historical_IM_development.csv").open(newline="", encoding="utf-8") as stream:
        references["IM_historical_development"] = {r["pep"] for r in csv.DictReader(stream)}
    neo_rows, neo_y, prior = released_neo(supported, references["EL_fit"], references["EL_selection"], references["IM_fit"])
    neo_receipt = write_and_check_cohort("Neo", neo_rows, neo_y)
    improve_rows, improve_y = released_improve(supported, references, prior)
    improve_receipt = write_and_check_cohort("IMPROVE", improve_rows, improve_y)
    coverage = []
    for name, rows in (("IMPROVE", improve_rows), ("Neo", neo_rows)):
        coverage.append({"cohort": name, "n": len(rows),
                         "patient_nonempty_rows": sum(bool(r.get("patient")) for r in rows),
                         "study_nonempty_rows": sum(bool(r.get("study") or r.get("study_DOI")) for r in rows),
                         "assay_nonempty_rows": sum(bool(r.get("assay")) for r in rows),
                         "sample_nonempty_rows": sum(bool(r.get("sample")) for r in rows),
                         "patient_independence": "NOT_ESTABLISHED_BY_NONEMPTY_KEYS_ALONE",
                         "identity_source_SHA256": sha(D / f"cohorts/{name}_identities.jsonl")})
    csvout(D / "metrics/COHORT_METADATA_COVERAGE.csv", coverage)
    put(D / "preflight/cohorts_generated.json", {"Neo": neo_receipt, "IMPROVE": improve_receipt})


if __name__ == "__main__":
    import sys

    stage = {"teacher": build_teacher, "prepare": prepare_training, "cohorts": build_cohorts, "controls": controls}
    stage[sys.argv[1]]()
