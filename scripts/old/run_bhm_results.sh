#!/bin/bash
#SBATCH --job-name=array-bhm-res
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=standard
#SBATCH --array=1-7
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=128G
# Usage: sbatch scripts/run_bhm_results.sh

# Load environment
source ~/miniconda3/bin/activate
conda activate ppca

# cd to project root
cd "/home/users/cho00/fire-pm-dep"

CONFIGS=(
  # "configs/bhm_results_cfg.yaml"
  # "configs/bhm_results_local_pm_cfg.yaml"
  # "configs/bhm_results_transported_pm_cfg.yaml"
  # "configs/bhm_results_non_nested_grid_int_slope_cfg.yaml"
  # "configs/bhm_results_local_pm_non_nested_grid_int_slope_cfg.yaml"
  # "configs/bhm_results_transported_pm_non_nested_grid_int_slope_cfg.yaml"
  "configs/bhm_fit_svd_cfg.yaml"
  "configs/bhm_fit_ppca_15kiter_24threads_cfg.yaml"
  "configs/bhm_fit_ppca_15kiter_24threads_scaley_cfg.yaml"
  "configs/bhm_fit_ppca_15kiter_24threads_local_cfg.yaml"
  "configs/bhm_fit_ppca_15kiter_24threads_local_scaley_cfg.yaml"
  "configs/bhm_fit_ppca_15kiter_24threads_transported_cfg.yaml"
  "configs/bhm_fit_ppca_15kiter_24threads_transported_scaley_cfg.yaml"
)

# Select config for this array task
CONFIG="${CONFIGS[$SLURM_ARRAY_TASK_ID-1]}"

# Build log filename from config name
LOGDIR="logs"
mkdir -p "$LOGDIR"

CFG_BASENAME="$(basename "$CONFIG" .yaml)"
LOGFILE="${LOGDIR}/${CFG_BASENAME}.log"

# Replace _fit_ with _results_ in log filename
LOGFILE="${LOGFILE/_fit_/_results_}"

# Redirect stdout and stderr
exec >"$LOGFILE" 2>&1

echo "Starting job at $(date)"
echo "SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID}"
echo "Using config: $CONFIG"
echo "Logging to: $LOGFILE"

Rscript scripts/bhm_results.R "$CONFIG"

echo "Finished at $(date)"
