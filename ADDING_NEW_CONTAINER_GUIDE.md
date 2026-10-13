# Add a new container quickly

Start in this repository's root. You need Python 3.8+ to generate the files and Git to push them. Docker is optional locally: GitHub Actions builds and tests the image. The HPC needs a working Singularity or Apptainer installation.

## 1. Check the software against the HPC

Read [HPC_COMPATIBILITY.md](HPC_COMPATIBILITY.md) and the software's official installation instructions. Check its Linux architecture, CPU instruction requirements, GPU/MPI needs, memory, and external databases. Prefer a maintained upstream image or prebuilt Conda package over compiling from source when it meets those requirements.

For GPU software, compare the driver requirement with every node eligible for its job. Use the profile's [zero-GPU inspection loop](HPC_COMPATIBILITY.md#gpu-information-without-reserving-a-gpu) to fill gaps, and select the accelerator stack explicitly during a CPU-only build. Keep tool-specific choices in the tool's README.

The current template targets **Linux x86_64, CPU-only, single-node tools**. It does not establish that an unknown GPU, MPI, ARM, or privileged application will work. Record unknowns in the tool's README and ask only for the cluster details that affect the choice. You can prepare/build a candidate while those details are pending.

**GPU installation scope:** build a suitable image and test it as far as practical without a GPU: package versions/dependencies, supported imports, command startup, and any upstream self-check that supports this mode. Fix failures in those checks. Once they pass, hand over the image, data/weights setup and an example Slurm command. The requester owns the GPU workload test; do not wait for a GPU allocation or require the installer to run inference before delivery. Record what passed and who will do the workload test in the tool's README.

## 2. Generate the files

Choose the actual Conda package version and executable from upstream documentation/package metadata. The executable need not match the package name.

```bash
# Example: a pinned Samtools package and its version command.
python3 scripts/new-tool.py samtools 'samtools=1.22.1' samtools --smoke-arg=--version
```

The script creates `samtools/Dockerfile`, `samtools/README.md`, and `.github/workflows/build-samtools.yml`, and refuses to overwrite an existing path. Replace the three positional arguments with your folder name, `package=version` (optionally `package=version=build`), and executable. `--smoke-arg` defaults to `--help`; use repeated `--smoke-arg=...` options for multiple arguments. For an extra channel, use `--channel channel-name`; qualify the package as `channel-name::package=version` when needed.

Then edit the tool's README to record its upstream source, requirements, and compatibility status. Review the generated Dockerfile:

- The official Miniforge base is pinned by digest. There is no separate installer download or certificate bypass.
- `--override-channels` and explicit channel ordering put conda-forge before Bioconda, with strict priority. Extra channels are tool-specific.
- The tool version is pinned. The full resolved environment is saved inside the image at `/opt/container-info/conda-explicit.txt` for inspection.
- Both `RUN` and `CMD` execute the smoke command: `RUN` tests the build; `CMD` supplies the default runtime check. Use a small offline test that exits zero on success. Never hide a failed test with `|| true`.
- `PATH` and `CONDA_PREFIX` select the environment for direct `exec` calls. If the package needs activation hooks or environment variables, add and test a wrapper for that tool.

The workflow builds `linux/amd64`, uses a per-tool cache, and runs the default command with no network, a read-only root filesystem, a temporary writable directory, and an arbitrary non-root UID. This catches common HPC startup problems before publishing. For GPU software, choose a startup check that is supported without a GPU; leave the real-data GPU run to the requester.

For software without a Conda package, keep the generated workflow and replace the Dockerfile installation with an official image, pinned release binary, or source build. Retain a real smoke test and direct execution through `singularity exec` / `apptainer exec`. Check the upstream image's entrypoint and architecture before reusing it.

### If copying a workflow manually

Use `templates/workflow.yml.tmpl`, replace **every** `__TOOL__` marker, and save it as `.github/workflows/build-your-tool.yml`. The tool name controls the context, cache, and image name. Both the tool folder and workflow filename must appear in **both** push and pull-request path filters. Never copy a different tool's image name unchanged.

## 3. Push and build

For the Samtools example, after filling in its notes:

```bash
git add samtools/ .github/workflows/build-samtools.yml
git diff --cached
git commit -m "Add samtools container"
git push
```

Pushes to `main` or `master` trigger the workflow when one of its watched paths changes. Pull requests targeting those branches build and test without publishing. **Only the repository's default branch publishes images**; merge a feature branch to that branch to publish. If your default branch has another name, update both branch filters.

For an unchanged tool, select its workflow under GitHub **Actions → Run workflow**. Choose the default branch to publish, or another branch to test only. Do not add dummy comments to force rebuilds. Manual runs can disable the build cache when diagnosing a cached installation.

After the first successful publication, check the package's visibility. GHCR packages start private. For anonymous pulls, make that specific package public in its package settings; a public Git repository does not automatically make its image public. Otherwise use the authenticated pull below.

### Keep the exact image

`latest` is convenient for trying a tool. `sha-<full-commit>` identifies a recipe revision, but rebuilding that commit can change dependencies and move its tag. The workflow's Actions summary includes an exact `docker://ghcr.io/...@sha256:...` pull command: save that digest with each analysis and retain its SIF. Pinning the main package and base does not freeze every transitive dependency or operating-system package. The environment manifest records the resolved packages; it is not a guarantee that those packages will always remain downloadable.

## 4. Pull and run on the HPC

These commands use Bash on **software23**, TSL's internet-enabled software node. Submission and compute nodes cannot pull images or download weights. Prefer the checked Apptainer module over the older default Singularity:

```bash
ml load apptainer
runtime=apptainer
"$runtime" --version
export APPTAINER_TMPDIR="/tsl/scratch/$USER/apptainer-tmp"
export APPTAINER_CACHEDIR="/tsl/scratch/$USER/apptainer-cache"
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR"
```

Set cache/temp paths **before** pulling: `/tmp` is only 5 GB. Pull once on software23, then reuse the SIF in jobs. Set `tool` to the image name and `owner` to the repository owner's lowercase GitHub name:

```bash
tool=samtools
owner=georgedeeks
mkdir -p "$HOME/containers"
sif="$HOME/containers/${tool}.sif"
"$runtime" pull "$sif" "docker://ghcr.io/${owner}/${tool}:latest"
```

Home quota is not yet recorded. If the SIF will not fit, choose a suitable path under `/tsl` visible to compute nodes. Scratch is not backed up; retain the image digest and copy any SIF/results you need to keep to persistent storage.

For **shared software installs**, the current site convention is `/tsl/software/testing/<Software>/<version>/x86_64/`. Set `sif` to a file there instead of `$HOME/containers`; keep the Apptainer cache/temp settings on scratch. See the [BindCraft2 setup](bindcraft2/README.md#pull-the-image-and-prepare-weights) for a concrete example with shared model weights. Installing at this path does not require rebuilding the image.

For a **private** image, use this instead of the last command, entering a GitHub username and personal access token (classic) with `read:packages` at the prompts. Authorize the token for your organization if its SSO policy requires it:

```bash
"$runtime" pull --docker-login "$sif" "docker://ghcr.io/${owner}/${tool}:latest"
```

An existing SIF is not silently replaced. For an update, pull to a **new filename** and test it before switching your jobs. For an exact release, use the digest command from the Actions summary. Do not put registry tokens in Dockerfiles, workflow files, or shell history.

### Space and site mounts

Allow enough scratch for compressed downloads, expanded layers, and the final SIF. Check your own quota as well as free disk space; the shared volume's free space is not your allocation. The cache settings above do not move application temporary files. In a Slurm job, create a separate directory for its temporary work:

```bash
export TMPDIR="/tsl/scratch/$USER/job-${SLURM_JOB_ID:?Run inside a Slurm allocation}/tmp"
mkdir -p "$TMPDIR"
```

TSL's older notes report that **user `--bind` is disabled**, while `/hpc-home` and `/tsl` are already mounted into containers. Use those real paths for inputs, outputs, weights and caches; do not map them to `/data` or `/work`. Confirm the default mounts in the first container test. Request any additional mounts from site support.

### Compute-node test and job examples

These commands are for whoever runs the workload. For GPU installs, include the equivalent commands in the handover to the requester; running them is not an installer delivery requirement.

Run the version/help test on a **representative allocated compute node**, following the site's scheduler rules. In a new job shell, load Apptainer and set the runtime and absolute SIF path again; variables from software23 are not a job configuration. Set the job scratch `TMPDIR` as above before the data test. For Samtools:

```bash
ml load apptainer
runtime=apptainer
sif="$HOME/containers/samtools.sif"
"$runtime" exec --cleanenv "$sif" samtools --version

# Run from a project directory under /tsl or /hpc-home.
"$runtime" exec --cleanenv --pwd "$PWD" --env TMPDIR="$TMPDIR" \
    "$sif" samtools view -H "$PWD/input.bam"
```

A real job goes through `sbatch`, not an interactive shell. A minimal CPU template — adjust partition, CPUs, memory and time to the workload; it assumes the SIF and inputs already exist under `/hpc-home` or `/tsl`:

```bash
#!/bin/bash
#SBATCH -p tsl-short
#SBATCH -c 1
#SBATCH --mem=2G
#SBATCH -t 00:30:00
#SBATCH -o %x-%j.out
# #SBATCH --constraint=avx2   # only if the tool needs AVX2; check the feature name first (HPC_COMPATIBILITY.md)
set -euo pipefail

ml load apptainer
sif="$HOME/containers/samtools.sif"     # absolute path under /hpc-home or /tsl
export TMPDIR="/tsl/scratch/$USER/job-${SLURM_JOB_ID}/tmp"
mkdir -p "$TMPDIR"
cd "$SLURM_SUBMIT_DIR"                  # submit from a project directory under /tsl or /hpc-home

apptainer exec --cleanenv --pwd "$PWD" --env TMPDIR="$TMPDIR" \
    "$sif" samtools view -H "$PWD/input.bam"

rm -rf "/tsl/scratch/$USER/job-${SLURM_JOB_ID}"
```

Pass the scheduler's CPU count to multithreaded tools (`-t "$SLURM_CPUS_PER_TASK"` or the tool's equivalent) rather than hard-coding it.

For Stargraph, the startup command is `stargraph.sh --help`. Use `exec IMAGE EXECUTABLE ...` for real work rather than depending on Docker `CMD` argument handling. Keep all input, output, database and scratch paths within the site-mounted trees. Lists of absolute input paths and any symlink targets must resolve inside the container. Its `/opt` installation is read-only at runtime; write results to the writable site storage.

Use a small representative dataset to check output files and exit status before a full job. Respect allocated CPUs and memory; do not run a full analysis on a login node. Download databases on software23 into a site-mounted path before submitting; offline compute nodes must not need to install or download anything. The container supplies userspace libraries, but still depends on the host kernel, CPU capabilities, and any GPU drivers.

`--cleanenv` reduces interference from login-shell Conda environments/modules. If a tool needs a licence variable, GPU settings, or other environment values, pass the required values explicitly using the runtime's documented environment options. For GPU jobs, request `-p tsl-gpu --gres=gpu:N`, use `--nv`, and explicitly preserve Slurm's non-empty device assignment with `--env CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:?Run inside a GPU allocation}"`. Include a framework GPU-backend check in the requester's example job. Set weights and application caches to absolute site-mounted paths. Do not disable environment isolation indiscriminately.

## Troubleshooting

| Symptom | First fix |
| --- | --- |
| Build did not run | Check branch and both path filters, or use Run workflow. |
| Build passed but no image was published | Publication is restricted to the default branch; PRs and other manual branches only test. |
| GHCR push denied | Check Actions has `packages: write`, organization policy permits publishing, and the package grants this repository Actions access. |
| Pull denied / unauthorized | Check image name and package visibility; use `--docker-login` for private packages. |
| Conda solve fails | Check the pinned version exists for `linux-64`, channel order, and dependency constraints. Do not switch off strict priority without understanding the conflict. |
| SSL/certificate error | Correct the CA/proxy configuration where the failure occurs. A container build cannot repair the HPC host's registry TLS setup. Keep certificate verification enabled. |
| Command not found | Check the actual executable and PATH; inspect `/opt/conda/envs/tool/bin`. |
| Permission denied / read-only filesystem | Use writable paths under `/hpc-home` or `/tsl`; do not add user `--bind` mounts on TSL. Check symlink destinations. |
| Illegal instruction / exec format error | Check compute-node CPU flags and image architecture against the package and base-image requirements. |
| No space left during pull | Move cache and temporary storage to approved scratch; check quota as well as free disk space. |
| Old Singularity cannot read the image | Use `ml load apptainer` for the checked Apptainer 1.4.5 runtime. |
| Help passes, analysis fails | Run a small real input and inspect dependencies, databases, bindings, activation hooks, and resource limits. |

## References

- [Bioconda channel setup](https://bioconda.github.io/)
- [Official Miniforge images](https://github.com/conda-forge/miniforge-images)
- [GitHub Container Registry access and visibility](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Singularity Docker/OCI support and authentication](https://docs.sylabs.io/guides/4.3/user-guide/singularity_and_docker.html)
- [Apptainer bind mounts](https://apptainer.org/docs/user/main/bind_paths_and_mounts.html)
