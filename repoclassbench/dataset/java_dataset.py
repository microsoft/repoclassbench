"""Java dataset setup"""

import os
import zipfile
import json
import shutil
from repoclassbench.evaluator.java_evaluator import (
    JavaEvaluationMetadata,
    JavaEvaluator,
)
from repoclassbench.dataset.base_dataset import BaseDataset, TaskData
import gdown


class JavaDataset(BaseDataset):
    """Class to load the Java dataset."""

    def __init__(self, specification: str, delete_relatives: bool) -> None:
        self.specification = specification
        self.delete_relatives = delete_relatives
        self.data = json.load(open("data/input/java_data.json", "r"))
        self._download_data()
        ## Extract jdk and maven

        os.makedirs("external/java",exist_ok=True)

        if not os.path.exists("external/java/jdk-17.0.6"):
            if not os.path.exists("external/java/jdk-17.0.6.zip"):
                data_url = "https://drive.google.com/uc?id=1HIJICJgQQvM_LzbSVRdBlQyiD_kY5BNc"
                gdown.download(data_url, "external/java/jdk-17.0.6.zip", quiet=False)            
            with zipfile.ZipFile("external/java/jdk-17.0.6.zip", "r") as zip_ref:
                zip_ref.extractall("external/java")
        
        if not os.path.exists("external/java/apache-maven-3.8.7"):
            if not os.path.exists("external/java/apache-maven-3.8.7.zip"):
                data_url = "https://drive.google.com/uc?id=1JFzF2oAzS8D31fhtpn3uIWhhWJTGG-5i"
                gdown.download(data_url, "external/java/apache-maven-3.8.7.zip", quiet=False)                        
            with zipfile.ZipFile(
                "external/java/apache-maven-3.8.7.zip", "r"
            ) as zip_ref:
                zip_ref.extractall("external/java")
        ## Give permissions
        for root, dirs, files in os.walk("external/java"):
            for d in dirs:
                os.chmod(
                    os.path.join(root, d), 0o777
                )  # Set permissions for directories
            for f in files:
                os.chmod(os.path.join(root, f), 0o777)  # Set permissions for files

    def _download_data(self) -> None:
        if os.path.exists("temp/java/original_repo"):
            return
        
        os.makedirs("temp/java",exist_ok=True)

        data_url = "https://drive.google.com/uc?id=16ZeWM_wKfeBfm7rvsBnksbVJZuLAZ1yo"
        gdown.download(data_url, "temp/java/java_repos.zip", quiet=False)

        extract_dir = "temp/java"
        with zipfile.ZipFile("temp/java/java_repos.zip", "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        extracted_folder_path = os.path.join(extract_dir, "LLMTools_dataset")
        new_folder_name = os.path.join(extract_dir, "original_repo")
        os.rename(extracted_folder_path, new_folder_name)

    def __len__(self) -> int:
        return len(self.data)

    def get_instance_and_setup_env(self, i: int) -> TaskData:
        data_instance = self.data[i]
        if self.delete_relatives:
            raise NotImplementedError("Not implemented yet")
        
        ## Delete the working repo
        if os.path.exists("temp/java/working_repo"):
            shutil.rmtree("temp/java/working_repo")

        ## Copy the original repo to working repo
        shutil.copytree(
            "temp/java/original_repo/" + data_instance["repo_metadata"]["repo_name"],
            "temp/java/working_repo/" + data_instance["repo_metadata"]["repo_name"],
            dirs_exist_ok=True,
        )

        ## Delete the test code. This should only be available during evaluation and not in the working repo.
        for file in os.walk(
            "temp/java/working_repo/" + data_instance["repo_metadata"]["repo_name"]
        ):
            if "src/test" in file and ".java" in file:
                with open(file, "w") as f:
                    pass

        ## Delete ground truth from working repo
        with open("temp/java/working_repo/" + data_instance["file"], "w") as file:
            pass

        ## Read ground truth
        with open("temp/java/original_repo/" + data_instance["file"], "r") as file:
            ground_truth = file.read()

        return TaskData(
            file="/".join(data_instance["file"].split("/")[1:]),
            class_name=data_instance["class_name"],
            description=(
                data_instance["detailed_description"]
                if self.specification == "detailed"
                else data_instance["sketchy_description"]
            ),
            evaluator=JavaEvaluator(
                repo_name=data_instance["repo_metadata"]["repo_name"],
                file_name=data_instance["file"],
                evaluation_metadata=JavaEvaluationMetadata(
                    **data_instance["evaluation_metadata"]
                ),
            ),
            repo_dir="temp/java/working_repo/"
            + data_instance["repo_metadata"]["repo_name"],
            repo_metadata=data_instance["repo_metadata"],
            ground_truth=ground_truth,
        )
