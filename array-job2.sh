#!/bin/bash
#SBATCH --time    1-00:00:00
#SBATCH --nodes   1
#SBATCH --constraint GPU
#SBATCH --partition cms-uhh,cms,allgpu
#SBATCH --array 1-42
#SBATCH --job-name DNN-scan
#SBATCH --workdir   /beegfs/desy/user/reimersa/ZprimeClassifier/workdir/output
#SBATCH --output    steer-%N-%j.out
#SBATCH --error     steer-%N-%j.err
#SBATCH --mail-type ALL                           # Type of email notification- BEGIN,END,FAIL,ALL
#SBATCH --mail-user arne.reimers@desy.de          # Email to which notifications will be sent. It defaults to <userid@mail.desy.de> if none is set.
# export LD_PRELOAD=""
# source /etc/profile.d/modules.sh

source ~/.setenv
cd /beegfs/desy/user/reimersa/ZprimeClassifier
./steer_array2.py $SLURM_ARRAY_TASK_ID
