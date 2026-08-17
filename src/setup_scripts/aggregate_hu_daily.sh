#!/bin/bash

#SBATCH --job-name=agg-hu-pm25
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=standard
#SBATCH --time=01:00:00
#SBATCH --mem=8G
#SBATCH --array=0-23


# SLURM_ARRAY_TASK_ID are array job task IDs (0-23, representing years 2000-2023)

# Source .bashrc to initialize Conda and environment variables
source ~/.bashrc

# Activate the Conda environment
source ~/miniconda3/bin/activate
conda activate terra    # env with netCDF4 installed

# Project directory
cd ~/fire-pm-dep/

# Logging
LOGDIR="logs/setup_scripts"
mkdir -p "$LOGDIR"
DATETIME=$(date +%Y-%m-%d_%H-%M-%S)
LOGFILE="${LOGDIR}/aggregate_hu_daily_${DATETIME}.$SLURM_ARRAY_TASK_ID.out"
exec >"$LOGFILE" 2>&1

# Run
echo "=============================================================="
echo "Starting job"
echo "Date:      $(date)"
echo "Array ID:  ${SLURM_ARRAY_TASK_ID}"
echo "Host:      $(hostname)"
echo "Log file:  ${LOGFILE}"
echo "=============================================================="

python src/setup_scripts/aggregate_hu_daily.py --mode both

EXIT_CODE=$?

echo
echo "=============================================================="
echo "Finished at $(date)"
echo "Exit code: ${EXIT_CODE}"
echo "=============================================================="

exit ${EXIT_CODE}