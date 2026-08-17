#!/bin/bash

#SBATCH --job-name=create-annual-data
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=standard
#SBATCH --time=24:00:00
#SBATCH --mem=128G
#SBATCH --array=6 #0-23

# SLURM_ARRAY_TASK_ID are array job task IDs (0-23, representing years 2000-2023)

# Source .bashrc to initialize Conda and environment variables
source ~/.bashrc

# Activate the Conda environment
source ~/miniconda3/bin/activate
conda activate pm

# Project directory
cd ~/fire-pm-dep/

# Logging
LOGDIR="logs/setup_scripts"
mkdir -p "$LOGDIR"
DATETIME=$(date +%Y-%m-%d_%H-%M-%S)
LOGFILE="${LOGDIR}/create_annual_pm_se_data_${DATETIME}.$SLURM_ARRAY_TASK_ID.out"
exec >"$LOGFILE" 2>&1

# Run
echo "=============================================================="
echo "Starting job"
echo "Date:      $(date)"
echo "Array ID:  ${SLURM_ARRAY_TASK_ID}"
echo "Host:      $(hostname)"
echo "Log file:  ${LOGFILE}"
echo "=============================================================="

python src/setup_scripts/create_annual_pm_se_data.py

EXIT_CODE=$?

echo
echo "=============================================================="
echo "Finished at $(date)"
echo "Exit code: ${EXIT_CODE}"
echo "=============================================================="

exit ${EXIT_CODE}