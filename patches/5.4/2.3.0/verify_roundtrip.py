#!/usr/bin/env python3
"""Prove an exact SUSFS removal/reapplication against the recorded kernel release.

Uses a new scratch Git repository and a full kernel index, but checks out only
patched paths. The source kernel repository is read-only. No build is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-repo', required=True, type=Path)
    parser.add_argument('--work-dir', required=True, type=Path,
                        help='New, nonexistent scratch directory')
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    patch_dir = Path(__file__).resolve().parent
    manifest = json.loads((patch_dir / 'manifest.json').read_text())
    patches = [patch_dir / line for line in (patch_dir / 'series').read_text().splitlines() if line]
    source = args.kernel_repo.resolve()
    scratch = args.work_dir.resolve()
    scratch.mkdir(parents=True, exist_ok=False)
    run(scratch, 'init', '-q')
    objects = run(source, 'rev-parse', '--path-format=absolute', '--git-path', 'objects').decode().strip()
    (scratch / '.git/objects/info/alternates').write_text(objects + '\n')
    run(scratch, 'config', 'core.autocrlf', 'false')
    run(scratch, 'config', 'core.filemode', 'true')
    release = manifest['kernel_release']
    base = manifest['kernel_pre_susfs_baseline']
    paths = [entry['path'] for entry in manifest['files']]
    expected_release_tree = run(source, 'rev-parse', release + '^{tree}').decode().strip()
    run(scratch, 'read-tree', release)
    run(scratch, 'checkout-index', '--index', '--', *paths)
    checks = []

    def check_files(state_name, source_revision):
        for entry in manifest['files']:
            path = entry['path']
            expected = entry[state_name]
            file = scratch / path
            tree_entry = run(source, 'ls-tree', source_revision, '--', path).decode().strip()
            if expected is None:
                assert not tree_entry and not file.exists(), path
                continue
            mode, kind, rest = tree_entry.split(' ', 2)
            blob, listed_path = rest.split('\t')
            assert kind == 'blob' and listed_path == path, path
            assert mode == expected['mode'] and blob == expected['git_blob'], path
            data = file.read_bytes()
            assert data == run(source, 'cat-file', 'blob', blob), path
            assert len(data) == expected['bytes'], path
            assert hashlib.sha256(data).hexdigest() == expected['sha256'], path
            executable = bool(file.stat().st_mode & 0o111)
            assert executable == (mode == '100755'), path
            if state_name == 'baseline':
                assert b'CONFIG_KSU_SUSFS' not in data and b'<linux/susfs' not in data, path
        checks.append({'check': state_name + '_bytes_modes_and_manifest', 'paths': len(paths), 'result': 'PASS'})

    check_files('applied', release)
    for patch in reversed(patches):
        run(scratch, 'apply', '--check', '--reverse', '--index', '--whitespace=nowarn', str(patch))
        run(scratch, 'apply', '--reverse', '--index', '--whitespace=nowarn', str(patch))
    check_files('baseline', base)
    baseline_tree = run(scratch, 'write-tree').decode().strip()
    changed = run(scratch, 'diff', '--cached', '--name-only', release).decode().splitlines()
    assert changed == paths, (changed, paths)
    checks.append({'check': 'all_unlisted_release_paths_retained_in_full_index', 'result': 'PASS'})

    for patch in patches:
        run(scratch, 'apply', '--check', '--index', '--whitespace=nowarn', str(patch))
        run(scratch, 'apply', '--index', '--whitespace=nowarn', str(patch))
    check_files('applied', release)
    applied_tree = run(scratch, 'write-tree').decode().strip()
    assert applied_tree == expected_release_tree, (applied_tree, expected_release_tree)
    checks.append({'check': 'applied_full_kernel_tree_equals_release_tree', 'result': 'PASS'})

    for patch in reversed(patches):
        run(scratch, 'apply', '--check', '--reverse', '--index', '--whitespace=nowarn', str(patch))
        run(scratch, 'apply', '--reverse', '--index', '--whitespace=nowarn', str(patch))
    check_files('baseline', base)
    reversed_tree = run(scratch, 'write-tree').decode().strip()
    assert reversed_tree == baseline_tree, (reversed_tree, baseline_tree)
    checks.append({'check': 'reverse_full_kernel_tree_equals_baseline_tree', 'result': 'PASS'})
    report = {
        'result': 'PASS',
        'source_kernel_release': release,
        'source_pre_susfs_baseline': base,
        'release_tree': expected_release_tree,
        'stripped_release_baseline_tree': baseline_tree,
        'reapplied_tree': applied_tree,
        'reversed_tree': reversed_tree,
        'patch_files': [p.name for p in patches],
        'modified_files': sum(entry['baseline'] is not None for entry in manifest['files']),
        'added_files': sum(entry['baseline'] is None for entry in manifest['files']),
        'checks': checks,
        'comparison': 'Each existing baseline file is compared directly with its OEM-baseline Git blob; every applied file is compared directly with its release Git blob. Modes and manifest SHA-256 values are checked. The full Git index proves all unlisted paths, including SELinux hooks.c/selinuxfs.c and BakaSU, are preserved.',
        'not_run': ['kernel compilation', 'ABI audit', 'device validation'],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
