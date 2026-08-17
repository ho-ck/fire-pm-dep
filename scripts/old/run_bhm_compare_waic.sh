#!/bin/bash
#SBATCH --job-name=waic-comp
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=high
#SBATCH --time=48:00:00
#SBATCH --cpus-per-task=96
#SBATCH --mem=1000G
# Usage: sbatch scripts/run_bhm_compare_waic.sh

# Load environment
source ~/miniconda3/bin/activate
conda activate ppca

# cd to project root
cd "/home/users/cho00/fire-pm-dep"

CONFIGS=(
  "configs/bhm_fit_ppca_15kiter_24threads_cfg.yaml"
  "configs/bhm_fit_ppca_15kiter_24threads_no_country_year_slope_cfg.yaml"
)

# Build log filename from config name
LOGDIR="logs"
mkdir -p "$LOGDIR"

DATE=$(date +%Y-%m-%d_%H-%M-%S)
LOGFILE="${LOGDIR}/bhm_compare_waic_${DATE}.log"

# Redirect stdout and stderr
exec >"$LOGFILE" 2>&1

echo "Starting job at $(date)"
echo "Using configs: ${CONFIGS[*]}"
echo "Logging to: $LOGFILE"

Rscript scripts/bhm_compare_waic.R "${CONFIGS[@]}"

echo "Finished at $(date)"
