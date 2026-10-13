#!/usr/bin/env bash
# Usage: sbatch run.slurm /absolute/image.sif /absolute/af2-params /absolute/settings.json
# Submit from a writable project directory under /tsl or /hpc-home.
# Adjust time, memory and CPUs for a production campaign.
#SBATCH --job-name=bindcraft2
#SBATCH --partition=tsl-gpu
#SBATCH --gres=gpu:a100:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=%x-%j.out
set -euo pipefail

sif="${1:?Pass the absolute SIF path}"
af_params="${2:?Pass the absolute AlphaFold 2 parameter directory}"
settings="${3:?Pass the absolute settings JSON path}"
for path in "$sif" "$af_params" "$settings"; do
    if [[ "$path" != /* || ! -e "$path" ]]; then
        printf 'Expected an existing absolute path: %s\n' "$path" >&2
        exit 2
    fi
done
: "${CUDA_VISIBLE_DEVICES:?Slurm must supply a GPU device assignment}"
: "${SLURM_JOB_ID:?Submit this script with sbatch}"

ml load apptainer
cd "$SLURM_SUBMIT_DIR"
export TMPDIR="/tsl/scratch/$USER/bindcraft2-${SLURM_JOB_ID}/tmp"
cache="/tsl/scratch/$USER/bindcraft2-cache"
mkdir -p "$TMPDIR" "$cache/jax-cuda12" "$cache/matplotlib"

container=(apptainer exec --cleanenv --nv --pwd "$PWD"
    --env "CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
    --env "TMPDIR=$TMPDIR" --env "XDG_CACHE_HOME=$cache"
    --env "MPLCONFIGDIR=$cache/matplotlib"
    --env "JAX_COMPILATION_CACHE_DIR=$cache/jax-cuda12"
    --env "OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK"
    --env "BINDCRAFT_AF2_PARAMS=$af_params"
    --env BINDCRAFT_WORKERS_PER_GPU=1 --env BINDCRAFT_DESIGN_WORKERS=1
    --env JAX_PLATFORMS=cuda
    "$sif")

# Check all externally staged weights, then require a real GPU backend.
srun "${container[@]}" python -m bindcraft.selfcheck cuda12
srun "${container[@]}" python -c \
    'import jax; print(jax.devices()); assert jax.default_backend() == "gpu", "JAX did not select a GPU"'
srun "${container[@]}" bindcraft design "$settings"

# Remove only this successfully completed job's temporary directory.
rm -rf -- "$TMPDIR"
