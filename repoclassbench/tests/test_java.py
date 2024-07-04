import unittest
from repoclassbench.dataset import Dataset


class TestJava(unittest.TestCase):
    """Class to test the Java dataset."""

    def test_blank(self):
        """Test with blank input."""
        dataset = Dataset(
            language="java", specification="detailed", delete_relatives=False
        )
        for i in range(len(dataset))[:1]:
            task = dataset.get_instance_and_setup_env(i)
            blank_input = ""
            evaluator = task.evaluator
            evaluation_status = evaluator.evaluate(blank_input)
            self.assertEqual(evaluation_status.passed_tests, 0)

    def test_ground_truth(self):
        """Test with ground truth."""
        dataset = Dataset(
            language="java", specification="detailed", delete_relatives=False
        )
        for i in range(len(dataset))[:1]:
            task = dataset.get_instance_and_setup_env(i)
            ground_truth = task.ground_truth
            evaluator = task.evaluator
            evaluation_status = evaluator.evaluate(ground_truth)
            self.assertEqual(evaluation_status.failed_tests, 0)
