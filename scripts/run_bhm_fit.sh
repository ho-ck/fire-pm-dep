#!/bin/bash
#SBATCH --job-name=array-bhm-fit
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=high
#SBATCH --array=1-6
#SBATCH --time=48:00:00
#SBATCH --cpus-per-task=96  # 48 if 12 threads_per_chain
#SBATCH --mem=512G
# Usage: sbatch scripts/run_bhm_fit.sh

# Load environment
source ~/miniconda3/bin/activate
conda activate ppca

# cd to project root
cd "/home/users/cho00/fire-pm-dep"

CONFIGS=(
  # "configs/bhm_fit_svd_cfg.yaml"
  # "configs/bhm_fit_ppca_15kiter_24threads_cfg.yaml"
  "configs/bhm_fit_ppca_15kiter_24threads_scaley_cfg.yaml"
  # "configs/bhm_fit_ppca_15kiter_24threads_local_cfg.yaml"
  # "configs/bhm_fit_ppca_15kiter_24threads_local_scaley_cfg.yaml"
  # "configs/bhm_fit_ppca_15kiter_24threads_transported_cfg.yaml"
  # "configs/bhm_fit_ppca_15kiter_24threads_transported_scaley_cfg.yaml"
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

Rscript scripts/bhm_fit.R "$CONFIG"

echo "Finished at $(date)"
