#!/usr/bin/env python3
"""Verify this profile in a disposable repository, without modifying the kernel.

Usage: verify_roundtrip.py --kernel-repo /path/to/kernel [--kernel-ref COMMIT]
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def run(*args, cwd=None, env=None):
    result = subprocess.run(args, cwd=cwd, env=env, check=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-repo', type=Path, required=True)
    parser.add_argument('--kernel-ref', help='default: manifest kernel_baseline')
    args = parser.parse_args()
    source = args.kernel_repo.resolve()
    profile = Path(__file__).resolve().parent
    manifest = json.loads((profile / 'manifest.json').read_text())
    ref = args.kernel_ref or manifest['kernel_baseline']
    paths = [entry['path'] for entry in manifest['files']]
    assert paths == (profile / 'files.list').read_text().splitlines()
    patches = [str(profile / name) for name in (profile / 'series').read_text().splitlines()]
    objects = run('git', '-C', str(source), 'rev-parse', '--git-path', 'objects').decode().strip()
    objects = (source / objects).resolve()
    env = dict(os.environ, GIT_ALTERNATE_OBJECT_DIRECTORIES=str(objects))
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix='susfs-roundtrip-') as directory:
        scratch = Path(directory)
        run('git', 'init', '--quiet', str(scratch), env=env)
        def git(*command):
            return run('git', '-C', str(scratch), *command, env=env)
        baseline_tree = git('rev-parse', ref + '^{tree}').decode().strip()
        git('update-ref', 'HEAD', git('rev-parse', ref).decode().strip())
        git('read-tree', ref)
        present = []
        for entry in manifest['files']:
            record = git('ls-tree', ref, '--', entry['path']).decode().split()
            actual = {'mode': record[0], 'blob': record[2]} if record else None
            assert actual == entry['before'], f"preimage changed: {entry['path']}"
            if actual:
                present.append(entry['path'])
        git('checkout-index', '--force', '--', *present)
        # Use the integrating kernel's established application helper.
        helper = scratch / '.git' / 'apply-susfs.py'
        helper.write_bytes(git('show', ref + ':kernel-patches/apply-susfs.py'))
        def apply():
            output = run('python3', str(helper), str(scratch), str(profile / 'series'), env=env)
            print(output.decode().strip())
            return output
        index = scratch / '.git' / 'index'
        original_index = index.read_bytes()
        assert b'SUSFS: applied ' in apply()
        assert index.read_bytes() == original_index, 'real index changed during application'
        snapshot = {name: (scratch / name).read_bytes() for name in paths}
        assert b'already applied' in apply()
        assert snapshot == {name: (scratch / name).read_bytes() for name in paths}
        assert index.read_bytes() == original_index, 'real index changed during skip'
        git('add', '--', *paths)
        for entry in manifest['files']:
            record = git('ls-files', '--stage', '--', entry['path']).decode().split()
            assert {'mode': record[0], 'blob': record[1]} == entry['after'], entry['path']
        applied_tree = git('write-tree').decode().strip()
        # Reverse with --index so the complete tree comparison protects other paths.
        git('apply', '--reverse', '--check', '--index', *patches)
        git('apply', '--reverse', '--index', *patches)
        assert git('write-tree').decode().strip() == baseline_tree
        for entry in manifest['files']:
            path = scratch / entry['path']
            if entry['before'] is None:
                assert not path.exists(), f'added file survived reversal: {path}'
            else:
                assert path.read_bytes() == git('cat-file', 'blob', entry['before']['blob'])
        print(json.dumps({'kernel_ref': ref, 'files': len(paths),
                          'baseline_tree': baseline_tree, 'applied_tree': applied_tree,
                          'first_apply': 'pass', 'repeat_skip': 'pass',
                          'reverse_check': 'pass', 'baseline_restored': 'pass'}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr.decode(errors='replace').strip()) from error
