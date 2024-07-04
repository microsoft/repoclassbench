"""Module to load the dataset."""

from repoclassbench.dataset.java_dataset import JavaDataset
from repoclassbench.dataset.python_dataset import PythonDataset
from repoclassbench.dataset.csharp_dataset import CSharpDataset


class Dataset:
    """Class to load the dataset."""

    def __init__(
        self, language="java", specification="detailed", delete_relatives=False
    ) -> None:
        if language == "java":
            self._dataset = JavaDataset(specification, delete_relatives)
        elif language == "python":
            self._dataset = PythonDataset(specification, delete_relatives)
        elif language == "csharp":
            self._dataset = CSharpDataset(specification, delete_relatives)
        else:
            raise ValueError("Unsupported language")

    def __getattr__(self, attr):
        return getattr(self._dataset, attr)

    def __len__(self):
        return len(self._dataset)
