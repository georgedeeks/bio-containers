#!/usr/bin/env bash
# Usage: sbatch run-wrapper.slurm /absolute/path/to/settings.json
# Submit from a writable project directory under /tsl or /hpc-home.
# Adjust CPUs, RAM and wall time for a production campaign.
#SBATCH --job-name=bindcraft2
#SBATCH --partition=tsl-gpu
#SBATCH --gres=gpu:a100:1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=%x-%j.out
set -eo pipefail

ml load apptainer
source /tsl/software/testing/bin/BindCraft2-1.0.3
set -u

settings="${1:?Pass the absolute settings JSON path}"
[[ "$settings" == /* && -f "$settings" && -r "$settings" ]] || {
    printf 'Expected a readable absolute settings JSON path: %s\n' "$settings" >&2
    exit 2
}
cd "${SLURM_SUBMIT_DIR:?Submit this script with sbatch}"
srun bindcraft --check-gpu
srun bindcraft design "$settings"
