"""Python dataset setup"""

import os
import zipfile
import json
import gdown

from repoclassbench.constants import PythonConstants
from repoclassbench.evaluator.python_evaluator import PythonEvaluator
from repoclassbench.dataset.base_dataset import BaseDataset, TaskData
from repoclassbench.dataset.python_setup_utils.python_repo_initializer import (
    PythonRepoInitializer,
)


class PythonDataset(BaseDataset):
    """Class to load the Python dataset."""

    def __init__(self, specification: str, delete_relatives: bool) -> None:
        assert specification in ["detailed", "sketchy"]
        assert delete_relatives in [True, False]

        self.specification = specification
        self.delete_relatives = delete_relatives

        # Load the dataset from a JSON file
        self.data = json.load(open("data/input/python_data.json", "r"))

        # Download the repositories associated with the dataset
        self._download_data()

    def _download_data(self) -> None:
        """
        This method is responsible for downloading the repositories.
        It downloads a zip file from a given URL and extracts its contents to a specified directory.

        Returns:
            None
        """
        # Get the path where the repositories should be stored
        path_with_repos = PythonConstants.directory_with_repos
        # Define the zip file path for the repositories
        zip_path_with_repos = PythonConstants.directory_with_repos + ".zip"

        # If the path already exists, no need to download again
        if os.path.exists(path_with_repos):
            return

        # URL to download the data from
        data_url = "https://drive.google.com/uc?id=12eRggtWWeoef55EyfcF42QOoBVDCbR9q"
        gdown.download(data_url, zip_path_with_repos, quiet=False)
        assert os.path.exists(zip_path_with_repos)

        # Define the directory to extract the zip file contents
        extract_dir = PythonConstants.TMP_FOLDER_FOR_PYTHON
        # Extract the zip file contents to the specified directory
        with zipfile.ZipFile(zip_path_with_repos, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

    def __len__(self) -> int:
        # Return the number of items in the dataset
        return len(self.data)

    def get_instance_and_setup_env(self, i: int) -> TaskData:
        """
        Retrieves the task instance data at the given index and sets up the environment for the task.

        Args:
            i (int): The index of the task instance to retrieve.

        Returns:
            TaskData: An object containing all the necessary information for the task, including the file to modify,
                      the task description, the evaluator object, the repository directory path, the repository metadata,
                      and the ground truth implementation.
        """
        # Ensure that the index i is within the bounds of the dataset
        assert i < len(self.data)

        # Retrieve the task instance data at index i
        data_instance = self.data[i]

        # Get the RepoClassBench task ID for this task
        repoclassbench_task_id = data_instance["task_id"]

        if self.delete_relatives:
            raise NotImplementedError("Delete relatives (Not implemented yet)")

        # Initialize the task initializer object which can be used to set up the environment
        python_task_initializer = PythonRepoInitializer(repoclassbench_task_id)
        # Ensure the repository is in a runnable state and remove the ground truth class if necessary
        python_task_initializer.ensure_final_runnable_state(
            delete_ground_truth_class=True
        )

        # Fetch the natural language description for the task
        description_use = (
            data_instance["detailed_description"]
            if self.specification == "detailed"
            else data_instance["sketchy_description"]
        )

        ground_truth_implementation = python_task_initializer.REPOTOOLS_ELEM[
            "ground_truth_class_body"
        ]
        repository_directory_path = python_task_initializer.REPO_DIR
        repository_metadata = {}

        # Initialize the evaluator object for the task
        evaluator_obj = PythonEvaluator(repoclassbench_task_id)

        return TaskData(
            file=python_task_initializer.file_to_modify_abs,
            class_name=data_instance["class_name"],
            description=description_use,
            evaluator=evaluator_obj,
            repo_dir=repository_directory_path,
            repo_metadata=repository_metadata,
            ground_truth=ground_truth_implementation,
        )
