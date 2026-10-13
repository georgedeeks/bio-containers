# BindCraft2 on TSL

Status: **ready for requester testing — native x86_64 build, offline CI checks and the SIF's CPU installation check on software23 passed**. This is an unofficial container for the unmodified upstream code, prepared for Dan's request. The requester owns the actual GPU workload test; the installer checks compatibility, packaging and operation without a GPU.

| Item | Value |
| --- | --- |
| Software | BindCraft2, Python package `bindcraft` 1.0.3 |
| Source | [Commit c0ee638](https://github.com/PacesaLab/BindCraft2/tree/c0ee638d11bc010817c2c97ee58ed5c323e664e2), fixed source-archive checksum in the Dockerfile |
| Image | `ghcr.io/georgedeeks/bindcraft2:latest`; use the Actions summary's digest for an exact image |
| Platform | Linux x86_64; Ubuntu 24.04 pinned by image digest; Python 3.12 in `/opt/venv` |
| Accelerator | Explicit CUDA 12; JAX 0.11.2, matching CUDA 12 plugin/PJRT and cuEquivariance ops |
| Dependencies | Hash-locked in [requirements.lock](requirements.lock); runtime inventory under `/opt/container-info/` |
| Models | ProteinMPNN checkpoints included; AlphaFold 2 parameters downloaded separately on software23 |
| Licence | Upstream [source-available licence](https://github.com/PacesaLab/BindCraft2/blob/c0ee638d11bc010817c2c97ee58ed5c323e664e2/LICENSE), retained at `/opt/bindcraft/LICENSE`; model/dependency licences remain separate |

Packaging changes from the upstream Dockerfile: CUDA 12, an isolated Python environment, pinned dependencies/source/base, additional offline checks, and direct `exec` usage for TSL. Upstream Python code is unchanged. The source tree stays at `/opt/bindcraft` because its editable installation needs the adjacent settings, structures and scaffolds.

## Pull the image and prepare weights

Run on **software23**. Use the shared install directory **`/tsl/software/testing/BindCraft2/1.0.3/x86_64/`**, following the site's software/version/architecture layout. You need write access while installing; requesters need read access to the SIF/weights and traversal access to their parent directories. This uses the site's default mounts, with no user `--bind`.

Keep Apptainer's download/conversion cache on scratch. The weights below live alongside the SIF: allow roughly 20 GB there for their download/extraction, plus space for the SIF. Upstream stages its weight archive beside the destination, even when `TMPDIR` points to scratch.

```bash
ml load apptainer
umask 022
install_dir="/tsl/software/testing/BindCraft2/1.0.3/x86_64"
sif="$install_dir/bindcraft2.sif"
export APPTAINER_TMPDIR="/tsl/scratch/$USER/apptainer-tmp"
export APPTAINER_CACHEDIR="/tsl/scratch/$USER/apptainer-cache"
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR" "$install_dir"
apptainer pull "$sif" \
    docker://ghcr.io/georgedeeks/bindcraft2@sha256:fa2adb249f2fbdfc3a0eccb77d958b432de04ea513f7fba95bb0a9970b54549b
apptainer exec --cleanenv "$sif" bindcraft --help
```

This pulls the exact image from the [successful publication run](https://github.com/georgedeeks/bio-containers/actions/runs/38424130232); anonymous registry access was verified. If access changes, see [registry authentication](../ADDING_NEW_CONTAINER_GUIDE.md#4-pull-and-run-on-the-hpc). For updates, use a new version directory or SIF filename. If you already pulled this image into `$HOME/containers/bindcraft2.sif`, move that existing file into `"$sif"` instead of downloading it again; its location is not baked into the image. Do not overwrite an existing installation.

Fetch and check the external AlphaFold 2 parameters once, without a GPU:

```bash
weights_root="$install_dir/weights"
mkdir -p "$weights_root"
apptainer exec --cleanenv --pwd "$PWD" \
    --env "TMPDIR=$APPTAINER_TMPDIR" --env "BINDCRAFT_WEIGHTS=$weights_root" \
    "$sif" bindcraft fetch-weights
```

The parameter directory passed to jobs is **`$install_dir/weights/alphafold`**. These shared files only need to be downloaded once; users keep their outputs and writable job caches elsewhere. Existing suitable AF2 parameters can be reused by passing their directory instead; AF3 model weights are a different model and are not used here. Compute jobs do not download weights.

## Requester's first GPU run

Copy [run.slurm](run.slurm) and [example-settings.json](example-settings.json) into a writable project directory under `/tsl` or `/hpc-home`. From that directory on the submission node:

```bash
install_dir="/tsl/software/testing/BindCraft2/1.0.3/x86_64"
sbatch run.slurm "$install_dir/bindcraft2.sif" \
    "$install_dir/weights/alphafold" \
    "$PWD/example-settings.json"
```

The example requests one A100, four CPU cores, 32 GB RAM and two hours. It limits BindCraft2 to one worker, preserves Slurm's GPU assignment through `--cleanenv`, places caches/temp files on scratch, checks all weights and requires JAX to select a GPU before starting. Adjust resources for the real campaign. This is a starting allocation, not a measured completion-time guarantee.

The supplied settings use upstream's shipped human PD-L1 target and a short 60-residue binder, with at most two trajectories and `trajectory_only: true`. Expected results are a successful CUDA device check, campaign metadata/logs and trajectory output under `results/installation_check`. Two attempts may yield no accepted design; acceptance is not the installation pass criterion. For a full campaign, use the requester's settings and turn off `trajectory_only`.

For a custom target, give `target_path` an absolute container-visible path and keep outputs in writable site storage. Discover available presets with `apptainer exec --cleanenv "$sif" bindcraft design --list-targets`. See [upstream usage](https://github.com/PacesaLab/BindCraft2/blob/c0ee638d11bc010817c2c97ee58ed5c323e664e2/docs/source/installation.md).

## Driver coverage

CUDA 12 is selected explicitly rather than relying on the installer's no-GPU default of CUDA 13. JAX documents Linux driver minimums of **525 for CUDA 12** and **580 for CUDA 13**; CUDA 12 is not a guarantee for arbitrarily old drivers. [JAX requirements](https://docs.jax.dev/en/latest/installation.html)

| Node | GPUs | Recorded driver | Evidence |
| --- | --- | --- | --- |
| tsl1024n1 | 2 × A100 | Unknown | Driver compatibility provisional |
| tsl2048n2 | 4 × A100 PCIe 80 GB | 580.95.05 | Meets the selected JAX driver requirement |
| tsl2048n3 | 4 × A100 | Unknown | Driver compatibility provisional |

The [zero-GPU inspection loop](../HPC_COMPATIBILITY.md#gpu-information-without-reserving-a-gpu) can fill the two gaps. Retain CUDA 12 unless all eligible nodes support a different stack. The example job can land on any eligible A100 node; an explicit `sbatch --nodelist=tsl2048n2 ...` restricts it to the verified driver but reduces eligibility from ten configured GPUs to four.

## Build and checks

Verified on 2026-10-13 on GitHub's native Ubuntu 24.04 x86_64 runner: the image built successfully and the complete smoke test passed as UID/GID 10001, with networking disabled, a read-only root filesystem and only `/tmp` writable. [Initial validation run](https://github.com/georgedeeks/bio-containers/actions/runs/38421677693). The publication workflow repeats these checks before uploading an image. AlphaFold 2 weights are staged separately; no GPU allocation was used for these installation checks.

**HPC result, user-reported 2026-10-13:** the published image was pulled to the shared installation path above, and `apptainer exec --cleanenv "$sif" bindcraft2-smoke-test` passed on software23 with Apptainer 1.4.5-2. It reported BindCraft2 1.0.3, JAX/CUDA 12 plugin/PJRT 0.11.2 and cuEquivariance ops 0.11.1; CPU JIT, CUDA library loading, packaged weights, presets and CLI startup passed. This check covers the packaged ProteinMPNN weights; external AF2 parameter setup is separate.

Matplotlib reported an unwritable home configuration directory and successfully used a temporary fallback. For subsequent installation checks, give it a persistent writable cache on scratch, as the Slurm script already does:

```bash
mpl_cache="/tsl/scratch/$USER/bindcraft2-cache/matplotlib"
mkdir -p "$mpl_cache" &&
apptainer exec --cleanenv --env "MPLCONFIGDIR=$mpl_cache" \
    "$sif" bindcraft2-smoke-test
```

From this repository's root:

```bash
docker buildx build --platform linux/amd64 --load \
    -t bio-containers/bindcraft2:local bindcraft2
docker run --rm --platform linux/amd64 --network none --read-only \
    --user 10001:10001 --tmpfs /tmp:rw,exec,size=256m \
    --workdir /tmp --env HOME=/tmp bio-containers/bindcraft2:local
```

The default command runs [smoke-test.py](smoke-test.py). It checks dependency consistency and imports, CUDA 12 package selection and dynamic-library loading, a small JAX CPU JIT calculation, the three packaged ProteinMPNN checkpoints, upstream's shipped-weight self-check, CLI startup and preset/structure paths. `JAX_PLATFORMS=cpu` is set only inside the test process. Normal jobs retain GPU support; the Slurm example requires CUDA explicitly.

The GitHub workflow repeats the offline, read-only, non-root check before publishing `latest` and `sha-<commit>`. The default `apptainer run` also runs the installation check; use **`apptainer exec IMAGE bindcraft ...`** for software commands.

To update dependencies, check out the intended pinned upstream source, then run:

```bash
uv pip compile /path/to/pinned/BindCraft2/pyproject.toml bindcraft2/build-requirements.in \
    --extra cuda12 --python-version 3.12 --python-platform x86_64-manylinux_2_39 \
    --only-binary :all: --generate-hashes --no-annotate \
    --output-file bindcraft2/requirements.lock
```

Update the Dockerfile's commit and archive checksum together if changing source, rebuild and repeat the checks. The lock fixes Python distributions; the image digest fixes the complete built image, including Ubuntu packages.

Historical reference: [the site's AlphaFold 3.0.0 image](../references/alphafold3.md). Shared policy and site facts: [HPC_COMPATIBILITY.md](../HPC_COMPATIBILITY.md).
