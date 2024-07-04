"""CSharp dataset setup"""

import os
import pickle
import pathlib
import subprocess
import zipfile
import json
import shutil
from typing import Dict

import requests
from repoclassbench.evaluator.csharp_evaluator import (
    CSharpEvaluationMetadata,
    CSharpEvaluator,
)
from repoclassbench.dataset.base_dataset import BaseDataset, TaskData
import gdown
from git import Repo


class CSharpDataset(BaseDataset):
    """Class to load the CSharp dataset."""

    repo_container_dir = "temp/csharp/"
    external_dir = "external/csharp"
    dotnet_executable_path = os.path.join(external_dir, "dotnet")
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
        self._setup_dotnet()
        self._download_data()

    def _setup_dotnet(self) -> None:
        # r = requests.get("https://dot.net/v1/dotnet-install.sh")
        # install_script_str = r.content.decode()
        # script_path = os.path.join(self.repo_container_dir, "dotnet-install.sh")
        # with open(script_path, "w") as f:
        #     f.write(install_script_str)
        # url = 'https://drive.google.com/file/d/1JbiK1ScxS7Y6IkjZhJlbIk0VbXo7BN4k/view?usp=sharing'
        if pathlib.Path(self.dotnet_executable_path).is_file():
            return
        tarball_url = "https://drive.google.com/uc?id=1JbiK1ScxS7Y6IkjZhJlbIk0VbXo7BN4k"
        gdown.download(
            tarball_url,
            os.path.join(self.external_dir, "dotnet-sdk-8.0.301-linux-x64.tar.gz"),
            quiet=False,
        )
        subprocess.check_call(
            "tar -xzvf dotnet-sdk-8.0.301-linux-x64.tar.gz",
            shell=True,
            cwd=self.external_dir,
        )

    def _download_data(self) -> None:
        # If non-empty skip download
        if len(os.listdir(self.original_repo_dir)) > 0:
            return

        data_url = "https://drive.google.com/uc?id=1B1WM1G7E8Tcy3VpGPIgcKDB8w49zdtql"
        gdown.download(
            data_url,
            os.path.join(self.repo_container_dir, "csharp_repos.zip"),
            quiet=False,
        )
        with zipfile.ZipFile(
            os.path.join(self.repo_container_dir, "csharp_repos.zip"), "r"
        ) as zip_ref:
            zip_ref.extractall(self.repo_container_dir)
        extracted_folder_path = os.path.join(
            self.repo_container_dir, "LLMTools_dataset"
        )
        os.rename(extracted_folder_path, self.original_repo_dir)
        # Below code creates a git index for each repo
        # So, for each task, after a change, we can revert back to the original state
        for dirpath in os.listdir(self.original_repo_dir):
            repo = Repo.init(os.path.join(self.original_repo_dir, dirpath))
            repo.index.add(repo.untracked_files)
            repo.index.commit("Initial commit")

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
        print("Delete all files which are a part of the test suite")
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
