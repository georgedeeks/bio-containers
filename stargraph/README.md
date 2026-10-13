# Stargraph

Status: **candidate — HPC execution pending** for this revised recipe. No compute-node analysis has been verified here.

| Item | Value |
| --- | --- |
| Upstream | [SAMtoBAM/stargraph](https://github.com/SAMtoBAM/stargraph) |
| Package | `samtobam::stargraph=1.0.0=0`, verified in [package metadata](https://api.anaconda.org/package/samtobam/stargraph) on 2026-10-13 |
| Package platform | `linux-64`; image builds for `linux/amd64` |
| Executable | `stargraph.sh` |
| Base | Official Miniforge 26.7.2-0, pinned by digest in the Dockerfile |
| GPU / MPI | This recipe targets CPU, single-node execution; confirm any additional upstream modules separately |
| CPU instruction requirements | Unverified for the complete dependency set; test the actual compute-node type |
| Resources | Genome-graph analyses can be substantial; measure a small dataset before choosing CPU/RAM/scratch for a full run |
| Inputs and external data | Genome assemblies and Starfish-derived inputs; follow upstream requirements and check databases needed by the selected modules |
| Dependency resolution | Linux x86_64 dry run passed on 2026-10-13: 514 packages, about 1.04 GiB of compressed downloads |
| CI / HPC tests | Pending for this revised recipe; dependency resolution does not execute the software |

Upstream offers both Conda installation and an image at `ghcr.io/samtobam/stargraph`; this repository retains its own pinned Conda build so the environment and startup check remain explicit. The package includes many tightly pinned dependencies. An installation or `--help` success alone does not validate every subtool, database, or pipeline stage.

The dependency dry run used `linux-64`, strict conda-forge/Bioconda/SAMtoBAM ordering, and virtual Linux/glibc values matching the intended Ubuntu-based container. It installed no packages. Allow additional space for the expanded environment, image layers, SIF conversion, databases, and analysis outputs; the compressed download figure is not a storage or memory requirement for a job.

## Startup check

Pull using the [main guide](../ADDING_NEW_CONTAINER_GUIDE.md#4-pull-and-run-on-the-hpc), then run on an allocated compute node:

```bash
apptainer exec --cleanenv "$HOME/containers/stargraph.sif" stargraph.sh --help
```

Load `ml load apptainer` first. TSL reports Apptainer 1.4.5. The default `apptainer run IMAGE` command also prints help; use `exec IMAGE stargraph.sh ...` for analyses.

## Small analysis check

Choose a small valid set of assemblies and matching Starfish outputs according to upstream instructions. Run from a project directory under `/tsl` or `/hpc-home`, using absolute container-visible paths in `assemblies_panSN.txt`:

```bash
# Set this to CPUs actually allocated by your scheduler.
threads=1
apptainer exec --cleanenv --pwd "$PWD" \
    "$HOME/containers/stargraph.sif" stargraph.sh \
    -a "$PWD/assemblies_panSN.txt" -r "$PWD/sample.filt.gff" -e "$PWD/sample.elements.ann.feat" \
    -t "$threads"
```

The sample filenames are placeholders, not bundled test data. Keep all database/input/scratch paths and symlink destinations under TSL's existing `/tsl` or `/hpc-home` mounts; user `--bind` is reported disabled. Keep downloads outside offline jobs and results outside the read-only image. Check expected upstream outputs and record the command, exit status, image digest, node type, runtime version, and resource usage here when a sample run is available.

To inspect the exact installed Conda package set:

```bash
apptainer exec --cleanenv "$HOME/containers/stargraph.sif" \
    cat /opt/container-info/conda-explicit.txt
```

Shared cluster facts: [HPC_COMPATIBILITY.md](../HPC_COMPATIBILITY.md).
