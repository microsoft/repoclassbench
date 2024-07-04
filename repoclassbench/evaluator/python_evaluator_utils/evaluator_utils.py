import json
from repoclassbench.constants import PythonConstants
import os
import repoclassbench.common_utils as utils
from repoclassbench.dataset.python_setup_utils import data_utils

logger = utils.fetch_ist_adjusted_logger()


def escape_single_quotes(s):
    """
    Escapes single quotes in a string by adding double quotes around them.

    Args:
        s (str): The input string.

    Returns:
        str: The string with single quotes escaped by adding double quotes around them.
    """
    ans = ""
    for c in s:
        if c == "'":
            ans += "'"
            ans += '"'
            ans += "'"
            ans += '"'
            ans += "'"
        else:
            ans += c
    return ans


def get_test_directives(repotools_task_id, repotools_task_elem):
    """
    Retrieves the test directives for a given repotools task ID.

    Args:
        repotools_task_id (str): The repotools task ID.

    Returns:
        list: A list of test directives.

    Raises:
        AssertionError: If the path to the test directives file does not exist.

    """
    if "litestar" in repotools_task_id:
        return []

    test_directives = repotools_task_elem["evaluation_metadata"]["test_directives"]

    for dir in test_directives:
        if "'" in dir:
            print("Has single:", dir)
    # escape single quotes
    test_directives = [escape_single_quotes(x) for x in test_directives]
    test_directives = [f"'{x}'" for x in test_directives]
    return test_directives


class PytestResults:
    """A class to handle the results of pytest execution.

    Args:
        pytest_json_to_parse (dict): The pytest JSON output to parse.

    Attributes:
        pytest_json_to_parse (dict): The pytest JSON output to parse.
        node_type_df (dict): A dictionary to store the node type of each test case or module.
        collected_modules (list): A list to store the node IDs of collected modules.
        collected_functions (list): A list to store the node IDs of collected functions.
        test_bifurcation (dict): A dictionary to categorize test cases based on their outcome.
        test_to_details_mapping (dict): A dictionary to map test case node IDs to their details.
        summary (dict): A dictionary to store the summary of the pytest execution.

    """

    def __init__(self, pytest_json_to_parse):
        self.pytest_json_to_parse = (
            pytest_json_to_parse if pytest_json_to_parse is not None else {}
        )
        self.node_type_df = dict()
        self.format_summary()
        self.find_all_modules()
        self.categorize_testcases()

    def find_all_modules(self):
        """Find all modules and functions in the pytest JSON output."""
        if "collectors" not in self.pytest_json_to_parse:
            self.pytest_json_to_parse["collectors"] = []
            logger.warning("No `collectors` found in the pytest json")

        self.collected_modules = []
        self.collected_functions = []
        for curr_node in self.pytest_json_to_parse["collectors"]:
            for child_node in curr_node["result"]:
                self.node_type_df[child_node["nodeid"]] = child_node["type"]
                if child_node["type"] in ["Function", "TestCaseFunction"]:
                    self.collected_functions.append(child_node)
                elif child_node["type"] == "Module":
                    self.collected_modules.append(child_node["nodeid"])

    def categorize_testcases(self):
        """Categorize test cases based on their outcome."""
        if "tests" not in self.pytest_json_to_parse:
            self.pytest_json_to_parse["tests"] = []
            logger.warning("No `tests` found in the pytest json")

        self.test_bifurcation = {"passed": [], "failed": []}
        self.test_to_details_mapping = {
            elem["nodeid"]: elem for elem in self.pytest_json_to_parse["tests"]
        }
        for curr_test in self.pytest_json_to_parse["tests"]:
            _outcome = curr_test["outcome"]

            assert ("litestar" in self.pytest_json_to_parse["root"]) or curr_test[
                "nodeid"
            ] in self.node_type_df
            if (
                "litestar" not in self.pytest_json_to_parse["root"]
            ) and self.node_type_df[curr_test["nodeid"]] not in [
                "Function",
                "TestCaseFunction",
            ]:
                continue
            if _outcome not in self.test_bifurcation:
                self.test_bifurcation[_outcome] = []
            self.test_bifurcation[_outcome].append(curr_test["nodeid"])

    def format_summary(self):
        """Format the summary of the pytest execution."""
        if "summary" not in self.pytest_json_to_parse:
            self.pytest_json_to_parse["summary"] = {}
            logger.warning("No `summary` found in the pytest json")

        _keys_to_extract = [
            "collected",
            "total",
            "passed",
            "error",
            "skipped",
            "failed",
        ] + list(self.pytest_json_to_parse["summary"].keys())
        self.summary = {
            k: self.pytest_json_to_parse["summary"].get(k, 0) for k in _keys_to_extract
        }
        if self.summary["collected"] == 0:
            logger.warning("Number of nodes collected: 0")
