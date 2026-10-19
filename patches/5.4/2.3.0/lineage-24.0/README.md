# SUSFS 2.3.0 for MIX4 lineage-24.0 / Linux 5.4.302

Use `series` for the candidate kernel with the Dream OEM adaptation. This profile changes 28 paths (23 modified, 5 added), including the SUSFS core and inline host hooks. The sibling `../series` remains the published Linux 5.4.259 profile.

## Baseline and build integration

- Kernel upstream: Inkypen79/kernel_xiaomi_odin `lineage-24.0`, `550c3503d7402b5f689f7956f083c2192282c071`.
- Exact pre-SUSFS OEM host: `43fe4bf80b65cbbe92cdacb12705505a23d62e35`, in kafuuchino-s/kernel_xiaomi_odin. Its `fs/proc/base.c` OEM task controls remain present.
- Checkpoint-one dependencies: SUSFS upstream `ca7093a1a26f7911987110c34a1352d74cfb1d09`, BakaSU `1744c140a08b233daf3b71801994b9b197318ef0`.
- Historical 5.4 patch extraction: SUSFS `82f08351fadb8b19dd6591bd14634d02ad832145`. See the sibling README for the existing SELinux mappings.

Set the kernel recipe's `susfs_series` to `patches/5.4/2.3.0/lineage-24.0/series`, relative to the pinned `susfs4ksu` submodule. Pass that file to the existing `kernel-patches/apply-susfs.py` before configuration:

```sh
python3 "$ROOT/kernel-patches/apply-susfs.py" "$ROOT" \
    "$ROOT/susfs4ksu/patches/5.4/2.3.0/lineage-24.0/series"
```

The helper preflights the whole series, applies a clean tree once, skips an already applied tree, and rejects a partial or conflicting state without modifying source files. Do not also apply the upstream GKI KernelSU patch to BakaSU. The integrating kernel retains responsibility for its driver glue, configuration, banner, recipe and submodule pins.

`files.list` names every affected path. `manifest.json` records the baseline and postimage Git blob IDs and modes. New baseline requirements apply to this profile; the published sibling profile keeps its existing contract.

## Port choices

The 5.4.259 inline hooks retain their locations and conditions. Linux 5.4.302 requires three adjustments:

- `fs/exec.c`: place `susfs_def.h` beside the current uaccess include. Keep the `__do_execve_file()` flow and BakaSU pre/post-exec calls, including the `!file` condition and `TIF_PROC_IN_KSU_EXECVE` reset.
- `fs/proc/fd.c`: retain the new upstream `ino:` fdinfo field. Print the same local inode value updated by `susfs_sus_kstat_spoof_proc_fd_seq_show()`, together with its adjusted mount ID. A plain file retains its real inode and mount ID; an eligible app sees configured kstat values. The existing task, file reference and lock lifetimes remain intact.

- `fs/proc/task_mmu.c`: Linux 5.4.302 makes `show_smap_vma()` a `void` callback. Its SUS_MAP early exit uses `return;`, preserving the hidden-VMA skip without returning a value. Both maps and smaps filter padding output using the original file-backed VMA, before `show_map_pad_vma()` turns padding into an anonymous VMA. `m_cache_vma()` still runs for hidden mappings.

The port stores metadata in existing thread, mapping, nameidata and mount flag bits; it adds no inode, mount or task structure members. BakaSU owns SELinux hiding and policy hooks. The host series includes the SUSFS AVC audit hook in `security/selinux/avc.c`; it does not add wrappers to `security/selinux/hooks.c` or `security/selinux/selinuxfs.c`.

## Reproduce application and reversal

The verifier reads the evidence kernel repository and creates a disposable scratch repository. It checks all 28 baseline blobs and modes, invokes the kernel's application helper twice, checks postimages and index preservation, then reverses the patch and compares the complete baseline tree and file bytes:

```sh
python3 /absolute/path/to/this/profile/verify_roundtrip.py \
    --kernel-repo /path/to/kernel
```

Use `--kernel-ref COMMIT` to verify a later OEM host whose affected preimages match the manifest. The reference must contain `kernel-patches/apply-susfs.py`. The source kernel tree is not modified.

For removal from an applied disposable or integrating tree, run from its root:

```sh
PROFILE=/absolute/path/to/this/profile
git apply --reverse --check "$PROFILE/0001-susfs-2.3.0-mix4-5.4.302-backport.patch"
git apply --reverse "$PROFILE/0001-susfs-2.3.0-mix4-5.4.302-backport.patch"
```

## Compilation handoff

The kernel owner runs incremental checks with the same prepared `out`, make arguments, CFI configuration and prefix maps as `build.sh`. Compile these changed C objects before a full build:

```text
drivers/input/input.o
fs/exec.o fs/namei.o fs/namespace.o fs/notify/fdinfo.o fs/open.o
fs/proc/base.o fs/proc/cmdline.o fs/proc/fd.o fs/proc/task_mmu.o
fs/proc_namespace.o fs/read_write.o fs/readdir.o fs/stat.o fs/statfs.o
fs/super.o fs/susfs.o
kernel/kallsyms.o kernel/reboot.o kernel/sys.o
mm/memory.o security/selinux/avc.o
```

Keep `CONFIG_KSU=y`, `CONFIG_KSU_SUSFS=y`, the requested SUSFS features, and `CONFIG_KSU_MANUAL_HOOK=n`. BakaSU supplies the top-level Kconfig option and hook implementation. Its changed objects and the header consumers also need rebuilding under normal Kbuild dependency tracking. Application/reversal proves source transformation; compilation, vendor ABI checks, boot and runtime behavior remain the integrating kernel's acceptance gates.
