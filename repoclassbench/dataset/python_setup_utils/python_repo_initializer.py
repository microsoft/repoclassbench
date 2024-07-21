from typing import Final
import os
import json
import sys
from repoclassbench.dataset.python_setup_utils import (
    data_utils,
    git_related_utils,
    swebench_related_constants,
)

# absolute imports
from project_utils import common_utils as utils
from project_utils.constants import PythonConstants

logger = utils.fetch_ist_adjusted_logger()


def fetch_linter_errors(file_name):
    """
    Fetches linter errors for a specified Python file within a specified conda environment.

    This function activates the given conda environment, runs pylint to find errors in the
    specified file, and filters the errors based on a predefined set of message IDs.

    Parameters:
    - file_name (str): The path to the Python file to lint.
    - env_name (str): The name of the conda environment to use for linting.

    Returns:
    - dict: A dictionary containing a list of filtered linter errors and a hint string
            with error messages formatted for display.
    """
    # Get the path to the current Python executable, assuming it's within the conda environment
    env_path = sys.executable
    assert "/bin/python" in env_path
    env_path = env_path.replace("/bin/python", "")

    logger.debug("Going to find linter errors for file: %s", file_name)
    # logger.debug("File content is: %s", file_content)  # Uncomment for debugging

    # Define a bash script to activate the conda environment and run pylint
    bash_script = f"""
#!/bin/bash

eval "$(conda shell.bash hook)"
conda activate {env_path}

pylint --errors-only --output-format=json {file_name}
    """
    # Execute the bash script and capture the result
    res = utils.execute_bash_script(bash_script)

    try:
        # Parse the JSON output from pylint
        json_arr = json.loads(res["stdout"])
    except Exception as E:
        # Log the result and the exception if JSON parsing fails
        logger.debug(f"Result: {json.dumps(res, indent=1)}")
        logger.exception(f"Some error in reading pylint json output: {E}")
        json_arr = []
        raise E

    # Filter out errors that are not of type "error"
    json_arr = [x for x in json_arr if x["type"] == "error"]

    # Define a set of message IDs to keep
    keep_message_ids = set(
        [
            "E0102",  # function-redefined
            "E0103",  # not in loop
            "E0104",  # return outside function
            # no value for parameter (less arguments supplied than needed)
            "E1120",
            "E0602",  # undefined variable
        ]
    )

    # Filter the errors based on the keep_message_ids set
    json_arr = [x for x in json_arr if x["message-id"] in keep_message_ids]

    # Read the file content again and split into lines
    content_now = open(file_name, "r").read()
    all_lines = content_now.split("\n")
    error_df = {}
    # Organize errors by line number
    for _err in json_arr:
        _err["line"] = _err["line"] - 1
        if _err["line"] not in error_df:
            error_df[_err["line"]] = []
        error_df[_err["line"]].append(f"[{_err['message-id']}]  {_err['message']}")

    # Construct a hint string with error messages
    hint_str = ""
    for _line, _errors in error_df.items():
        hint_str += (
            f"Line {_line+1} | {all_lines[_line]} | Errors: {' ; '.join(_errors)}\n"
        )

    return {"error_list": json_arr, "hint_str": hint_str}


@utils.with_tempfile(prefix="tmp_import_py_")
def remove_unused_imports(file_content, temp_file=None):
    """
    Removes unused imports from the given file content.

    Args:
        file_content (str): The content of the file to remove unused imports from.
        temp_file (file): A temporary file object to write the modified content to.

    Returns:
        str: The modified content after removing unused imports.
    """
    assert temp_file is not None
    temp_file_path = temp_file.name
    with open(temp_file_path, "w") as f:
        f.write(file_content)
    logger.debug(f"Running import-removal ruff on {temp_file_path}")
    bash_script = f"""
#!/bin/bash

eval "$(conda shell.bash hook)"


conda activate swe-bench
ruff --fix --fix-only --fixable F401 --show-fixes {temp_file_path}  --output-format json
    """
    utils.execute_bash_script(bash_script)

    new_content = open(temp_file_path, "r").read()
    logger.debug(
        f"After useless import removal, truncated from: {len(file_content)} to {len(new_content)}"
    )
    return new_content


class PythonRepoInitializer:
    """
    A class to initialize and manage the state of a Python repository for testing and development.

    This class performs the following tasks:
    1. Ensures the repository is in its final state by:
       - Installing necessary environments.
       - Cloning the repository.
       - Ensuring the repository is in perfect working condition.
    2. Provides functionality to remove specific classes related to test case generation.
    3. Creates a placeholder for the class body and removes single-dependent imports.
    """

    PLACEHOLDER_TEXT = "# <MSR CLASS PLACEHOLDER>"

    def __init__(self, repotools_task_id):
        self.REPOTOOLS_TASK_ID = repotools_task_id

        # Fetch the repository tools task element using the task ID
        self.REPOTOOLS_ELEM = data_utils.fetch_repotools_task_elem(
            self.REPOTOOLS_TASK_ID
        )

        # Set the configuration object
        self.config_obj = PythonConstants

        self.SWEBENCH_ISSUE_ID: Final[str] = self.REPOTOOLS_ELEM["repo_metadata"][
            "issue_id"
        ]

        # Set the repository directory path
        self.REPO_DIR: Final[str] = os.path.normpath(
            os.path.abspath(
                os.path.join(PythonConstants.TESTBED_FOR_REPOS, self.SWEBENCH_ISSUE_ID)
            )
        )

        self.CONDA_ENV_NAME: Final[str] = self.SWEBENCH_ISSUE_ID

        # Get installation preferences like version of python to install etc
        self.SWEBENCH_ELEM = self.REPOTOOLS_ELEM["repo_metadata"]["setup_details"]
        if self.SWEBENCH_ELEM is None:
            # If no specific element is found, use default installation settings
            assert "litestar" in self.SWEBENCH_ISSUE_ID
            self.install_related_obj = {
                "python": "3.8",
                "install": "pdm install --dev ; pip install -e .",
            }
        else:
            # Use the installation settings from the fetched swebench element
            self.install_related_obj = (
                swebench_related_constants.MAP_VERSION_TO_INSTALL[
                    self.SWEBENCH_ELEM["repo"]
                ][self.SWEBENCH_ELEM["version"]]
            )

    @property
    def CONDA_ENV_PATH(self):
        """Path to the conda environment used for the task"""
        return os.path.join(PythonConstants.CONDA_PREFIX, 'envs', self.CONDA_ENV_NAME, 'bin', 'python')
        # return f"/anaconda/envs/{self.CONDA_ENV_NAME}/bin/python"

    @property
    def use_dir_for_dump_path(self):
        """The below directory is used to store certain temporary files such as requirements.txt, environment.yaml"""
        dir_path = os.path.join(
            self.config_obj.TMP_FOLDER_FOR_PYTHON, "use_dir_for_dump_path"
        )
        return dir_path

    @property
    def file_to_modify_rel(self):
        """Gets the relative path of the file to be modified. (Relative to the task-repository)"""
        # earlier_path = self.REPOTOOLS_ELEM['global_module']
        earlier_path = self.REPOTOOLS_ELEM["file"]
        sep_token = self.SWEBENCH_ISSUE_ID
        if "litestar" in earlier_path:
            sep_token = "os/litestar"
        assert earlier_path.count(sep_token) == 1
        relative_path = earlier_path.split(sep_token)[1]
        if relative_path.startswith("/"):
            relative_path = relative_path[1:]
        return relative_path

    @property
    def file_to_modify_abs(self):
        """Gets the absolute path of the file to be modified."""
        abs_path = os.path.normpath(
            os.path.join(self.REPO_DIR, self.file_to_modify_rel)
        )
        assert os.path.exists(abs_path)
        return abs_path

    def ensure_ideal_repo_state(self):
        """
        Ensures that:
        (1) Repository is in the final paraphrased state
        (2) No spurious files are present in the repository

        Returns:
            None
        """
        # Check if the repository directory exists
        if os.path.exists(self.REPO_DIR):
            logger.debug(f"Repo dir: {self.REPO_DIR} already exists")
        else:
            # If the repository directory does not exist, copy it from the zip
            _copy_path = os.path.normpath(
                os.path.abspath(
                    os.path.join(
                        self.config_obj.directory_with_repos, self.SWEBENCH_ISSUE_ID
                    )
                )
            )
            logger.debug(f"Repo dir: {self.REPO_DIR} copied from: {_copy_path}")
            assert os.path.exists(_copy_path)
            os.system("cp -r %s %s" % (_copy_path, self.REPO_DIR))

        self.commit_id = self.REPOTOOLS_ELEM["repo_metadata"]["commit_id"]

        # Reset the repository to the specific commit
        if not git_related_utils.reset_to_commit(self.REPO_DIR, self.commit_id):
            logger.error("Repo checkout to base commit failed")
            raise Exception("Repo checkout to base commit failed")
        logger.info("Repo checkout to base commit successful.")
        return

    def ensure_final_runnable_state(self, delete_ground_truth_class=False):
        """
        Ensures the repository is in a final runnable state by performing the following steps:

        1. Ensures the repository is in the ideal state by calling `ensure_ideal_repo_state`.
        2. Installs the necessary environment for the repository.
        3. Checks if folder-level installation is needed and performs it if necessary.
        4. Ensures that the repository is being referenced correctly in the environment.
        5. Optionally deletes the ground truth class if specified.

        Args:
            delete_ground_truth_class (bool): If True, deletes the ground truth class.
        Returns:
            None
        """

        logger.info(
            f"[{self.SWEBENCH_ISSUE_ID}] Going to ensure final_state for: {self.SWEBENCH_ISSUE_ID}"
        )

        logger.info(f"Repo dir: {self.REPO_DIR}")

        # Ensure the repository is in the final state
        self.ensure_ideal_repo_state()

        # Install the environment
        self.run_environment_installation_script()
        logger.info(
            f"[{self.SWEBENCH_ISSUE_ID}] Initial env installation seems to be taken care of."
        )

        # Check if folder-level installation is needed
        _ref_packages = data_utils.get_referenced_directories(self.CONDA_ENV_NAME)
        logger.info("Packages being referenced are: %s", _ref_packages)
        referenced_paths = [x[1] for x in _ref_packages]
        already_referencing = any([self.REPO_DIR in x for x in referenced_paths])

        logger.info(
            f"[{self.SWEBENCH_ISSUE_ID}] Ref packages (initial): {_ref_packages}"
        )

        ##################################################################
        # Handle potential conflicts with already referenced folders
        if len(referenced_paths) > 0:
            logger.debug(
                f"[{self.SWEBENCH_ISSUE_ID}] Uninstalling the already referenced folder"
            )

            # Filter out the repo-package
            uninstallation_commands = [
                f"pip install {x[0]} --upgrade"
                for x in _ref_packages
                if self.REPO_DIR not in x[1]
            ]
            logger.debug(
                "Potential Uninstallation commands: %s", uninstallation_commands
            )
            # Ensure there are no interfering packages
            assert len(uninstallation_commands) == 0

            uninstallation_commands = "\n".join(uninstallation_commands)
            uninstall_bash_script = f"""
#!/bin/bash

eval "$(conda shell.bash hook)"

conda activate {self.CONDA_ENV_NAME}
{uninstallation_commands}
    """
            logger.debug(
                f"[{self.SWEBENCH_ISSUE_ID}] Uninstallation commands script: %s",
                uninstall_bash_script,
            )
            utils.execute_bash_script(uninstall_bash_script)
        #######################################################################

        # If not already referencing, install the folder state
        if not already_referencing:
            logger.info(f"[{self.SWEBENCH_ISSUE_ID}] Not already referencing")
            logger.debug("Referenced dirs: %s" % (referenced_paths))
            logger.debug("Wanted dir: %s" % (self.REPO_DIR))
            # Run the `pip install -e .` specific instructions
            self.run_folder_state_installation_script(self.REPO_DIR)
        else:
            logger.info(f"[{self.SWEBENCH_ISSUE_ID}] Already referencing")

        ######################################################
        # Ensure the repository is now being referenced
        _ref_packages = data_utils.get_referenced_directories(self.CONDA_ENV_NAME)
        logger.info(
            f"[{self.SWEBENCH_ISSUE_ID}] Later (ref packages): %s", _ref_packages
        )
        referenced_paths = [x[1] for x in _ref_packages]
        already_referencing = any([self.REPO_DIR in x for x in referenced_paths])
        logger.debug(
            f"Is {self.REPO_DIR} being referenced after all environment-related setup: {already_referencing}"
        )
        assert already_referencing
        assert len(referenced_paths) == 1

        # Optionally delete the ground truth class
        if delete_ground_truth_class:
            self.delete_ground_truth_class()

    def delete_ground_truth_class(self, remove_useless_imports=True):
        """
        Delete the ground truth class from the repository.

        Args:
            remove_useless_imports (bool): Flag indicating whether to remove useless imports.
                                            Defaults to True.

        Raises:
            AssertionError: If the ground truth class is not found in the file.

        """
        # Ensure there is no linter error with the ground truth class
        _linter_error_df_on_gt = fetch_linter_errors(self.file_to_modify_abs)
        self.gt_has_linter_error = False
        if len(_linter_error_df_on_gt["error_list"]) > 0:
            logger.error(
                f"Ground truth file has linter errors. Please fix them first: {_linter_error_df_on_gt['hint_str']}"
            )
            self.gt_has_linter_error = True
            # assert(False)

        # Extract the ground truth implementation of the class
        _ground_truth_file_body = open(self.file_to_modify_abs, "r").read()
        _ground_truth_class_body = self.REPOTOOLS_ELEM["ground_truth_class_body"]
        assert _ground_truth_file_body.count(_ground_truth_class_body) == 1

        # Replace the ground truth class with a placeholder text
        _ground_truth_file_body_without_class = _ground_truth_file_body.replace(
            _ground_truth_class_body, self.PLACEHOLDER_TEXT
        )

        # Remove useless imports (ie those imports which were only depended on by the ground truth class)
        if remove_useless_imports:
            _ground_truth_file_body_after_removing_useless_imports = (
                remove_unused_imports(_ground_truth_file_body_without_class)
            )
        else:
            _ground_truth_file_body_after_removing_useless_imports = (
                _ground_truth_file_body_without_class[:]
            )

        # Rewrite the file with the ground truth class removed and with useless imports removed
        with open(self.file_to_modify_abs, "w") as f:
            f.write(_ground_truth_file_body_after_removing_useless_imports)
        assert (
            _ground_truth_file_body_after_removing_useless_imports.count(
                _ground_truth_class_body
            )
            == 0
        )
        logger.debug(f"Ground truth class removed from: {self.file_to_modify_abs}")

    def run_environment_installation_script(self):
        """Runs the top-level environment installation script.

        This method is responsible for executing the environment installation process.
        It checks if the Conda environment already exists and skips the installation if it does.
        It handles different types of package installations based on the provided configuration.
        After executing the installation script, it checks the exit status and logs any errors encountered.

        Returns:
            None
        """
        logger.debug(
            f"[{self.SWEBENCH_ISSUE_ID}] [Environment installation] Fetching environment installation script"
        )

        self.init_install_result = {
            "stdout": "None <Command did not run>",
            "stderr": "None <Command did not run>",
            "exit_status": None,
        }

        # Check if the Conda environment already exists
        if self.CONDA_ENV_NAME in data_utils.get_conda_environments():
            logger.debug(
                "Conda env already exists, so skipping environment installation"
            )
            return

        ####################
        # Set default commands for installation
        defaults = {
            k: ""
            for k in [
                "requirements_cmd",
                "environment_yaml_cmd",
                "pip_cmd",
                "pip_packages_cmd",
                "requirements_pip_cmd",
                "yaml_pip_cmd",
            ]
        }
        defaults["env_name"] = self.CONDA_ENV_NAME

        # Determine the type of package installation
        self.install_packages_type = (
            self.install_related_obj["packages"]
            if "packages" in self.install_related_obj
            else ""
        )

        set_val = {}

        # Handle different types of package installations
        if self.install_packages_type == "requirements.txt":
            # Command to create a Conda environment with a specific Python version
            cmd_use = f"conda create -n {self.CONDA_ENV_NAME} python={self.install_related_obj['python']} -y"
            set_val["requirements_cmd"] = cmd_use
            # Get the path to the requirements.txt file
            path_to_reqs = data_utils.get_requirements(
                self.SWEBENCH_ELEM, self.use_dir_for_dump_path
            )
            # Command to install packages from requirements.txt using pip
            set_val["requirements_pip_cmd"] = f"pip install -r {path_to_reqs}"
        elif self.install_packages_type == "environment.yml":
            # Get the path to the environment.yml file
            path_to_reqs = data_utils.get_environment_yml(
                self.SWEBENCH_ELEM, self.CONDA_ENV_NAME, self.use_dir_for_dump_path
            )
            if not (
                "no_use_env" in self.install_related_obj
                and self.install_related_obj["no_use_env"]
            ):
                # Command to create a Conda environment from environment.yml
                cmd_use = f"conda env create --file {path_to_reqs}"
                set_val["environment_yaml_cmd"] = cmd_use
            else:
                # Command to create a Conda environment with a specific Python version
                cmd_use = f"conda create -c conda-forge -n {self.CONDA_ENV_NAME} python={self.install_related_obj['python']} -y"
                set_val["environment_yaml_cmd"] = cmd_use
                # Command to update the Conda environment from environment.yml
                set_val["yaml_pip_cmd"] = f"conda env update -f {path_to_reqs}"
        else:
            # Command to create a Conda environment with specific packages
            _pkgs = self.install_packages_type
            cmd_use = f"conda create -n {self.CONDA_ENV_NAME} python={self.install_related_obj['python']} {_pkgs} -y"
            set_val["pip_cmd"] = cmd_use

        ##################################
        # Handle additional pip packages
        if "pip_packages" in self.install_related_obj:
            _pip_pkgs = self.install_related_obj["pip_packages"]
            set_val["pip_packages_cmd"] = f"pip install {_pip_pkgs}"
        if "litestar" in self.SWEBENCH_ISSUE_ID:
            assert "litestar" in self.SWEBENCH_ISSUE_ID
            # Read and set the specific installation script for litestar
            set_val["pip_packages_cmd"] = (
                "\n"
                + open(
                    os.path.join(
                        PythonConstants.ProjectDir,
                        "repoclassbench/dataset/python_setup_utils/script_templates/03_litestar_specific_installation.txt",
                    )
                ).read()
                + "\n"
            )
        #############################

        # Merge default and specific commands
        args_use = {**defaults, **set_val}

        # Read and format the bash template for environment installation
        with open(
            os.path.join(
                PythonConstants.ProjectDir,
                "repoclassbench/dataset/python_setup_utils/script_templates/00_environment_installation.sh",
            ),
            "r",
        ) as f:
            bash_template = f.read()
        self.init_install_bash_script = bash_template.format(**args_use)

        # Execute the bash script for environment installation
        self.init_install_result = utils.execute_bash_script(
            self.init_install_bash_script
        )

        # Check if the script execution was successful
        if self.init_install_result["exit_status"] != 0:
            logger.error(
                f"During environment installation, the exit status was {self.init_install_result['exit_status']} and the following error was encountered: {self.init_install_result['stderr']}"
            )

        logger.debug("Environment installation (top-level) complete")

    def run_folder_state_installation_script(self, repo_dir_path: str):
        """Run folder-specific environment installation script.

        Args:
            repo_dir_path (str): The path to the repository directory.

        Returns:
            None
        """

        # Store the directory path for folder state installation
        self.last_dir_for_folder_state_installation = repo_dir_path

        # Ensure the provided path exists and is a directory
        assert os.path.exists(repo_dir_path) and os.path.isdir(repo_dir_path)

        # Initialize the installation result dictionary with default values
        self.dir_install_result = {
            "stdout": "None <Command did not run>",
            "stderr": "None <Command did not run>",
            "exit_status": None,
        }

        # Log the start of fetching the folder state installation script
        logger.debug(
            f"[{self.SWEBENCH_ISSUE_ID}] [Folder state installation] Fetching folder state installation script"
        )

        # Initialize default arguments for the installation commands
        defaults = {k: "" for k in ["pre_install_cmd", "main_install_cmd"]}
        args_use = dict()

        # Set the environment name and repository directory path
        args_use["env_name"] = self.CONDA_ENV_NAME
        args_use["repo_dir_path"] = repo_dir_path

        # Set the base commit ID if it's not related to 'litestar'
        args_use["base_commit_id"] = self.commit_id

        # Handle pre-install and main install commands if they exist in the installation object
        if "pre_install" in self.install_related_obj:
            args_use["pre_install_cmd"] = self.install_related_obj["pre_install"]
        if "install" in self.install_related_obj:
            args_use["main_install_cmd"] = self.install_related_obj["install"]

        # Merge default arguments with the ones to be used
        args_use = {**defaults, **args_use}

        # Read the bash template for folder state installation and format it with the arguments
        with open(
            os.path.join(
                PythonConstants.ProjectDir,
                "repoclassbench/dataset/python_setup_utils/script_templates/01_tc_specific_installation.sh",
            ),
            "r",
        ) as f:
            bash_template = f.read()

        self.dir_install_bash_script = bash_template.format(**args_use)

        # Log the formatted bash script
        logger.debug(
            f"[{self.SWEBENCH_ISSUE_ID}] [Folder state installation] Bash script: %s"
            % self.dir_install_bash_script
        )

        # Execute the bash script and store the result
        self.dir_install_result = utils.execute_bash_script(
            self.dir_install_bash_script
        )

        # Check if the script execution was successful, log errors if any
        if self.dir_install_result["exit_status"] != 0:
            logger.error(
                f"During Folder state installation, the exit status was {self.dir_install_result['exit_status']} and the following error was encountered: {self.dir_install_result['stderr']}"
            )

        # Log the stdout and stderr outputs of the script execution
        logger.debug("STDout Output: %s", self.dir_install_result["stdout"])
        logger.debug("STDerr Output: %s", self.dir_install_result["stderr"])

        # Log the completion of the folder state installation
        logger.debug("[Folder state installation] Complete")
