# Repository-driven reproducibility audit (Task 2.15M)

This audit starts from approved commit `0c3b5cf245c42803854c9139f4c4058cc36f7dbf`.
It performs transport, cryptographic verification and metadata inventory only. It
runs no model, reads no scientific table rows and opens no sealed BigMHC ZIP member.
Mac evidence does not establish Windows execution or checkpoint integrity.

The project is **not yet fully reconstructible from a fresh clone**. The two
current GPU-input packages have a tested exact restoration path. Much historical
analysis has generation code, but exact frozen models, complete provenance
snapshots and Windows outputs still need authenticated backups.

## Architecture and authority

The existing path resolver remains authoritative. A workspace root is the `codex`
directory containing `repos/`, `data/` and `runs/`, rather than the user's home.
Code, transport definitions and reconstruction recipes live in Git. Archives and
partial downloads live in `data/stability-label-curation/artifacts/cache/`;
source files retain their original data paths and derived files their original
run paths. No migration or automatic retraining is performed.

`configs/artifact_registry.json` extends transport instructions; it does not
replace `data_sources.toml`, the scientific evidence locks or run manifests.
`configs/artifact_reconstruction_plan.json` records group-level generation recipes,
producing commits, actual historical input identities, environment requirements,
seeds, dependencies, consumers and gaps. The 21-file GPU mapping references the
existing transfer manifest by its SHA256 rather than maintaining a second list.

Registry entries require a stable ID/version, role, transport format, archive or
file SHA256 and size, HTTPS locator/host allowlist, exact members, hashes and
canonical `data`/`runs` destinations. Incomplete source groups are kept in the
reconstruction plan as GAP, not disguised as downloadable artifacts. Dependencies
are recorded; the restore command operates only on explicitly selected IDs and
does not execute dependencies or recipes automatically.

## Mac inventory and classification

The audit inventories 9 historical data groups and 22 historical run directories.
The plan additionally identifies payload subsets, unavailable historical data,
future independent evaluation and four pending Windows groups: 39 groups total.
Subsets overlap directories; group counts must not be summed as physical bytes.
The generated inventory counts each physical file once, hashes all regular
scientific/provenance files, and records installed environments as metadata only.
It reports symlinks without following them. The current audit/cache directories
are excluded so repeated inventory is deterministic.

| Class | Groups | Meaning and limit |
|---|---:|---|
| R1 | 5 | Hash-pinned retrieval definition for exact source/payload files |
| R2 | 21 | Documented regeneration, conditional on authenticated parents and authorization |
| R3 | 1 | Exact score-sidecar restore plus a documented deterministic generator |
| GAP | 12 | Missing full provenance, input, backup, original data or Windows verification |

R1 public-source definitions reuse original publisher or commit-pinned source
links; their remote availability was not retested here. Both Dropbox R1/R3
packages were independently downloaded and verified in this audit. R2 is not a
claim of successful clean-machine replay. Every recipe records conditional input
requirements. Exact-byte recovery of a complete old run directory is evaluated
separately and generally unavailable even when deterministic scientific reports
can be recomputed. No historical scientific analysis was rerun in this task.

The generated `artifact_dependency_graph.json` uses the actual historical run
inputs, not assumed relationships. Producer configuration hashes are checked
against Git at the recorded commit. An argv recording run creation or an old
temporary script is not treated as the generation recipe.

## Tested transport packages

| ID | Compressed bytes | SHA256 | Regular members |
|---|---:|---|---:|
| `gpu-inputs-23af9966` | 165,825,262 | `16c9beff7a85f65da2485ebbe5b986424114a9f39405d8acba4403ad83ab26bf` | 21 |
| `el-positive-scores-task2-13` | 7,279,294 | `c4465d7ac048d278546c63057516b56a0ab28dfc96e63f47d705a48a11adff2e` | 2 |

The GPU archive expands to 207,979,774 original-file bytes. Its expected archive
hash comes from the retained packaging-verification receipt, whose identity is
recorded in the registry. The mapping comes from the approved transfer manifest
SHA256 `4a369fbfeaece04fb05f0d03e2df42a31c285d1b996b495582119c4972a66331`.
The sidecar archive expands to the 7,272,684-byte score file plus the 11,060-byte
positive-score manifest. It covers 70,069 positives and 49 HLA groups; the existing
Task 2.13 receipt authenticates both member hashes. These are local checksums
established by project evidence, not publisher checksums.

Original-label views, source-row ledgers, the frozen development cohort,
pseudosequences and ten pinned BigMHC source files are included. Neither bundle
contains historical corrected views, sealed evaluation datasets, checkpoints,
Teacher fitting artifacts or credentials. The score sidecar is not a relabeled
training table. Original source values and paths are preserved.

## Access and sharing

Authenticated GitHub repository metadata reported `private` during this audit.
That does not establish permission to redistribute the datasets or publish
capability-bearing Dropbox links. No complete shared link is committed. Resolve
these locator references through authorized environment variables:

- `SLC_ARTIFACT_GPU_INPUTS_URL`
- `SLC_ARTIFACT_EL_POSITIVE_SCORES_URL`

Obtain their values through an approved private channel. Receipts never record
those values. Authorized access to the private repository and live artifact links
remains an external prerequisite: the recovery is not unattended without it.
There are no new uploads. Existing Academic software-license and dataset terms
remain separate; no new legal determination is made. See the source audits and
`data_sources.toml` before any redistribution.

## Restore contract

See [fresh-clone recovery](FRESH_CLONE_RECOVERY.md) for executable commands.
The standard-library wrapper supports `list`, `status`, `fetch`, `restore`,
`verify`, `dry-run`, explicit IDs, `--all`, `--workspace-root`, `--registry` and
`--receipt`. Output is JSON; verification failure returns nonzero. Read-only
operations and dry runs create no directories. Existing matching files are reused;
wrong-hash files cause a failure and are left untouched. An explicit receipt must
be a new file in controlled artifact or run storage; failures also produce JSON
on stdout, which can be captured by the caller.

Transport uses bounded HTTPS streaming, exact size/hash gates, timeouts and an
allowlisted redirect chain. Temporary files stay beside the controlled cache
file. Archives are fully verified before any destination is published. Only the
registered regular files are accepted; absolute/traversal names, links, special
files, duplicates, unexpected members and unsafe archive structures fail closed.
Writes use atomic no-replace publication. Partial publication after an OS failure
can be resumed by authenticating and reusing the already completed files.

A disposable root under project `data/artifacts/audits/task-2_15/clean-root` was
used for genuine network recovery, not seeded from local source files. Receipts
record download lengths, all 23 restored hashes and exact relative destinations.
An offline second invocation must reuse all files with zero download bytes.
The existing worker input verifier also authenticated all 23 restored inputs
(215,263,518 bytes), including its original-view and parent-manifest contracts,
without loading a model or parsing development outcomes.
Wrong-hash and malicious-archive behavior is covered by synthetic tests and the
canonical collision probe. No part of the workflow depends on a legacy download
folder or extraction into a user's home.

## Reconstructing historical analyses and trained models

For a reconstruction, inspect the relevant group in the reconstruction plan,
check out its producing commit into a separate worktree, authenticate **all**
listed parents, recreate its environment and create a new run through the existing
run-manifest infrastructure. Use the listed configuration, seed and generation
command. Training recipes are documentation only and require separate approval.
Historical unapproved label-view generation is marked explicitly; it is not a
current recommended workflow. No original or historical run is overwritten.

A freshly generated manifest contains new timestamps, host paths, code state and
possibly software versions. Existing downstream configurations often pin the
original manifest/report SHA256, including host-specific metadata. A new manifest
cannot substitute for that input merely because its scientific rows agree.
Either restore the old provenance byte-for-byte, or approve a separately versioned
descendant configuration that explicitly binds new evidence hashes and preserves
all scientific inputs, cohort rules, seeds and model settings. Never edit old
receipts or relax checksum gates silently.

The frozen Task 2.3 Teacher has model SHA256
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
It is present locally, but no authenticated external model locator is known.
A fitted replacement, even from the same science recipe, does not establish this
identity. The Task 2.7 and CPU-regression EL/IM weights also lack remote backups.
The inventory hashes their opaque bytes without deserializing them. Prefer exact
checkpoint restoration when authorized archives become available; no automatic
training fallback is provided.

## Prioritized gaps

| Priority | Missing recovery evidence | Required remedy |
|---|---|---|
| Current A/B/P training | Windows 2.14B/C receipts, matched-state/checkpoint identities and backup locators | After Windows work closes, collect metadata and publish approved authenticated backup definitions |
| Baseline A reproduction | Task 2.9/2.10 Windows models, full lineage and runtime receipts absent on Mac | Verify on Windows; archive trained outputs outside Git; register hashes and restricted locators |
| Teacher reproduction / rescoring | Exact frozen Teacher and byte-pinned parent provenance lack remote recovery | Back up model plus input/provenance manifests; rerunning is a distinct model identity |
| Historical analysis | Source acquisition metadata, documentary PDF/HTML snapshots and some pinned checkout evidence | Restricted exact metadata/source backups or explicit reproducible snapshot recipes |
| Historical replay | Host-specific manifest hashes and local paths | Approved versioned provenance rebinding or exact legacy evidence backup |
| Future independent evaluation | Cohort acquisition/provenance and checkpoint exposure not finalized | Separate authorized evaluation audit; keep sealed outcomes unopened |

The current Mac contains no Task 2.9, 2.10 or 2.14B/C outputs. Their metadata are
recorded as pending Windows verification, not reconstructed results. The original
5,509-row NetMHCstab table remains unavailable; synthetic rows cannot fill that
gap. The T-SCAPE original supplement was not locally acquired. Installed virtual
environments are regenerated from version-controlled requirements, not copied
between platforms; CUDA compatibility remains a worker-specific check.

## Windows checks after Task 2.14C closes

Do not change or interrupt the active worker. Afterwards fetch the reviewed audit
commit, configure authorized locator variables privately, and execute the recovery
guide's `status`, `restore` and `verify` commands with an explicit Windows WSL2
workspace root. No training is required. Run the synthetic restore tests on Linux.
Verify the original 21 GPU files and the 2 score files, then inventory Windows
Task 2.9/2.10/2.14B/C manifests, configurations, environments, parent EL state,
IM overlays, initial-state and sampling hashes, checkpoint sizes/hashes and
prediction-file hashes. Do not expose sealed evaluation outcomes or load weights
merely to inventory them. Return authenticated metadata for a later approved
backup/registry update. Mac validation alone does not certify those artifacts.

## Reproducing the metadata audit

Read-only inspection (standard library):

```sh
PYTHONPATH=src python3 -B -m stability_label_curation.reproducibility_audit
```

For saved reports, first reserve a new run from the clean committed checkout with
`run_manifest.create_run`. Pass `configs/artifact_registry.json` as configuration
and the actual inventory `file_records` paths as explicit hashed inputs. Also
record any transport archives or receipts actually read. Then run:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation.reproducibility_audit --out "$HOME/codex/runs/stability-label-curation/<new_run_id>"
PYTHONPATH=src python3 -B -m stability_label_curation runs validate <new_run_id>
```

The inventory treats the canonical Task 2.15M run and project artifact/cache tree
as audit outputs, outside the historical inventory. Other newly created run
folders are deliberately discovered rather than silently omitted. A later
inventory may therefore differ legitimately as experiments accumulate; preserve
the original inventory and compare immutable file records when checking integrity.
