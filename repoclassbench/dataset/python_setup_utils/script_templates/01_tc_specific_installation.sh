#!/bin/bash

eval "$(conda shell.bash hook)"

# conda env list


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


echo "Start of folder installation"
python3 -m pip list --format=json

# Function to run a command and check its exit status
run_command() {{
    cmd="$@"
    eval $cmd
    if test $? -ne 0; then
        echo "Error: Failed to run command: $cmd"
        exit 1
    fi
}}

cd {repo_dir_path}

# Remove all paths in .gitignore
if [ -e ".gitignore" ]; then
    run_command "git ls-files --ignored --exclude-standard -o -z | xargs -0 -r rm -rf"
fi

# Reset git repo + checkout base commit
run_command "git restore ."
run_command "git reset HEAD ."
run_command "git clean -fdx"
run_command "git -c advice.detachedHead=false checkout {base_commit_id}"

echo "############"
echo "Output of git status is:"
git status

echo "############"
echo "Output of git log is:"

git log -n2

echo "############"

echo "Before stage"
python3 -m pip list --format=json

python -m pip install pytest-json
python -m pip install pytest-json-report

# pre-install commands
run_command {pre_install_cmd}

# main install command
run_command {main_install_cmd}


echo "After stage"
python3 -m pip list --format=json