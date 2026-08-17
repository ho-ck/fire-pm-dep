#!/bin/bash
#SBATCH --job-name=pred-loc-tp
#SBATCH --account=no-project
#SBATCH --partition=standard
#SBATCH --qos=high
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=48
#SBATCH --mem=128G
#SBATCH -o /home/users/cho00/fire-pm-dep/logs/pred_local_transported_pm.out
#SBATCH -e /home/users/cho00/fire-pm-dep/logs/pred_local_transported_pm.err

# Load environment
source ~/.bashrc
source ~/miniconda3/bin/activate
conda activate inla

# Script directory
cd /home/users/cho00/fire-pm-dep/src/transported_pm_model

echo "Starting local/transported PM estimation script..."

# Run Rscript
Rscript pred_local_transported_pm.R configs/pred_local_transported_pm_cfg.yaml
