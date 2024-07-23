#!/bin/bash

eval "$(conda shell.bash hook)"


##########################
# Deactivating prior conda environments
for i in $(seq $CONDA_SHLVL); do
    conda deactivate
    echo "Deactivated conda environment"
done
#########################


conda activate {env_name}


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


echo "Before pytest reinstallation"
# python3 -m pip list --format=json
{additional_add_pytest_specific}

# Function to run a command and check its exit status
run_command() {{
    cmd="$@"
    eval $cmd
    if test $? -ne 0; then
        echo "Error: Failed to run command: $cmd"
        exit 1
    fi
}}
run_command "cd {repo_dir_path}"
echo "After pytest reinstallation"
# python3 -m pip list --format=json

pwd
# run pytest command
{test_cmd}
# echo "After test-case running"
# which pip
# which python3
# # python3 -m pip list --format=json