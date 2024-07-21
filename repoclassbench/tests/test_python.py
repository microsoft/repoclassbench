from repoclassbench.dataset import Dataset
import pytest

# Retrieve the python dataset
dataset = Dataset(language="python", specification="detailed", delete_relatives=False)

# Collect the indices of the dataset to use for parameterization
dataset_indices = [data_instance["task_id"] for data_instance in dataset.data]
dataset_indices = list(enumerate(dataset_indices))
dataset_indices = [f"{f[1]}!{f[0]}" for f in dataset_indices]


# TODO: comment
# dataset_indices = dataset_indices[::-30]


@pytest.mark.parametrize("test_details", dataset_indices)
def test_blank(test_details):
    """Test with blank input for each element of the dataset."""
    idx_use = int(test_details.split("!")[1])
    task = dataset.get_instance_and_setup_env(idx_use)
    code_test = ""
    evaluator = task.evaluator
    evaluation_status = evaluator.evaluate(code_test)
    # assert(evaluation_status['contextually_evaluated_result']['final_judgement_outcome'] == False)
    assert evaluation_status.passed_tests == 0


@pytest.mark.parametrize("test_details", dataset_indices)
def test_ground_truth(test_details):
    """Test with Ground Truth for each element of the dataset."""
    idx_use = int(test_details.split("!")[1])
    task = dataset.get_instance_and_setup_env(idx_use)
    code_test = task.ground_truth
    evaluator = task.evaluator
    evaluation_status = evaluator.evaluate(code_test)
    assert (
        evaluation_status.passed_tests
        == evaluation_status.passed_tests + evaluation_status.failed_tests
    )
