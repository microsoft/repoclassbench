import os
import shutil
import pathlib
from repoclassbench.dataset.csharp_dataset import CSharpDataset
from repoclassbench.dataset import Dataset


class TestCSharp:

    # def test_ds_download(self):
    #     if pathlib.Path(CSharpDataset.repo_container_dir).exists():
    #         shutil.rmtree(CSharpDataset.repo_container_dir)
    #     ds = CSharpDataset(specification="detailed", delete_relatives=False)
    #     assert pathlib.Path(ds.original_repo).exists()

    def test_blank(self):
        """Test with blank input."""
        dataset: CSharpDataset = Dataset(
            language="csharp", specification="detailed", delete_relatives=False
        )
        for i in range(len(dataset))[:1]:
            task = dataset.get_instance_and_setup_env(i)
            blank_input = ""
            evaluator = task.evaluator
            evaluation_status = evaluator.evaluate(blank_input)
            assert evaluation_status.passed_tests == 0

    def test_ground_truth(self):
        """Test with ground truth."""
        dataset: CSharpDataset = Dataset(
            language="csharp", specification="detailed", delete_relatives=False
        )
        for i in range(len(dataset))[:1]:
            task = dataset.get_instance_and_setup_env(i)
            ground_truth = task.ground_truth
            evaluator = task.evaluator
            evaluation_status = evaluator.evaluate(ground_truth)
            print(ground_truth)
            assert evaluation_status.failed_tests == 0
