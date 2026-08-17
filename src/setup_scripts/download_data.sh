#!/bin/bash

#SBATCH --job-name=download-data
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=long
#SBATCH --time=32:00:00
#SBATCH --mem=16G
#SBATCH --array=0-16, 
#       --array=5 # temp 06/07/2026: just downloading worldpop age-sex 
#       --array=0-15    # (there are 16 datasets)

###############################################################################
# Environment
###############################################################################

# Source .bashrc to initialize Conda
source ~/.bashrc
source ~/miniconda3/bin/activate

# Activate environment
conda activate pm

# Project directory
cd ~/fire-pm-dep/

###############################################################################
# Datasets
#
# Names match keys in DATASETS in download_data.py
# Slurm array size (--array=0-N) should equal len(DATASETS) - 1.
###############################################################################

DATASETS=(
    hu_annual
    xu_annual
    xu_monthly
    adm0
    western_sahara
    worldpop
    worldpop_age_sex
    kummu
    education
    stunting
    wash
    grdi
    ghs
    gfed
    era5_meteo
    era5_precipitation
    kummu_admin2
)

DATASET=${DATASETS[$SLURM_ARRAY_TASK_ID]}

###############################################################################
# Logging
###############################################################################

LOGDIR="logs/setup_scripts"
mkdir -p "$LOGDIR"

DATETIME=$(date +%Y-%m-%d_%H-%M-%S)

LOGFILE="${LOGDIR}/${SLURM_ARRAY_TASK_ID}_${DATASET}_${DATETIME}.log"

exec >"$LOGFILE" 2>&1

###############################################################################
# Run
###############################################################################

echo "=============================================================="
echo "Starting job"
echo "Date:      $(date)"
echo "Dataset:   ${DATASET}"
echo "Array ID:  ${SLURM_ARRAY_TASK_ID}"
echo "Host:      $(hostname)"
echo "Log file:  ${LOGFILE}"
echo "=============================================================="

# python src/setup_scripts/download_data.py \
python src/setup_scripts/download_data_2000_2022.py \
    --dataset "${DATASET}"

EXIT_CODE=$?

echo
echo "=============================================================="
echo "Finished at $(date)"
echo "Exit code: ${EXIT_CODE}"
echo "=============================================================="

exit ${EXIT_CODE}