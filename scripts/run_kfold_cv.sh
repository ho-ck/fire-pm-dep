#!/bin/bash
#SBATCH --job-name=array-bhm-fit
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=high
#SBATCH --array=1-8
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=48
#SBATCH --mem=256G
# Usage: sbatch scripts/run_kfold_cv.sh

# Load environment
source ~/miniconda3/bin/activate
conda activate inla

# cd to project root
cd "/home/users/cho00/fire-pm-dep"

# Build log filename
LOGDIR="logs"
mkdir -p "$LOGDIR"

LOGFILE="${LOGDIR}/run_kfold_cv_$SLURM_ARRAY_TASK_ID.log"

# Redirect stdout and stderr
exec >"$LOGFILE" 2>&1

echo "Starting job at $(date)"
echo "SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID}"
echo "Logging to: $LOGFILE"

Rscript scripts/pred_fold.R

echo "Finished at $(date)"
