#!/bin/bash
#SBATCH --job-name=fit-inla
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=high
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=48
#SBATCH --mem=128G
#SBATCH -o /home/users/cho00/fire-pm-dep/logs/inla_model.out
#SBATCH -e /home/users/cho00/fire-pm-dep/logs/inla_model.err

# Load environment
source ~/.bashrc
source ~/miniconda3/bin/activate
conda activate inla

# Script directory
cd /home/users/cho00/fire-pm-dep/src/transported_pm_model

echo "Starting INLA model script..."

# Run Rscript to fit INLA BYM2 model
Rscript fit_inla.R configs/fit_inla_cfg.yaml
