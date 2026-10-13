# BindCraft2 on TSL

Status: **ready for requester testing — native x86_64 build, offline CI checks, shared TSL loader, CLI startup and CPU installation check passed; shared AF2 parameters downloaded and checked**. This is an unofficial container for the unmodified upstream code, prepared for Dan's request. The requester owns the actual GPU workload test; the installer checks compatibility, packaging and operation without a GPU.

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

## Install the TSL command launcher

Do this once on **software23**, after the SIF and weights are in place. There are two small scripts involved: the site's sourced loader, `BindCraft2-1.0.3`, makes the software available; our executable [bin/bindcraft](bin/bindcraft) launches the container. Use the existing TSL wrapper generator for the sourced loader and catalogue metadata.

**No Git checkout or installer script is required.** Download the tested launcher and two example files directly into the existing installation. This block stages the downloads before installing them and stops if any download fails:

```bash
(
    set -e
    install_dir="/tsl/software/testing/BindCraft2/1.0.3/x86_64"
    base="https://raw.githubusercontent.com/georgedeeks/bio-containers/4ed42aef3fbb885c365d50763691d85ea953d525/bindcraft2"
    staging=$(mktemp -d)
    trap 'rm -rf -- "$staging"' EXIT
    curl -fL --retry 3 "$base/bin/bindcraft" -o "$staging/bindcraft"
    curl -fL --retry 3 "$base/run-wrapper.slurm" -o "$staging/run-wrapper.slurm"
    curl -fL --retry 3 "$base/example-settings.json" -o "$staging/example-settings.json"
    install -d -m 755 "$install_dir/bin" "$install_dir/examples"
    install -m 755 "$staging/bindcraft" "$install_dir/bin/bindcraft"
    install -m 644 "$staging/run-wrapper.slurm" "$staging/example-settings.json" "$install_dir/examples/"
)
```

Then register the software with the site's self-service creator. The command below uses the maintainer's source copy, which was used for the successful installation:

```bash
chmod -R a+rX /tsl/software/testing/BindCraft2/1.0.3/x86_64
bash "$HOME/my-software-wrapper/bin/create-tsl-testing-wrapper" \
    BindCraft2-1.0.3 \
    --desc "BindCraft2 protein binder design (Apptainer, CUDA 12)" \
    --categories "alphafold"
```

For maintainers who already have a repository checkout, `bash bindcraft2/install-launcher.sh` is an optional way to copy the same files. It is not needed for the direct-download setup above.

Once the fixed creator is deployed to `/tsl/software/testing/bin/`, `create-tsl-testing-wrapper` can be used instead of the explicit source path. The HPC team's `create-software-testing-wrapper` is another site option. Choose one generator; edit an existing loader rather than forcing its replacement. The generator writes the central loader under `/tsl/software/testing/bin/` and catalogue metadata in the version directory. See the [wrapper maintenance notes](../references/tsl-software-wrappers.md) for the fixes and source/deployment distinction.

Open `/tsl/software/testing/bin/BindCraft2-1.0.3` and make its app-specific section look like this, retaining the existing `source hpccore-5` line once. The location messages follow the user's successfully tested loader:

```bash
source hpccore-5
ml load apptainer || return 1

echo 'Installation: /tsl/software/testing/BindCraft2/1.0.3/x86_64/'
echo 'Launcher:     bin/bindcraft'
echo 'Container:    bindcraft2.sif'
echo 'AF2 weights:  weights/alphafold/'
echo "Per-user caches and temporary files go under ${BINDCRAFT_SCRATCH_ROOT:-/tsl/scratch/$USER}/"

# Python, CUDA libraries and ProteinMPNN weights are inside the SIF.
# The launcher supplies the external AF2 weights and per-user cache paths.
export PATH="/tsl/software/testing/BindCraft2/1.0.3/x86_64/bin:$PATH"
```

Preserve the site's header/footer sections. `bin/bindcraft` is a shell launcher, not a self-contained executable: keep `bindcraft2.sif` and `weights/alphafold/` beside `bin/`. No host Python or CUDA library paths are needed. This setup does not modify the SIF or re-download weights. Users then load and check the software with:

```bash
source /tsl/software/testing/bin/BindCraft2-1.0.3
command -v bindcraft
bindcraft --help
bindcraft --check-install
```

`command -v` should show `/tsl/software/testing/BindCraft2/1.0.3/x86_64/bin/bindcraft`. Where the central testing directory is already on `PATH`, `source BindCraft2-1.0.3` is equivalent; the user confirmed that command followed by `bindcraft --help` worked. The installation check runs the existing CPU smoke test plus checks for the externally staged AF2 parameters; it needs no GPU. It took **5 minutes 26 seconds** on the reported run and can be quiet between stages. Run it after installation or relevant changes, not whenever someone loads the software. A non-fatal Matplotlib cache fallback was observed; see [Build and checks](#build-and-checks).

The launcher supplies the shared AF2 path, a per-user Matplotlib/JAX cache and a temporary working directory on scratch. It keeps the caller's working directory and arguments, limits BindCraft2 to one worker by default, and requires a Slurm GPU assignment for design/scoring and `--check-gpu`. Help, preset listings and `--check-install` use the CPU. GPU commands use `--nv`, preserve Slurm's device assignment and require JAX's CUDA backend. [Apptainer environment handling](https://apptainer.org/docs/user/1.4/environment_and_metadata.html) and [GPU support](https://apptainer.org/docs/user/1.4/gpu.html).

Optional host overrides: `BINDCRAFT_AF2_PARAMS` selects another existing parameter directory; `BINDCRAFT_SCRATCH_ROOT` selects writable scratch under a site-mounted path (default `/tsl/scratch/$USER`). Worker counts can be changed with `BINDCRAFT_WORKERS_PER_GPU` and `BINDCRAFT_DESIGN_WORKERS` when the requester has sized their workload appropriately.

## Requester's first GPU run

After the launcher is installed, copy the shared [run-wrapper.slurm](run-wrapper.slurm) and [example-settings.json](example-settings.json) into a new writable project directory under `/tsl` or `/hpc-home`. From that directory on the submission node:

```bash
install_dir="/tsl/software/testing/BindCraft2/1.0.3/x86_64"
cp -n "$install_dir/examples/run-wrapper.slurm" \
    "$install_dir/examples/example-settings.json" .
sbatch run-wrapper.slurm "$PWD/example-settings.json"
```

The example requests one A100, four CPU cores, 32 GB RAM and two hours. It loads the site wrapper, runs `bindcraft --check-gpu` to check weights and execute a small JAX computation on CUDA, then runs `bindcraft design` with the settings file. The launcher supplies caches, weights and the Slurm GPU assignment. Adjust resources for the real campaign. This is a starting allocation, not a measured completion-time guarantee.

The supplied settings use upstream's shipped human PD-L1 target and a short 60-residue binder, with at most two trajectories and `trajectory_only: true`. Inspect `bindcraft2-<jobid>.out`: expect `PASS: JAX CUDA computation and shared checkpoint checks`, followed by a design run without a traceback, and campaign metadata/logs and trajectory output under `results/installation_check`. Two attempts may yield no accepted design; acceptance is not the installation pass criterion.

For normal use, submit the same script with the requester's own settings:

```bash
sbatch run-wrapper.slurm "$PWD/my-settings.json"
```

Set a distinct output directory for each campaign, choose the real target/design settings, turn off `trajectory_only` for a full campaign, and adjust the script's resource/time requests. Inside an already allocated GPU job the command is simply `bindcraft design my-settings.json`. Help and preset discovery, such as `bindcraft design --list-targets`, can run without a GPU.

For a custom target, give `target_path` an absolute container-visible path and keep outputs in writable site storage. See [upstream usage](https://github.com/PacesaLab/BindCraft2/blob/c0ee638d11bc010817c2c97ee58ed5c323e664e2/docs/source/installation.md). The original [run.slurm](run.slurm) remains available for direct container use without the site loader; its arguments are the absolute SIF, AF2 parameter directory and settings JSON paths.

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

**Weights result, user-reported 2026-10-13:** `bindcraft fetch-weights` downloaded and extracted the 5.3 GB AlphaFold parameter archive to `/tsl/software/testing/BindCraft2/1.0.3/x86_64/weights/alphafold`, then reported that directory and the packaged ProteinMPNN directory successfully. This command checks that the required AF2 and all three ProteinMPNN checkpoint variants exist and meet upstream's minimum file sizes. Shared weight staging is complete; the requester's Slurm job uses the paths above.

**Shared launcher result, user-reported 2026-10-13:** the site's `create-tsl-testing-wrapper` created `/tsl/software/testing/bin/BindCraft2-1.0.3` and its clean-shell sourcing check passed. After configuring the application-specific section, `bindcraft --check-install` completed in **5 minutes 26 seconds**, reporting both the packaged smoke-test PASS and `PASS: shared AlphaFold and ProteinMPNN checkpoint files found.` This verifies the shared launcher, container CPU checks and external checkpoint file checks together. Installation checks are complete for the agreed best-effort scope; the requester owns the first GPU workload test.

Matplotlib still reported `/tsl/scratch/deeks/bindcraft2-cache/matplotlib` as unwritable despite the launcher's explicit `MPLCONFIGDIR`. It successfully used a temporary cache under the launcher's per-invocation scratch directory, and both checks passed. The warning is non-fatal; persistent Matplotlib caching remains unresolved. Setting that same scratch cache path again is not a demonstrated fix, and the reported elapsed time does not establish that the cache warning caused the delay.

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

Host launcher checks: `python3 bindcraft2/test-wrapper.py` exercises installation into a directory containing spaces, CPU/GPU routing, refusal of unallocated GPU work, unchanged CLI arguments and device lists, shared/cache paths, temporary-file cleanup and error propagation using a recording Apptainer stub. These check launcher behavior; the actual shared-launcher HPC installation check is recorded above.

To update dependencies, check out the intended pinned upstream source, then run:

```bash
uv pip compile /path/to/pinned/BindCraft2/pyproject.toml bindcraft2/build-requirements.in \
    --extra cuda12 --python-version 3.12 --python-platform x86_64-manylinux_2_39 \
    --only-binary :all: --generate-hashes --no-annotate \
    --output-file bindcraft2/requirements.lock
```

Update the Dockerfile's commit and archive checksum together if changing source, rebuild and repeat the checks. The lock fixes Python distributions; the image digest fixes the complete built image, including Ubuntu packages.

Historical reference: [the site's AlphaFold 3.0.0 image](../references/alphafold3.md). Shared policy and site facts: [HPC_COMPATIBILITY.md](../HPC_COMPATIBILITY.md).
