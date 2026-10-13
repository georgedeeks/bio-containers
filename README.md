# Bio-Containers Toolbox

> **Scope: the TSL / NBI HPC only** (`hpc.tsl.ac.uk`, Slurm, Apptainer 1.4.5). Every command, path and rule in this repository assumes that cluster. Another site needs its own profile in [HPC_COMPATIBILITY.md](HPC_COMPATIBILITY.md) before any guide here applies to it.

Build bioinformatics tools on GitHub, then use them on the HPC with Singularity or Apptainer. Each tool has its own folder, image name, and workflow. The aim is to get a working tool quickly, with enough checking to catch common cluster failures.

**Flow:** Dockerfile → GitHub Actions → GHCR image → `singularity pull` / `apptainer pull` → local `.sif` file. The pull converts the Docker image to SIF; GitHub does not build the SIF.

## Use Stargraph on the HPC

On **software23**, use Bash and load Apptainer. Put download/conversion caches on scratch because TSL's `/tmp` is only 5 GB:

```bash
ml load apptainer
export APPTAINER_TMPDIR="/tsl/scratch/$USER/apptainer-tmp"
export APPTAINER_CACHEDIR="/tsl/scratch/$USER/apptainer-cache"
sif_dir="$HOME/containers"   # must sit under /hpc-home or /tsl; use a /tsl path if home quota is short
mkdir -p "$APPTAINER_TMPDIR" "$APPTAINER_CACHEDIR" "$sif_dir"
apptainer pull "$sif_dir/stargraph.sif" docker://ghcr.io/georgedeeks/stargraph:latest
apptainer exec --cleanenv "$sif_dir/stargraph.sif" stargraph.sh --help
```

Keep SIFs in a location with enough quota under `/hpc-home` or `/tsl`. Run analyses in a Slurm allocation. Submission and compute nodes have no internet; user `--bind` mounts are reported disabled, so the examples use existing site mounts.

If the image is private, add `--docker-login` immediately after `pull`; use your GitHub username and a personal access token (classic) with `read:packages` when prompted. See [access, scratch space, updates, and real jobs](ADDING_NEW_CONTAINER_GUIDE.md#4-pull-and-run-on-the-hpc).

The default template targets **Linux x86_64 CPUs**. For GPU software, adapt the installation to the recorded [HPC hardware, driver and runtime](HPC_COMPATIBILITY.md). Our delivery target is a successful build with useful checks that can run without a GPU, plus clear usage instructions. The requester runs the actual GPU workload; waiting for an allocation is not required before handing over the installation.

## Add a tool

Read the [short adding guide](ADDING_NEW_CONTAINER_GUIDE.md). A small generator creates the correctly named Dockerfile, workflow, and tool notes:

```bash
# Example only: first check that this version meets your requirements.
python3 scripts/new-tool.py samtools 'samtools=1.22.1' samtools --smoke-arg=--version
```

It refuses to replace existing tools. Check the new tool against the [HPC profile](HPC_COMPATIBILITY.md), fill in its notes, then commit and push the generated files.

Builds run when the tool folder or its workflow changes. Pull requests are tested without publishing; successful builds on the repository's default branch publish `latest` and a `sha-<full-commit>` tag. Use the **image digest printed in the Actions summary** to retrieve an exact image later. A manual **Run workflow** button is also available.

## Repository layout

- `tool-name/`: Dockerfile and tool-specific usage/compatibility notes.
- `.github/workflows/build-tool-name.yml`: build, smoke test, cache, and publish.
- `templates/` and `scripts/new-tool.py`: starting point for new tools; changing a template does not update existing tools.
- [HPC_COMPATIBILITY.md](HPC_COMPATIBILITY.md): shared cluster facts and checks for each new piece of software.
- `references/`: detailed evidence from existing site installations, including [AlphaFold 3.0.0](references/alphafold3.md).
- [AGENTS.md](AGENTS.md): instructions for assistants working in this repository.

Tools: [Stargraph](stargraph/README.md) and [BindCraft2](bindcraft2/README.md) (CUDA 12, with offline installation checks and a TSL Slurm example).

For shared installs, use the tested **site loader → executable launcher → SIF and weights** arrangement. Users run `source <Software>-<version>` and then the normal tool command. See the [shared-wrapper guide](ADDING_NEW_CONTAINER_GUIDE.md#shared-command-wrappers) and [creator maintenance notes](references/tsl-software-wrappers.md). The loader, container libraries and external model files have different roles; no new module system or HPC repository checkout is needed.
