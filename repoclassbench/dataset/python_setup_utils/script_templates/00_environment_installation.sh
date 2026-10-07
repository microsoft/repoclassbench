#!/bin/bash

which python3
eval "$(conda shell.bash hook)"
which python3
#################


##########################
# Deactivating prior conda environments
for i in $(seq $CONDA_SHLVL); do
    conda deactivate
    echo "Deactivated conda environment"
done
#########################

# Function to run a command and check its exit status
run_command() {{
    cmd="$@"
    eval $cmd
    if test $? -ne 0; then
        echo "Error: Failed to run command: $cmd"
        exit 1
    fi
}}

# requirements.txt related commands
run_command {requirements_cmd}

# environment.yaml related commands
run_command {environment_yaml_cmd}

# pip related commands (conda create -n env_name python=install['python'] pkgs -y)
run_command {pip_cmd}

conda activate {env_name}

# Some per-task install commands (see swebench_related_constants.py) use the
# legacy "--no-use-pep517" pip flag, which pip removed in 23.1+. These task
# definitions were authored against older pip releases, so pin pip to a
# version that still understands that flag before running the real install.
python3 -m pip install "pip<23.1" -q

###########################
# Check if CONDA_SHLVL is exactly 1
if [ "$CONDA_SHLVL" != "1" ]; then
  echo "Current CONDA_SHLVL value: $CONDA_SHLVL"
  echo "CONDA_SHLVL is NOT 1"
  exit 1
fi

# Continue with the rest of the script if CONDA_SHLVL is 1
echo "CONDA_SHLVL is 1, continuing with the script..."
#######################

# requirements_pip
run_command {requirements_pip_cmd}

# yaml_pip
run_command {yaml_pip_cmd}


# pip_packages related commands (pip install install['pip_packages'])
{pip_packages_cmd}

echo "end of environment installation"
python3 -m pip list --format=json
