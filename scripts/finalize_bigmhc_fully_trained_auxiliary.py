"""Save focused read-only completion verification and closed resource-log hashes."""
import json

from stability_label_curation import bigmhc_fully_trained_auxiliary as experiment
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation.paths import resolve_paths
from verify_bigmhc_fully_trained_auxiliary import verify


def main() -> None:
    paths = resolve_paths()
    directory = paths.project_runs_dir/experiment.RUN_ID
    verification = verify()
    runner.raw.write_report(directory/'reports/completion_verification.json', verification, paths=paths)
    samples = []
    failed = 0
    for line in (directory/'logs/execute_gpu.jsonl').read_text().splitlines():
        record = json.loads(line)
        if record['returncode'] != 0:
            failed += 1
            continue
        fields = record['csv'].split(',')
        samples.append(dict(utilization=float(fields[-4]), memory_MiB=float(fields[-3]),
                            power_W=float(fields[-2]), temperature_C=float(fields[-1])))
    resource = dict(valid_GPU_snapshots=len(samples), failed_GPU_snapshots=failed,
                    snapshot_interval_seconds=30, includes_display_and_other_system_GPU_use=True)
    if samples:
        resource['GPU_summary'] = {k: dict(mean=sum(s[k] for s in samples)/len(samples), maximum=max(s[k] for s in samples)) for k in samples[0]}
    resource['stages'] = {f'{m}_{s}': json.loads((directory/f'reports/{m}_{s}_completed.json').read_text()) for m in ('S', 'P') for s in ('EL', 'IM')}
    runner.raw.write_report(directory/'reports/resource_summary.json', resource, paths=paths)
    finalization = dict(status='passed', scientific_output_manifest_sha256=runner.raw.sha256_file(directory/'reports/output_manifest.json'),
                        completion_verification_sha256=runner.raw.sha256_file(directory/'reports/completion_verification.json'),
                        resource_summary_sha256=runner.raw.sha256_file(directory/'reports/resource_summary.json'),
                        closed_logs={str(p.relative_to(directory)):runner.raw.sha256_file(p) for p in sorted((directory/'logs').iterdir()) if p.is_file()})
    runner.raw.write_report(directory/'reports/finalization_manifest.json', finalization, paths=paths)
    print(json.dumps({k:v for k,v in verification.items() if k != 'loss_histories'}, sort_keys=True, indent=2))
    print(json.dumps(resource, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
