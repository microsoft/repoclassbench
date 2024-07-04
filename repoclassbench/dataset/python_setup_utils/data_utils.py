from typing import List
import subprocess
import os
import sys
import json
from typing import Dict, List
import requests
from copy import deepcopy
from repoclassbench.common_utils import fetch_ist_adjusted_logger
import repoclassbench.dataset.python_setup_utils.swebench_related_constants as swebench_related_constants
from repoclassbench.constants import PythonConstants

logger = fetch_ist_adjusted_logger()


def fetch_repotools_task_elem(repoclassbench_id: str):
    """
    Fetches the repository tools task element based on the given repoclassbench_id.

    Args:
        repoclassbench_id (str): The ID of the repository tools task element.

    Returns:
        dict: The repository tools task element matching the repoclassbench_id, or None if not found.
    """
    file_path = os.path.join(PythonConstants.ProjectDir, "data/input/python_data.json")
    assert os.path.exists(file_path)
    with open(file_path, "r") as f:
        data = json.load(f)
    relevant_elems = [x for x in data if x["task_id"] == repoclassbench_id]
    if len(relevant_elems) == 0:
        return None
    assert len(relevant_elems) == 1
    return relevant_elems[0]


# def fetch_repo_to_commit_mapping():
#     '''Fetches the mapping of issue to commit id which contains the paraphrased repository'''
#     file_path = os.path.join(
#         PythonConstants.ProjectDir, "data/input/python_dataset_intermediate_files/issue_to_commit_id.json")
#     assert (os.path.exists(file_path))
#     with open(file_path, 'r') as f:
#         data = json.load(f)
#     return data


def get_conda_environments():
    """Fetches all the conda environments available on a device running Ubuntu and returns them as a list.

    Returns:
        list: A list of conda environment names.
    """
    # Run the 'conda env list' command and capture its output
    output = subprocess.check_output(["conda", "env", "list"]).decode("utf-8")

    # Split the output into lines
    lines = output.strip().split("\n")

    # Extract the environment names from the output
    environments = [line.split()[0] for line in lines[2:]]

    return environments


# def fetch_swebench_df(path_to_swebench_tc_file: str = os.path.join(PythonConstants.ProjectDir, "data/input/python_dataset_intermediate_files/swe-bench_all.json")):
#     """
#     Fetches the dataset details made public by SweBench authors.

#     Args:
#         path_to_swebench_tc_file (str): The path to the SweBench test case file.

#     Returns:
#         dict: The SweBench dataset as a dictionary.

#     Raises:
#         AssertionError: If the specified file does not exist.

#     """
#     assert (os.path.exists(path_to_swebench_tc_file))
#     logger.debug("Fetching SweBench dataset from %s" %
#                  (path_to_swebench_tc_file))
#     with open(path_to_swebench_tc_file, "r") as f:
#         swebench_df = json.load(f)
#     return swebench_df


# def fetch_swebench_elem(swebench_issue_id: str):
#     '''Fetches the swebench element for a given test case id.

#     Args:
#         swebench_issue_id (str): The test case id in the format `scikit-learn__scikit-learn-13328`.

#     Returns:
#         dict: The swebench element as a dictionary.
#     '''
#     swebench_df = fetch_swebench_df()
#     swebench_elem = list(
#         filter(lambda x: x['instance_id'] == swebench_issue_id, swebench_df))
#     if len(swebench_elem) == 0:
#         logger.error(
#             "No element found in swebench_df with issue_id: %s" % (swebench_issue_id))
#         # raise Exception("No such element found")
#         return None
#     assert (len(swebench_elem) == 1)
#     return swebench_elem[0]


def get_environment_yml(instance: Dict, env_name: str, save_path: str = None) -> str:
    """
    Get environment.yml for given task instance

    Args:
        instance (dict): SWE Bench Task instance
        env_name (str): Rename retrieved environment.yml to this name
        save_path (str): If provided, save environment.yml to this path
    Returns:
        environment.yml (str): If save_path given, returns path to saved environment.yml.
            Otherwise, returns environment.yml as string
    """
    # Attempt to find environment.yml at each path based on task instance's
    # repo
    path_worked = False

    commit = (
        "environment_setup_commit"
        if "environment_setup_commit" in instance
        else "base_commit"
    )
    for req_path in swebench_related_constants.MAP_REPO_TO_ENV_YML_PATHS[
        instance["repo"]
    ]:
        reqs_url = os.path.join(
            swebench_related_constants.SWE_BENCH_URL_RAW,
            instance["repo"],
            instance[commit],
            req_path,
        )
        reqs = requests.get(reqs_url)
        if reqs.status_code == 200:
            path_worked = True
            break
    if not path_worked:
        print(
            f"Could not find environment.yml at paths {swebench_related_constants.MAP_REPO_TO_ENV_YML_PATHS[instance['repo']]}"
        )
        return None

    lines = reqs.text.split("\n")
    cleaned = []
    for line in lines:
        # Rename environment to given name
        if line.startswith("name:"):
            cleaned.append(f"name: {env_name}")
            continue
        cleaned.append(line)

    # Return environment.yml as string if no save path given
    if save_path is None:
        return "\n".join(cleaned)

    # Save environment.yml to given path and return path
    path_to_reqs = os.path.join(save_path, "environment.yml")
    with open(path_to_reqs, "w") as f:
        f.write("\n".join(cleaned))
    return path_to_reqs


def get_requirements(instance: Dict, save_path: str = None):
    """
    Get requirements.txt for given task instance

    Args:
        instance (dict): task instance
        save_path (str): If provided, save requirements.txt to this path
    Returns:
        requirements.txt (str): If save_path given, returns path to saved requirements.txt.
            Otherwise, returns requirements.txt as string
    """
    # Attempt to find requirements.txt at each path based on task instance's
    # repo
    path_worked = False
    commit = (
        "environment_setup_commit"
        if "environment_setup_commit" in instance
        else "base_commit"
    )

    for req_path in swebench_related_constants.MAP_REPO_TO_REQS_PATHS[instance["repo"]]:
        reqs_url = os.path.join(
            swebench_related_constants.SWE_BENCH_URL_RAW,
            instance["repo"],
            instance[commit],
            req_path,
        )
        reqs = requests.get(reqs_url)
        if reqs.status_code == 200:
            path_worked = True
            break
    if not path_worked:
        logger.warning(
            f"Could not find requirements.txt at paths {swebench_related_constants.MAP_REPO_TO_REQS_PATHS[instance['repo']]}"
        )
        return None

    lines = reqs.text
    original_req = []
    additional_reqs = []
    req_dir = "/".join(req_path.split("/")[:-1])

    def exclude_line(line):
        return any([line.strip().startswith(x) for x in ["-e .", "#", ".[test"]])

    for line in lines.split("\n"):
        if line.strip().startswith("-r"):
            # Handle recursive requirements
            file_name = line[len("-r") :].strip()
            reqs_url = os.path.join(
                swebench_related_constants.SWE_BENCH_URL_RAW,
                instance["repo"],
                instance[commit],
                req_dir,
                file_name,
            )
            reqs = requests.get(reqs_url)
            if reqs.status_code == 200:
                for line_extra in reqs.text.split("\n"):
                    if not exclude_line(line_extra):
                        additional_reqs.append(line_extra)
        else:
            if not exclude_line(line):
                original_req.append(line)

    # Combine all requirements into single text body
    additional_reqs.append("\n".join(original_req))
    all_reqs = "\n".join(additional_reqs)

    if save_path is None:
        return all_reqs

    path_to_reqs = os.path.join(save_path, "requirements.txt")
    with open(path_to_reqs, "w") as f:
        f.write(all_reqs)
    return path_to_reqs


def conda_pip_list(env_name: str):
    """
    Deactivate all nested conda environments, activate the specified environment, and run 'pip list' to get the list of installed packages.

    Parameters:
        env_name (str): The name of the conda environment to activate.

    Returns:
        str: The list of installed packages as a string.

    Raises:
        Exception: If there is an error while executing the command.
    """
    command = (
        'eval "$(conda shell.bash hook)" && '
        "for i in $(seq $CONDA_SHLVL); do "
        "conda deactivate; "
        # 'echo "Deactivated conda environment"; '
        "done && "
        f"conda activate {env_name} && "
        "pip list"
    )
    result = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        executable="/bin/bash",
    )
    if result.returncode != 0:
        raise Exception(f'Error: {result.stderr.decode("utf-8")}')
    return result.stdout.decode("utf-8")


def get_referenced_directories(env_name: str) -> List:
    """
    Retrieves the referenced directories for a given environment name.

    Args:
        env_name (str): The name of the environment.

    Returns:
        List: A list of tuples containing the package name and the referenced directory path.
    """
    output = conda_pip_list(env_name)
    paths_referenced = []
    _stat = False
    for _line in output.split("\n"):
        elems = _line.split()
        if "-----------------------------------" in _line:
            _stat = True
            continue
        if _stat and len(elems) > 2:
            path_used = elems[-1]
            package_used = elems[0]
            paths_referenced.append((package_used, path_used))
            # assert ("t-agarwalan" in path_used)
    return paths_referenced
