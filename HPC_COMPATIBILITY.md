# HPC profile and software compatibility

> **Scope: the TSL / NBI HPC only** (`hpc.tsl.ac.uk`, Slurm, Apptainer 1.4.5). Every command, path and rule in this repository assumes that cluster. Another site needs its own profile in this file before any guide here applies to it.

Purpose: make each new tool work on our cluster with the least unnecessary setup. Reuse confirmed facts here instead of asking the same questions for each container. Do not infer compute-node capabilities from a Mac or a login node.

## Agreed scope for GPU installations

RC normally handles GPU installations for the group, according to the user. For installs undertaken here, aim for a working image quickly: check compatibility, build, and run useful supported checks without a GPU. Fix failures, then hand over the image, data/weights setup and an example Slurm job. **The requester owns the GPU workload test.** GPU queue availability is not a delivery gate.

Use **ready for requester testing** once the build and relevant available checks pass. Record the checks actually run; accept reported successful use of existing site software without requiring repeated validation.

## TSL / NBI cluster profile

Updated 2026-10-13 from the user's Obsidian note `Code/Infrastructure & Tech/Install & HPC/HPC Guide/TSL HPC specifications.md` and supplied cluster-command output. **Checked** means a live check reported by the user; **older notes** means not recently re-checked. GPU nodes are separate Slurm resources. Existing AlphaFold installations provide evidence of successful GPU container use; the AF3 build history and package inventory are in the [AlphaFold reference](references/alphafold3.md).

| Property | Evidence and current value |
| --- | --- |
| Cluster | TSL / NBI shared HPC; `hpc.tsl.ac.uk` and `slurm.nbi.ac.uk` are recorded as login aliases (older notes) |
| CPU architecture | x86_64; tested node Intel Xeon E5-2630 v4 / Broadwell with AVX2 (checked). Mixed Intel/AMD cluster (older notes); do not extrapolate this CPU to every partition |
| Operating system / kernel | AlmaLinux 9.8 (checked); kernel 5.14.0-687.54.1.el9_8 on GPU nodes; Slurm 23.02.8 (checked via `scontrol`, 2026-10-13) |
| Container runtime | Prefer **`ml load apptainer` → Apptainer 1.4.5** (checked; module `apptainer/1.4.5-2` successfully started the existing AF3 image for Python/package inspection). Default Singularity is 3.8.7; after loading the module, `singularity` also resolves to Apptainer |
| Scheduler | Slurm / Lmod. CPU partitions include `tsl-short`, `tsl-medium`, `tsl-long`, `tsl-interactive` (older notes) |
| GPU partition | `tsl-gpu` (checked via Slurm 2026-10-13). Request `--gres=gpu:a100:N` (or `gpu:N`); use Apptainer `--nv` within the allocation. Nodes: tsl1024n1 — 32 cores (2×16, no hyperthreading), ~1 TB RAM, 3.5 TB local SSD; tsl2048n2/n3 — ~2 TB RAM, 5.9 TB local SSD. Local SSD is exposed as a Slurm GRES (`ssd`) with `TmpDisk=0`; how jobs should use it is unknown |
| GPU inventory | A100: tsl1024n1 ×2, tsl2048n2 ×4, tsl2048n3 ×4 (checked via Slurm, 2026-10-13). **tsl2048n2: A100 PCIe 80 GB, NVIDIA driver 580.95.05** (checked, PCI ID `10de:20b5` + `/proc/driver/nvidia/version`). Match the software's driver requirement to every node eligible for its job. tsl1024n1 and tsl2048n3 variant/driver unchecked — don't assume the same. `RealMemory` is system RAM, not GPU memory |
| Internet | **No internet on submission or compute nodes. Use `software23` for image pulls, packages, and model/data downloads** (checked). GitHub Actions can still build externally |
| User bind mounts | **`--bind` reported disabled**; `/hpc-home` and `/tsl` reported as default mounts (older notes). Avoid custom binds; verify visibility in the first container test. New mounts require site support |
| Temporary storage | `/tmp` is only **5 GB**, `$TMPDIR` unset (checked). Set container caches and temporary paths under `/tsl/scratch/$USER` before pulling |
| Scratch | `/tsl/scratch`: 77 TB volume, 38 TB free at the note's check; up to 3 TB per user from older notes. Usage changes; check quota/free space. Not backed up |
| Persistent SIFs/results | `/hpc-home` or a suitable `/tsl` location visible to jobs. Home quota unrecorded; retain needed results/SIFs outside purgeable scratch |
| Shared software installs | User's current convention: `/tsl/software/testing/<Software>/<version>/x86_64/` (reported 2026-10-13; flexible). Prefer this for shared SIF installations when writable; keep download/conversion and per-user job caches on scratch. Shared weights may live alongside the SIF or in an existing shared model directory; settings/results belong in users' project directories |
| Shared software loading | User-provided site guide: install executables/launchers in `x86_64/bin`, then use `create-software-testing-wrapper <Software>-<version>` to register a sourced loader in `/tsl/software/testing/bin/` and catalogue metadata in the version directory. Users run `source <Software>-<version>` (or the full loader path). `create-tsl-testing-wrapper` is a self-service alternative requiring write access, with `--from`, `--desc` and `--categories` options. Preserve the site template and add application dependencies/PATH in its app-specific section |
| CPU/RAM allocation | Match job requests to the intended workload; available limits not yet recorded |
| MPI / local image builds | MPI integration unverified. Whether fakeroot builds work on software23 is unknown; pulling our published Docker images avoids needing a local Dockerfile build |

Do not use the software node for full analyses. The note identifies it as non-submittable to Slurm; run analyses in compute allocations. The report that downloads work on software23 is not evidence that login or GPU nodes have internet.

## GPU information without reserving a GPU

**Use a CPU-only Slurm job on each GPU node.** Reading `/proc/driver/nvidia/version` and `lspci -nn` with `--gres=gpu:0` worked on tsl2048n2 on 2026-10-13 while its GPUs were busy. It revealed driver 580.95.05 and PCI ID `10de:20b5` (recorded as A100 PCIe 80 GB). Run this loop from a submission node outside an existing job to inspect all three nodes:

```bash
for node in tsl1024n1 tsl2048n2 tsl2048n3; do
    printf '\nNode: %s\n' "$node"
    if ! srun -p tsl-gpu -w "$node" --gres=gpu:0 \
        --nodes=1 --ntasks=1 -c1 --mem=500M -t 00:02:00 --immediate=10 \
        bash -c 'set -euo pipefail; cat /proc/driver/nvidia/version; lspci -nn | grep -i nvidia'; then
        printf 'Inspection failed or resources unavailable on %s; leave it unverified.\n' "$node" >&2
    fi
done
```

This reserves a small amount of CPU/RAM, **zero GPUs**, and does not access GPU devices or run GPU kernels. CPU availability and scheduler policy still apply: `--immediate=10` stops an allocation attempt after ten seconds if resources are unavailable, then the loop tries the next node. The loop has not been run here; n1 and n3 remain unchecked until their output is recorded. A failed inspection is not evidence of an old driver.

The driver version is read directly. PCI IDs identify GPU variants and can establish nominal VRAM when mapped to a known model; `lspci` does not measure usable/free GPU memory. `nvidia-smi` may see no devices in this zero-GPU job because Slurm hides unrequested GPUs. If this method fails, use a colleague's existing allocated-job output or ask RC for just the missing facts.

For scheduler inventory only, no allocation is needed:

```bash
sinfo -p tsl-gpu -N -o '%N|%G|%f|%m'
scontrol show node tsl1024n1
```

These expose configured GPU counts/types and host RAM (`%m`), not normally the driver or VRAM. Do not infer a host driver from a CUDA module, an installer filename or an older working container. Choose a software stack supported across the intended nodes; a job without a node restriction can land on any eligible node. Document any deliberate node restriction and its capacity cost in the tool's README.

References: [Slurm srun](https://slurm.schedmd.com/srun.html), [sinfo](https://slurm.schedmd.com/sinfo.html), [scontrol](https://slurm.schedmd.com/scontrol.html).

## Optional GPU inspection for the requester

When the requester has a GPU allocation, they can record the visible hardware with:

```bash
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
```

For their GPU application job, request `-p tsl-gpu --gres=gpu:N`, load Apptainer, use `--nv`, and preserve Slurm's non-empty device assignment with `--env CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:?Run inside a GPU allocation}"` when using `--cleanenv`. Their example job should verify the framework selects a GPU before the full workload. Host drivers are not replaced by container libraries. See the [job guide](ADDING_NEW_CONTAINER_GUIDE.md#compute-node-test-and-job-examples).

## TSL storage and execution rules

- Pull SIFs and fetch weights on **software23** after loading Apptainer and setting scratch cache/temp paths. Follow the commands in the adding guide.
- Keep settings, input, output, weights, and writable application caches under the default-mounted `/hpc-home` or `/tsl` trees. Pass their absolute paths and check symlink destinations too.
- Do not add `--bind` or relocate project data to `/data` or `/work` in TSL job examples. Use `--pwd` with the real mounted working directory if the image sets its own working directory.
- Set a job-specific `$TMPDIR` under scratch and pass it into a clean container environment when the application needs temporary space. Neither `/tmp` nor home quota should be assumed sufficient for large model images.
- **CPU features:** GPU nodes advertise `xeon,nht,sse4,avx2,avx512,nps` (checked via Slurm, 2026-10-13), so `#SBATCH --constraint=avx2` (or `avx512`) is a real feature name there. Check a CPU partition before relying on it: `sinfo -p tsl-medium -N -o '%N|%f'` — the Broadwell node checked earlier has AVX2 but no AVX-512. Prefer generic x86_64 builds where possible.

## Check every new piece of software

Record the following in `tool-name/README.md`, linking to upstream requirements and the version reviewed. The [adding guide](ADDING_NEW_CONTAINER_GUIDE.md) covers build and job commands.

- **Install:** prefer a maintained upstream image or prebuilt Linux package; verify architecture and version, pin the recipe, and avoid `-march=native` on a CI runner.
- **Compatibility:** check CPU flags, kernel requirements, GPU/driver requirements across eligible nodes, and any MPI integration. An x86_64 label alone does not establish CPU compatibility.
- **Runtime:** use the HPC user's UID, a read-only image, site-mounted writable storage and direct `exec` commands; check activation hooks. Jobs must not need root, a Docker daemon or package installation.
- **Data/resources:** estimate CPU, RAM, storage and temporary space; pre-fetch databases/weights, and check relevant licences.
- **Evidence/handover:** record the image digest, checks run and results. For GPU installs, build and test without a GPU where supported, then give the requester a small workload example with expected output. The installer does not need to run inference before delivery.

Use **candidate — build/checks pending**, **CI smoke test passed**, **ready for requester testing**, or **HPC sample analysis passed** as appropriate. Ask for more facts only when they affect an installation choice that cannot reasonably be resolved from existing evidence.
