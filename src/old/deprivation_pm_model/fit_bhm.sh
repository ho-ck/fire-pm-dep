#!/bin/bash
#SBATCH --job-name=fit-brms-array
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=high
#SBATCH --array=1-5
#SBATCH --time=48:00:00
#SBATCH --cpus-per-task=96 # can only do >1 if using 'high' qos (which has 2day walltime limit)
#SBATCH --mem=128G
#SBATCH -o /home/users/cho00/fire-pm-dep/logs/bhm_model_%a.out
#SBATCH -e /home/users/cho00/fire-pm-dep/logs/bhm_model_%a.err

# Load environment
source ~/.bashrc
source ~/miniconda3/bin/activate
conda activate R

# Script directory
SCRIPT_DIR=/home/users/cho00/fire-pm-dep/src/deprivation_pm_model
cd "${SCRIPT_DIR}"

CONFIG_FILE="configs/fit_bhm_cfg.yaml"  # fit_bhm.R takes relative path to cfg
MODEL_INDEX="${SLURM_ARRAY_TASK_ID}"

echo "Running model index ${SLURM_ARRAY_TASK_ID}"

# Run Rscript to fit Bayesian hierarchical model
Rscript fit_bhm.R "${CONFIG_FILE}" ${SLURM_ARRAY_TASK_ID}
