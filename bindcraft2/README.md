# BindCraft2

Status: **assessment only — container build and checks pending**. This folder currently holds installation decisions; there is no BindCraft2 Dockerfile, workflow or published image in this repository yet.

Requested by Dan. Scope: a reasonable best-effort installation with useful checks without a GPU, then handover to the requester for the actual GPU workload test. Follow the shared [installation policy and HPC profile](../HPC_COMPATIBILITY.md).

## Installation choice

Use **CUDA 12 explicitly** for the initial build. Upstream supports the `cuda12` extra (including matching JAX and cuEquivariance packages). Its installer otherwise defaults to CUDA 13 when no GPU/driver is visible, so do not rely on autodetection during a CPU-only build. Adapt the upstream container to install `.[cuda12]`; if using its installer, specify `bash install.sh cuda12`.

Reviewed on 2026-10-13: the upstream `main` branch's package metadata reports `bindcraft` version 1.0.3, Python >=3.12 and JAX >=0.11,<0.12. Pin a release/commit and the resolved environment when implementing the container. Sources: [package requirements](https://github.com/PacesaLab/BindCraft2/blob/main/pyproject.toml), [installation guide](https://github.com/PacesaLab/BindCraft2/blob/main/docs/source/installation.md).

## Driver coverage

JAX documents Linux driver minimums of **525 for CUDA 12** and **580 for CUDA 13**. CUDA 12 is the conservative choice across potentially mixed driver versions; it is not compatible with arbitrarily old drivers. Check the resolved dependencies for any stricter requirements when building. [JAX requirements](https://docs.jax.dev/en/latest/installation.html)

| Node | GPUs | Recorded driver | Current evidence |
| --- | --- | --- | --- |
| tsl1024n1 | 2 × A100 | Unknown | Driver compatibility provisional |
| tsl2048n2 | 4 × A100 PCIe 80 GB | 580.95.05 | Meets JAX's CUDA 12 and CUDA 13 driver minimums |
| tsl2048n3 | 4 × A100 | Unknown | Driver compatibility provisional |

Use the [zero-GPU inspection loop](../HPC_COMPATIBILITY.md#gpu-information-without-reserving-a-gpu) to fill the two gaps. This requires no GPU reservation and does not prevent build preparation. Retain CUDA 12 unless evidence from **all three** nodes supports moving to CUDA 13. A job requesting only `-p tsl-gpu --gres=gpu:1` can land on any eligible node, so n2's driver alone does not establish partition-wide compatibility.

An explicit `--nodelist=tsl2048n2` would permit a CUDA 13 candidate to target the verified driver, but makes only 4 of the partition's 10 configured GPUs eligible. This is an optional tradeoff, not the default. Do not describe an unrestricted job as compatible with all three nodes until their drivers meet the selected stack's requirements.

## Checks and handover

Build for Linux x86_64 and run supported package/dependency checks, CPU-side imports, CLI startup and upstream checks that do not require a GPU. Check operation as an unprivileged user with a read-only image and offline runtime. Record the exact checks and results here when implemented.

Prepare the weights on software23 before handing over an offline Slurm example. Keep weights, inputs, outputs and caches under the site's default-mounted `/tsl` or `/hpc-home` paths. The requester owns the GPU workload run; no repeat test of the established AlphaFold installation is needed.

Historical packaging reference: [the site's AlphaFold 3.0.0 image](../references/alphafold3.md). Its older dependency versions are reference information, not the BindCraft2 dependency specification.
