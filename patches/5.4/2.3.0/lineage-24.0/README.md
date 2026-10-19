# SUSFS 2.3.0 for MIX4 lineage-24.0 / Linux 5.4.302

Use `series` for the candidate kernel with the Dream OEM adaptation. This profile changes 28 paths (23 modified, 5 added), including the SUSFS core and inline host hooks. The sibling `../series` remains the published Linux 5.4.259 profile.

## Baseline and build integration

- Kernel upstream: Inkypen79/kernel_xiaomi_odin `lineage-24.0`, `550c3503d7402b5f689f7956f083c2192282c071`.
- Exact pre-SUSFS OEM host: `43fe4bf80b65cbbe92cdacb12705505a23d62e35`, in kafuuchino-s/kernel_xiaomi_odin. Its `fs/proc/base.c` OEM task controls remain present.
- Current merged SUSFS upstream: `f43926dc94b8ffbf9b74321313536600f69367b1`, `gki-android12-5.10`.
- Paired BakaSU candidate: `997d1ac40e65497637741f97c531b1a3fc211e15`.
- Checkpoint-one dependencies: SUSFS upstream `ca7093a1a26f7911987110c34a1352d74cfb1d09`, BakaSU `1744c140a08b233daf3b71801994b9b197318ef0`. The corresponding profile is recorded by SUSFS commit `897ee7e2f922c39b5e3183b6a99235a0f423a1cc`; the final profile has identical patch bytes.
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

## Latest upstream changes

All five new commits are merged, including their GKI patch files. The upstream core files under `kernel_patches/fs/` and `kernel_patches/include/` are unchanged from `ca7093a1`. The inherited 5.4 core therefore remains the source for this profile.

| Upstream commit | Change and 5.4 treatment |
| --- | --- |
| `c06d5f8ef2b53d04c5e1c6b86dc3076f1e0e9f33` | Rebase GKI patch context onto android12-5.10.257. This profile uses the independently pinned 5.4.302 OEM baseline; its exec include and fdinfo inode field adaptations are described above. |
| `31eb14add587b0a089dfe1819f92cc94920e141e` | Keep original and hidden SELinux SID tables synchronized. BakaSU `kernel/feature/selinux_hide.c`, `ksu_security_context_to_sid()`, parses both contexts and invokes `sidtab_context_to_sid()` on both tables; context-hash checks remain in the live and backup paths. No additional host hook is required. |
| `5a3af83ef589eb1e19dc48550a9eb59fff1facdf` | Sync the official KernelSU architecture, including its PID 1 preinit runner. BakaSU retains its own startup architecture, described below. Its existing exec/read/fstat/post-exec interfaces remain the host contract. |
| `e24d1726e23d9f6915b04fd89fd79d8b5bc20139` | Reuse native `my_setprocattr`, `my_write_context` and `my_write_access` instead of duplicate GKI helpers. BakaSU owns those native hiding paths in `kernel/feature/selinux_hide.c`; do not add GKI wrappers to host `hooks.c` or `selinuxfs.c`. |
| `f43926dc94b8ffbf9b74321313536600f69367b1` | Sync official Kconfig and init.rc patch context. `fs/susfs.Kconfig` already defaults SUS_KSTAT and OPEN_REDIRECT to `y`, and the MIX4 build explicitly enables both. The ARM64 port uses its own inline hook glue, so the removed x86 dispatcher Kconfig context is inapplicable. |

The official KSU functions `ksu_setup_preinit_file()` and `ksu_preinit_handle_post_execveat()` execute an embedded runner before PID 1 `/system/bin/init selinux_setup`. On failure they close its fd, restore the original init target and retry exec. BakaSU has no equivalent runner or retry state machine. This is an architecture difference; the profile preserves BakaSU's original startup capabilities and adds neither those symbols nor placeholder stubs.

In BakaSU `kernel/feature/sucompat.c:425`, `ksu_handle_execveat_init()` explicitly requires `current->pid != 1`; it handles an init child executing ksud. Its `ksu_handle_post_execve()` at line 404 installs the su-session fd, rather than recovering a PID 1 runner. Startup services and module rc instead use `kernel/runtime/ksud_integration.c`: second-stage detection at line 261, `KERNEL_SU_RC` at line 53, `load_module_rc_once()` at line 386, fstat at line 690, init.rc at line 717 and the read entry at line 781. `userspace/ksud/src/android/module/mod.rs:520`, `regenerate_preinit_rc()`, generates the metadata `modules.rc`. These paths require runtime verification on the new candidate.

## Reproduce application and reversal

The verifier reads the evidence kernel repository and creates a disposable scratch repository. It checks all 28 baseline blobs and modes, invokes the kernel's application helper twice, checks postimages and index preservation, then reverses the patch and compares the complete baseline tree and file bytes:

```sh
python3 /absolute/path/to/this/profile/verify_roundtrip.py \
    --kernel-repo /path/to/kernel
```

Use `--kernel-ref COMMIT` to verify a later OEM host whose affected preimages match the manifest. The reference must contain `kernel-patches/apply-susfs.py`. The source kernel tree is not modified.

The exact OEM baseline passed first application, repeat skip, postimage checks, real-index preservation and reverse restoration. Its baseline tree is `014ac9ab6bf6988915ae3a2d35464b7b95c5e247`; the applied tree is `2de792b5aa9affb62eac6bcf962a4c23e14ffba6`. The same evidence applies to the final upstream profile because its patch and all 28 pre/postimages remain unchanged.

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
