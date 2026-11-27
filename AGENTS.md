# Permanent project guardrails

- Primary analyses use human HLA-I data only. Keep measured kinetic half-life and thermal melting temperature separate.
- Synthetic negatives are not experimental stability measurements. SPEARMINT is not a primary training source until provenance auditing is complete.
- Follow the authorized task scope; do not start training, evaluation, downloads, or subsequent tasks without authorization.
- Keep code and small configuration in Git. External inputs/public weights belong in project storage under `data`; derived data, checkpoints, predictions, logs, and metrics belong under `runs`.
- Track only the small published manuscript aggregates in `manuscript/source_data/`; place newly generated outputs outside Git.
- Resolve storage through `stability_label_curation.paths`; never hardcode usernames or machine-specific absolute paths. Imports and path resolution must remain free of filesystem writes.
- Preserve unrelated projects. Do not add automatic deletion, cleanup, or recursive permission changes.
- Prefer typed, standard-library implementations and built-in `unittest`; add dependencies only when justified by the authorized task.
- Validate relevant changes and report actual execution evidence. Do not claim WSL2/GPU validation from macOS checks.
- Commit on the authorized task branch; do not merge, push, or configure remotes without authorization.
