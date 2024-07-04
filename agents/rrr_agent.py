from agents.rrr_prompts import Prompts
from repoclassbench import Dataset
from repotools import Tools
from repoclassbench.dataset.base_dataset import BaseDataset

language = "java"

dataset: BaseDataset = Dataset(
    language=language, specification="detailed", delete_relatives=False
)

task = dataset.get_instance_and_setup_env(0)

tools = Tools(language=language, class_name=task, repo_root_dir=task)

prompts = Prompts(
    language=language, nl_description=task.description, file_path=task.file
)
