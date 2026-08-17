#!/bin/bash

#SBATCH --job-name=create-urb
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=short
#SBATCH --time=01:00:00
#SBATCH --mem=128G


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
LOGFILE="${LOGDIR}/create_urban_pop_tifs_${DATETIME}.out"
exec >"$LOGFILE" 2>&1

# Run
echo "=============================================================="
echo "Starting job"
echo "Date:      $(date)"
echo "Host:      $(hostname)"
echo "Log file:  ${LOGFILE}"
echo "=============================================================="

python src/setup_scripts/create_urban_pop_tifs.py

EXIT_CODE=$?

echo
echo "=============================================================="
echo "Finished at $(date)"
echo "Exit code: ${EXIT_CODE}"
echo "=============================================================="

exit ${EXIT_CODE}
