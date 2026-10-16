# SUSFS 2.3.0 for the published MIX4 Linux 5.4 tree

Apply `series` at the kernel repository root to restore the SUSFS source used by `kernel_xiaomi_odin` commit `df2522bc7b7458012e53a108f1c8238581cdeeb0`. The series contains one standard Git patch covering 28 files (23 modified, 5 added). It includes the core, feature Kconfig and the inline host hooks; no separate copy step is needed.

## Pins and baseline

- SUSFS: `82f08351fadb8b19dd6591bd14634d02ad832145`, upstream `gki-android12-5.10`, <https://gitlab.com/simonpunk/susfs4ksu.git>.
- Kernel before the initial integration: `f24f331d4b8de9903fd019a4bea9e425f4de4477` in <https://github.com/kafuuchino-s/kernel_xiaomi_odin.git>. This is the parent recorded by integration commit `597abcfc140528fd6b17612d1613f2e457d0bbe4`.
- Effective kernel source: `df2522bc7b7458012e53a108f1c8238581cdeeb0`. The patch uses these final blobs, including the later uname buffer-length fix.
- Paired BakaSU: `08966cd0574d898a678a9bbe9a3ea0270e71ea6e`, with the separate MIX4 5.4 BakaSU adaptation, including the sidtab context-hash fix.

For integration, the **stripped release baseline** means the release tree with exactly the paths in `files.list` restored to their pre-SUSFS blobs and modes, or removed when `manifest.json` records a null baseline. Every other release path stays in place. It is not a checkout of the entire older OEM commit. Applying this patch to that baseline restores the complete release tree byte for byte, including Git file modes.

The old `security/selinux/hooks.c` and `security/selinux/selinuxfs.c` wrappers were removed by kernel commit `81c2c29e2c2349fa6cf8547f5b85f033577f592f`; BakaSU now owns those interfaces. Keep the release versions of both files, including their whitespace and modes. The active SUSFS audit hook in `security/selinux/avc.c` is included here. `include/linux/odin_ksu_hooks.h` and all of its current host callers are included as the paired inline-hook interface.

The patch does not alter BakaSU contents or its glue patch, `drivers/Kconfig`, `drivers/Makefile`, `drivers/kernelsu`, the OEM reconstruction, frozen banner, ROM configuration, build scripts, or submodule pins. Those remain kernel/BakaSU integration responsibilities. Keep `CONFIG_KSU=y`, `CONFIG_KSU_SUSFS=y` and the desired features in the kernel configuration. The BakaSU configuration supplies the top-level `KSU_SUSFS` option; this series supplies its feature menu.

`kernel_patches/` remains the upstream 5.10 material. For this 5.4 port, use only `patches/5.4/2.3.0/series`; do not also apply the upstream KernelSU patch to BakaSU.

## Apply and remove

Set an absolute path to this directory, then run from the kernel repository root:

```sh
SUSFS_PATCHES=/absolute/path/to/susfs4ksu/patches/5.4/2.3.0
while IFS= read -r patch; do
    git apply --check "$SUSFS_PATCHES/$patch" &&
    git apply "$SUSFS_PATCHES/$patch" || exit 1
done < "$SUSFS_PATCHES/series"
```

To strip the existing tree before switching to build-time application:

```sh
tac "$SUSFS_PATCHES/series" | while IFS= read -r patch; do
    git apply --reverse --check "$SUSFS_PATCHES/$patch" &&
    git apply --reverse "$SUSFS_PATCHES/$patch" || exit 1
done
```

`series` contains one patch filename per line, relative to its directory. `files.list` is the exact touched-path list; `manifest.json` records before/after blob IDs, SHA-256 values, lengths and modes for every path.

## Reproduce the byte-level proof

Use a kernel Git repository containing both recorded kernel commits. For a shallow checkout missing only the OEM baseline, fetch that exact commit into the verification clone:

```sh
git -C /path/to/kernel-evidence fetch --depth=1 \
    https://github.com/kafuuchino-s/kernel_xiaomi_odin.git \
    f24f331d4b8de9903fd019a4bea9e425f4de4477
python3 "$SUSFS_PATCHES/verify_roundtrip.py" \
    --kernel-repo /path/to/kernel-evidence \
    --work-dir /path/to/new-scratch-directory \
    --report /path/to/local-roundtrip.json
```

The script reads the evidence repository without modifying it. It creates a new scratch repository with the complete release index and checks out only the 28 touched paths. It checks reverse application, compares the resulting files directly against the independent OEM-baseline blobs, checks application, compares the files directly against the release blobs, and verifies that the **entire** resulting Git tree equals the release tree. A final reversal must reproduce the same stripped baseline tree. The full index comparison also protects all unlisted SELinux and BakaSU paths.

The expected tree identities are:

| State | Git tree |
| --- | --- |
| Published release / reapplied series | `3a17e0e0c5bfe3ec97fa2beb6bae3d11667a834f` |
| Stripped release / reversed series | `5f981f90ee693b2f05f9e64672cd9486a39adc0e` |

This extraction proves source equivalence. The integrating kernel owner performs compilation, ABI gates and release validation.
