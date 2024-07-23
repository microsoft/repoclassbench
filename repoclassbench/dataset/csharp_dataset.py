"""CSharp dataset setup"""

import os
import json
import shutil
import pickle
import logging
import pathlib
from typing import Dict
from repoclassbench.evaluator.csharp_evaluator import (
    CSharpEvaluationMetadata,
    CSharpEvaluator,
)
from repoclassbench.dataset.base_dataset import BaseDataset, TaskData
from project_utils.csharp_setup_utils import setup_dotnet, download_data, PROJECT_ROOT_DIR, DOTNET_ROOT_DIR

class CSharpDataset(BaseDataset):
    """Class to load the CSharp dataset."""

    repo_container_dir = os.path.join(PROJECT_ROOT_DIR, "temp/csharp/")
    dotnet_executable_path = os.path.join(DOTNET_ROOT_DIR, "dotnet")
    original_repo_dir = os.path.join(repo_container_dir, "original_repo")
    working_repo_dir = os.path.join(repo_container_dir, "working_repo")
    eval_repo_dir = os.path.join(repo_container_dir, "eval_repo")

    def __init__(self, specification: str, delete_relatives: bool) -> None:
        self.specification = specification
        self.delete_relatives = delete_relatives
        self.data = json.load(open("data/input/csharp_data.json", "r"))
        pathlib.Path(self.original_repo_dir).mkdir(parents=True, exist_ok=True)
        # TODO: Check with security team whether external dir can be uploaded to GitHub
        # If yes, below line becomes redundant
        pathlib.Path("external").mkdir(parents=True, exist_ok=True)
        setup_dotnet()    # ENV-var setup takes place in csharp_setup_utils automatically
        download_data()

    def __len__(self) -> int:
        return len(self.data)

    def get_instance_and_setup_env(self, i: int) -> TaskData:
        data_instance = self.data[i]
        task_fname = data_instance["file"]
        original_repo_path = os.path.join(
            self.original_repo_dir, data_instance["repo_metadata"]["repo_name"]
        )
        working_repo_path = os.path.join(
            self.working_repo_dir, data_instance["repo_metadata"]["repo_name"]
        )
        eval_repo_path = os.path.join(
            self.eval_repo_dir, data_instance["repo_metadata"]["repo_name"]
        )

        if pathlib.Path(working_repo_path).exists():
            shutil.rmtree(working_repo_path)
        ## Copy the original repo to working repo
        shutil.copytree(original_repo_path, working_repo_path)

        if self.delete_relatives:
            raise NotImplementedError("Not yet implemented for CSharp")
            cousins_info_fpath = os.path.join(working_repo_path, "cousins_info.pkl")
            with open(cousins_info_fpath, "rb") as f:
                cousins_info: Dict = pickle.load(f)
            cousins_list = cousins_info.get(task_fname, [])
            for cousin_fpath in cousins_list:
                os.remove(cousin_fpath)

        ## Delete the test code. This should only be available during evaluation and not in the working repo.
        logging.warning("Delete all files which are a part of the test suite")
        for test_prefix in data_instance["repo_metadata"]["test_prefix"]:
            for fpath in pathlib.Path(working_repo_path).glob(
                f"{test_prefix}/" + "**/*.cs"
            ):
                with open(fpath, "w") as f:
                    pass

        # TODO: Check if the filepath contains repo name
        with open(os.path.join(original_repo_path, data_instance["file"]), "r") as file:
            ground_truth = file.read()

        return TaskData(
            file=task_fname,
            class_name=data_instance["class_name"],
            description=(
                data_instance["detailed_description"]
                if self.specification == "detailed"
                else data_instance["sketchy_description"]
            ),
            evaluator=CSharpEvaluator(
                repo_name=data_instance["repo_metadata"]["repo_name"],
                file_name=task_fname,
                evaluation_metadata=CSharpEvaluationMetadata(
                    original_dir=original_repo_path,
                    eval_dir=eval_repo_path,
                    **data_instance["evaluation_metadata"],
                ),
                executable_path=self.dotnet_executable_path,
            ),
            repo_dir=working_repo_path,
            repo_metadata=data_instance["repo_metadata"],
            ground_truth=ground_truth,
        )
