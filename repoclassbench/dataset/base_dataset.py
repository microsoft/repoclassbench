"""Base class for setting up the environment and returning the dataset"""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass
from repoclassbench.evaluator.base_evaluator import BaseEvaluator


@dataclass
class RepoMetadata:
    """Metadata about the repository"""

    repo_name: str  # The name of the repository
    repo_branch: Optional[str]  # The branch of the repository (optional)
    repo_commit: Optional[str]  # The commit hash of the repository (optional)    


@dataclass
class TaskData:
    """Data structure for a task in the dataset"""

    description: str  # The NL description of the class
    file: str  # The file to be modified
    class_name: str  # The class to be generated
    evaluator: BaseEvaluator  # Evaluator
    ground_truth: str  # The ground truth generation
    repo_metadata: dict  # Metadata about the repository
    repo_dir: str  # The working directory of the repository with deleted tests (accessible to user)


class BaseDataset(ABC):
    """Base class for setting up the environment and returning the dataset"""

    @abstractmethod
    def __init__(self, specification: str, delete_relatives: bool) -> None:
        """Initializes the dataset with the specification and delete_relatives flag"""

    @abstractmethod
    def __len__(self) -> int:
        """Returns the total number of items in the dataset"""

    @abstractmethod
    def get_instance_and_setup_env(self, i: int) -> TaskData:
        """Sets up the environment and returns the i'th element of the dataset"""
