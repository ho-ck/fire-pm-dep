#!/bin/bash

#SBATCH --job-name=align-climate-data
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=standard
#SBATCH --time=04:00:00
#SBATCH --mem=64G
#SBATCH --array=0-19

# SLURM_ARRAY_TASK_ID are array job task IDs (0-19, representing years 2000-2019)

# Source .bashrc to initialize Conda and environment variables
source ~/.bashrc
source ~/miniconda3/bin/activate

# Activate Conda env `pm`
conda activate pm

# Navigate to project directory
cd ~/fire-pm-dep/

# Logging directory
LOGDIR="logs/setup_scripts"
mkdir -p "$LOGDIR"

DATETIME=$(date +%Y-%m-%d_%H-%M-%S)
LOGFILE="${LOGDIR}/align_climate_data_monthly_${DATETIME}.$SLURM_ARRAY_TASK_ID.log"

# Redirect stdout and stderr
exec >"$LOGFILE" 2>&1

echo "Starting job at $(date)"
echo "Logging to: $LOGFILE"

# Run the Python script with the task ID, which will determine which year to process
python src/setup_scripts/align_climate_data_monthly.py

echo "Finished at $(date)"