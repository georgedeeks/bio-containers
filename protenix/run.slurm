#!/usr/bin/env bash
# Usage: sbatch run.slurm IMAGE.sif ASSETS INPUT.json NEW_OUTPUT [SEEDS] [SAMPLES] [--no-msa]
# All paths must be absolute and under /tsl or /hpc-home (including symlink targets).
# Resource requests are a starting point for a toy run, not a throughput estimate.
# This example is limited to the node whose A100 80 GB/driver were checked.
#SBATCH --job-name=protenix-v1
#SBATCH --partition=tsl-gpu
#SBATCH --nodelist=tsl2048n2
#SBATCH --gres=gpu:a100:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --output=%x-%j.out
set -euo pipefail

sif="${1:?Pass the absolute SIF path}"
assets="${2:?Pass the absolute assets directory}"
input="${3:?Pass the absolute input JSON path}"
output="${4:?Pass a new absolute output directory}"
seeds="${5:-101}"
samples="${6:-1}"
extra=()
if [[ $# -ge 7 ]]; then
    [[ $# -eq 7 && "$7" == --no-msa ]] || { echo 'Only --no-msa is accepted as the seventh argument' >&2; exit 2; }
    extra+=(--no-msa)
fi
for path in "$sif" "$assets" "$input" "$output"; do
    case "$path" in
        /tsl/*|/hpc-home/*) ;;
        *) printf 'Use an absolute site-mounted path: %s\n' "$path" >&2; exit 2 ;;
    esac
    resolved="$(realpath -m -- "$path")"
    case "$resolved" in
        /tsl/*|/hpc-home/*) ;;
        *) printf 'Path resolves outside site mounts: %s\n' "$path" >&2; exit 2 ;;
    esac
done
[[ -f "$sif" && -d "$assets" && -f "$input" ]] || { echo 'Missing SIF, assets or input' >&2; exit 2; }
[[ ! -e "$output" ]] || { echo 'Output already exists; choose a fresh directory' >&2; exit 2; }
: "${SLURM_JOB_ID:?Submit this script with sbatch}"
: "${CUDA_VISIBLE_DEVICES:?Slurm must supply a GPU assignment}"

ml load apptainer
cd "${SLURM_SUBMIT_DIR:?Submit from a project directory}"
job_cache="/tsl/scratch/$USER/protenix-${SLURM_JOB_ID}"
mkdir -p "$job_cache/tmp" "$job_cache/cache" "$job_cache/torch" "$job_cache/triton" "$job_cache/matplotlib"
export APPTAINERENV_CUDA_VISIBLE_DEVICES="$CUDA_VISIBLE_DEVICES"
export APPTAINERENV_TMPDIR="$job_cache/tmp"
export APPTAINERENV_XDG_CACHE_HOME="$job_cache/cache"
export APPTAINERENV_TORCH_HOME="$job_cache/torch"
export APPTAINERENV_TORCH_EXTENSIONS_DIR="$job_cache/torch/extensions"
export APPTAINERENV_TRITON_CACHE_DIR="$job_cache/triton"
export APPTAINERENV_MPLCONFIGDIR="$job_cache/matplotlib"
export APPTAINERENV_OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK:-4}"

# Preserve the site library mount on hosts that provide it.
apptainer_options=(--cleanenv --no-eval --nv --pwd "$PWD")
if [[ ! -e /usr/local/lib64/rc_preload.so ]]; then
    apptainer_options+=(--no-mount /usr/local/lib64/rc_preload.so)
fi
srun apptainer exec "${apptainer_options[@]}" "$sif" \
    protenix-predict --assets "$assets" --input "$input" --out-dir "$output" \
    --seeds "$seeds" --samples "$samples" "${extra[@]}"
printf 'Completed: %s\nJob caches retained at: %s\n' "$output" "$job_cache"
