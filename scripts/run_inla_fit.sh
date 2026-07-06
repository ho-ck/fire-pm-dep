#!/bin/bash
#SBATCH --job-name=inla-fit
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=high
#SBATCH --array=1
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=48
#SBATCH --mem=256G
# Usage: sbatch scripts/run_inla_fit.sh

# Load environment
source ~/miniconda3/bin/activate
conda activate inla

# cd to project root
cd "/home/users/cho00/fire-pm-dep"

CONFIGS=(
  "configs/inla_fit_cfg.yaml"
)

# Select config for this array task
CONFIG="${CONFIGS[$SLURM_ARRAY_TASK_ID-1]}"

# Build log filename from config name
LOGDIR="logs"
mkdir -p "$LOGDIR"

CFG_BASENAME="$(basename "$CONFIG" .yaml)"
LOGFILE="${LOGDIR}/${CFG_BASENAME}.log"

# Redirect stdout and stderr
exec >"$LOGFILE" 2>&1

echo "Starting job at $(date)"
echo "SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID}"
echo "Using config: $CONFIG"
echo "Logging to: $LOGFILE"

Rscript scripts/inla_fit.R "$CONFIG"

echo "Finished at $(date)"
