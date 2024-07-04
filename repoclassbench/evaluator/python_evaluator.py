from regex import E
from repoclassbench.evaluator.base_evaluator import BaseEvaluator

import os
import json
from typing import Final

from repoclassbench.constants import PythonConstants
import repoclassbench.common_utils as utils
from repoclassbench.dataset.python_setup_utils import (
    data_utils,
    swebench_related_constants,
)
from repoclassbench.dataset.python_setup_utils import python_repo_initializer
from repoclassbench.evaluator.python_evaluator_utils import evaluator_utils
from repoclassbench.evaluator.base_evaluator import EvaluationData

logger = utils.fetch_ist_adjusted_logger()


class PythonEvaluator(BaseEvaluator):
    PLACEHOLDER_TEXT = "# <MSR CLASS PLACEHOLDER>"

    def __init__(self, repotools_task_id):
        self.REPOTOOLS_TASK_ID = repotools_task_id

        # Fetch the task element details using the provided task ID
        self.REPOTOOLS_ELEM = data_utils.fetch_repotools_task_elem(
            self.REPOTOOLS_TASK_ID
        )

        self.SWEBENCH_ISSUE_ID: Final[str] = self.REPOTOOLS_ELEM["repo_metadata"][
            "issue_id"
        ]

        # Define the repository directory path
        self.REPO_DIR: Final[str] = os.path.normpath(
            os.path.abspath(
                os.path.join(PythonConstants.TESTBED_FOR_REPOS, self.SWEBENCH_ISSUE_ID)
            )
        )

        self.CONDA_ENV_NAME: Final[str] = self.SWEBENCH_ISSUE_ID

        # Initialize the Python repository setup object
        self.setup_obj = python_repo_initializer.PythonRepoInitializer(
            repotools_task_id
        )

        # Maximum tokens allowed in feedback
        self.MAX_TOKENS_ALLOWED_IN_FEEDBACK = (
            PythonConstants.MAX_TOKENS_ALLOWED_IN_FEEDBACK
        )

    @property
    def name_of_class_to_generate(self):
        """
        Returns the name of the class to generate based on the global fully qualified domain name (FQDN).

        Returns:
            str: The name of the class to generate.
        """
        return self.REPOTOOLS_ELEM["global_fqdn"].split(".")[-1]

    @property
    def CONDA_ENV_PATH(self):
        return f"/anaconda/envs/{self.CONDA_ENV_NAME}/bin/python"

    @property
    def REPO_NAME(self):
        """
        Fetches the name of the repository or the swebench issue ID.

        Returns:
            str: The repository name.
        """
        repo_name = "-".join(self.SWEBENCH_ISSUE_ID.split("-")[:-1])
        repo_name = repo_name.replace("__", "/")
        return repo_name

    def see_git_status(self):
        """
        Displays the output of 'git status' when called in the repository directory.
        """
        os.system(f"cd {self.REPO_DIR} && git status")

    def evaluate(self, new_class_gen) -> EvaluationData:
        """
        Takes generated code, adds it to the file to be modified, and evaluates the test cases.

        Args:
            new_class_gen (str): The generated class code.

        Returns:
            dict: The evaluation results including parsed and contextually evaluated results.
        """
        # Ensure the repository is in the final runnable state
        self.setup_obj.ensure_final_runnable_state(delete_ground_truth_class=True)
        logger.debug(
            "Abs path of file being modified is: %s", self.setup_obj.file_to_modify_abs
        )

        # Check if the file to modify exists
        curr_file_contents = open(self.setup_obj.file_to_modify_abs, "r").read()
        assert self.PLACEHOLDER_TEXT in curr_file_contents

        # Replace the placeholder text with the generated class code
        new_file_contents = curr_file_contents.replace(
            self.PLACEHOLDER_TEXT, new_class_gen
        )

        # Write the new file contents
        with open(self.setup_obj.file_to_modify_abs, "w") as f:
            f.write(new_file_contents)

        # Evaluate the test cases
        eval_result = self.run_testcases(self.REPO_DIR, run_all_testcases=False)
        parsed_eval_result = evaluator_utils.PytestResults(eval_result["pytest_json"])

        # Contextually evaluate the parsed results
        contextually_evaluated_result = self.contextually_evaluate(
            parsed_eval_result, self.setup_obj.gt_has_linter_error
        )

        # Return the evaluation results in proper format
        evaluation_results_obj = EvaluationData(
            passed_tests=contextually_evaluated_result["summary"]["passed"],
            failed_tests=contextually_evaluated_result["summary"]["total"]
            - contextually_evaluated_result["summary"]["passed"],
            error_feedback=contextually_evaluated_result["feedback_str"],
            evaluation_metadata={
                "eval_result": eval_result,
                "contextually_evaluated_result": contextually_evaluated_result,
            },
            formatted_feedback=contextually_evaluated_result["feedback_str"],
        )

        return evaluation_results_obj

    @utils.with_tempfile(prefix="tmp_json_output_")
    def run_testcases(self, repo_dir_path, run_all_testcases=False, temp_file=None):
        """
        Run test cases using pytest.

        Args:
            repo_dir_path (str): The path to the repository directory.
            run_all_testcases (bool): Whether to run all test cases or not.
            temp_file (NamedTemporaryFile): Temporary file to store pytest results.

        Returns:
            dict: The results of running the test cases.
        """
        assert os.path.exists(repo_dir_path)
        assert os.path.isdir(repo_dir_path)

        self.run_tc_result = {
            "stdout": "None <Command did not run>",
            "stderr": "None <Command did not run>",
            "exit_status": None,
        }

        logger.debug("[Test case execution] Starting process to run test cases ")

        args_use = dict()
        args_use["env_name"] = self.CONDA_ENV_NAME
        args_use["additional_add_pytest_specific"] = ""

        _test_type = swebench_related_constants.MAP_REPO_TO_TEST_FRAMEWORK[
            self.REPO_NAME
        ]

        _test_directives = (
            ""
            if run_all_testcases
            else evaluator_utils.get_test_directives(
                self.REPOTOOLS_TASK_ID, self.REPOTOOLS_ELEM
            )
        )

        args_use["test_cmd"] = f"{_test_type} {' '.join(_test_directives)}"
        args_use["repo_dir_path"] = repo_dir_path

        # Add specific dependencies based on the repository name
        if "pytest-dev__pytest" not in self.CONDA_ENV_NAME:
            args_use[
                "additional_add_pytest_specific"
            ] += 'python -m pip install "pytest<=7.4.4"'
        if "sql" in self.REPO_NAME:
            args_use["additional_add_pytest_specific"] += "\npython -m pip install six"
        if (
            ("pytest" in self.REPO_NAME)
            or ("astroid" in self.REPO_NAME)
            or ("astropy" in self.REPO_NAME)
            or ("scikit" in self.REPO_NAME)
        ):
            args_use[
                "additional_add_pytest_specific"
            ] += "\npip3 install urllib3 idna certifi six coverage attrs tomli requests"
        if (
            ("pytest-dev/pytest" in self.REPO_NAME)
            or ("astroid" in self.REPO_NAME)
            or ("pylint" in self.REPO_NAME)
            or ("requests" in self.REPO_NAME)
        ):
            args_use["additional_add_pytest_specific"] += "\npip3 install numpy"
        if "pydicom" in self.REPO_NAME:
            args_use[
                "additional_add_pytest_specific"
            ] += "\npip3 install pyvista psutil"
        if "pydata" in self.REPO_NAME:
            args_use[
                "additional_add_pytest_specific"
            ] += "\npip3 install pyvista psutil"
        if "pyvista" in self.REPO_NAME:
            args_use["additional_add_pytest_specific"] += "\npip3 install requests"
        if "pylint" in self.REPO_NAME:
            args_use["additional_add_pytest_specific"] += "\npip3 install requests"
        if "requests" in self.REPO_NAME:
            args_use[
                "additional_add_pytest_specific"
            ] += "\npip3 uninstall requests_mock"
        if "litestar" in self.REPO_NAME:
            pass

        assert "pytest" in _test_type
        tmp_file_path = temp_file.name
        args_use[
            "test_cmd"
        ] += f" --json-report --json-report-file={tmp_file_path} --tb=auto --continue-on-collection-errors"

        if run_all_testcases:
            # additional_cmd = self.fetch_files_to_ignore()
            # logger.debug(f"Additional command to ignore files: {additional_cmd}")
            # args_use['test_cmd'] += f" {additional_cmd}"
            pass

        with open(
            os.path.join(
                PythonConstants.ProjectDir,
                "repoclassbench/dataset/python_setup_utils/script_templates/02_test_specific.sh",
            ),
            "r",
        ) as f:
            bash_template = f.read()

        self.run_tc_bash_script = bash_template.format(**args_use)

        self.run_tc_result = utils.execute_bash_script(self.run_tc_bash_script)
        # logger.debug("Bash script used: %s", self.run_tc_bash_script)
        # logger.debug("Stdout Bash script used: %s", self.run_tc_result['stdout'])
        # logger.debug("Stderr Bash script used: %s", self.run_tc_result['stderr'])
        try:
            self.run_tc_result["pytest_json"] = json.load(open(tmp_file_path, "r"))
        except BaseException as E:
            self.run_tc_result["pytest_json"] = None
            # worst case:
            self.run_tc_result["pytest_json"] = {
                "summary": {},
                "comments": "Artificially constructed json",
                "collectors": [
                    {
                        "result": [],
                        "outcome": "failed",
                        "nodeid": "Repository",
                        "longrepr": self.run_tc_result["stderr"],
                    }
                ],
            }
            # surely, some bad import incident has taken place
            logger.exception(
                "Exception occurred while trying to load the pytest json file (%s): %s"
                % (tmp_file_path, E)
            )

        if self.run_tc_result["exit_status"] != 0:
            logger.error(
                f"During running test cases, the exit status was {self.run_tc_result['exit_status']} and the following error was encountered: {self.run_tc_result['stderr']}"
            )

        # logger.debug("[Test case execution] Test case running output: %s" % (self.run_tc_result['stdout']))

        logger.debug("[Test case execution] Complete")
        return self.run_tc_result

    def find_expected_to_pass_tc(self):
        """
        Finds the ground truth functions which are expected to pass.

        Returns:
            list: List of directives expected to pass.
        """
        return self.REPOTOOLS_ELEM["evaluation_metadata"]["test_directives"]

    def contextually_evaluate(self, parsed_eval_result, gt_has_linter_error):
        """
        Contextually evaluates the parsed evaluation result.

        Args:
            parsed_eval_result (PytestResults): The parsed evaluation result.
            gt_has_linter_error (bool): Whether the ground truth has linter errors.

        Returns:
            dict: The contextually evaluated result.
        """
        expected_to_pass = self.find_expected_to_pass_tc()
        actually_passed = [
            x
            for x in expected_to_pass
            if x in parsed_eval_result.test_bifurcation["passed"]
        ]
        actually_failed = [
            x
            for x in expected_to_pass
            if x in parsed_eval_result.test_bifurcation["failed"]
        ]
        neither_passed_nor_failed = [
            x
            for x in expected_to_pass
            if (x not in actually_passed) and (x not in actually_failed)
        ]
        logger.info(
            f"Stats: | Expected to pass: {len(expected_to_pass)} | Actually passed: {len(actually_passed)} | Actually failed: {len(actually_failed)} | Neither passed nor failed: {len(neither_passed_nor_failed)}"
        )

        # Collect failed collectors
        _failed_collectors = [
            x
            for x in parsed_eval_result.pytest_json_to_parse["collectors"]
            if x["outcome"] == "failed"
        ]
        failed_collectors = []
        for _collector in _failed_collectors:
            if _collector in failed_collectors:
                continue
            failed_collectors.append(_collector)
        failed_collector_df = {k["nodeid"]: k["longrepr"] for k in failed_collectors}

        # Gather feedback for each test case
        generate_feedback_for_failed_tc_df = dict()

        all_failed = actually_failed + neither_passed_nor_failed
        for tc_id in all_failed:
            if tc_id not in parsed_eval_result.test_to_details_mapping:
                assert tc_id in neither_passed_nor_failed
                continue
            assert tc_id in parsed_eval_result.test_to_details_mapping
            tc_failure_elem = parsed_eval_result.test_to_details_mapping[tc_id]
            logger.error(f"Test case {tc_id} details. Details: {tc_failure_elem}")
            # assert(tc_failure_elem['outcome'] == 'failed')
            assert tc_failure_elem["outcome"] != "passed"
            generate_feedback_for_failed_tc_df[tc_id] = ""
            for _key in ["setup", "call", "teardown"]:
                if _key in tc_failure_elem:
                    if tc_failure_elem[_key]["outcome"] == "passed":
                        continue
                    generate_feedback_for_failed_tc_df[tc_id] += (
                        tc_failure_elem[_key]["longrepr"] + "\n"
                    )

        # Fetch linter error
        linter_error_df = python_repo_initializer.fetch_linter_errors(
            self.setup_obj.file_to_modify_abs
        )
        logger.debug("Number of lint errors: %s", len(linter_error_df["error_list"]))
        if gt_has_linter_error:
            # Ignore evaluation linter errors also
            linter_error_df["error_list"] = []
            linter_error_df["hint_str"] = ""

        feedback_str = ""
        if (len(linter_error_df["error_list"])) > 0:
            additional_str = "Linter errors detected. Please fix them first. These are linter errors on the whole file and not just the class. Some errors such as symbol not found may either be due to missing imports or missing members in the class."
            feedback_str = f"<Linter Errors>\n{additional_str}\n{linter_error_df['hint_str']}</Linter Errors>\n"
        if True:
            # Sort collector-level feedback
            failed_collector_df = {
                k: v
                for k, v in sorted(
                    failed_collector_df.items(), key=lambda item: len(item[1])
                )
            }
            generate_feedback_for_failed_tc_df = {
                k: v
                for k, v in sorted(
                    generate_feedback_for_failed_tc_df.items(),
                    key=lambda item: len(item[1]),
                )
            }
            for k, v in failed_collector_df.items():
                feedback_to_add = f"<Feedback for collector `{k}`>\n{v}\n</End of feedback for collector>\n"
                if (
                    utils.estimate_token_cnt(feedback_str + feedback_to_add)
                    > self.MAX_TOKENS_ALLOWED_IN_FEEDBACK
                ):
                    pass
                feedback_str += feedback_to_add
            for k, v in generate_feedback_for_failed_tc_df.items():
                feedback_to_add = f"<Feedback for test case `{k}`>\n{v}\n</End of feedback for test case>\n"
                if (
                    utils.estimate_token_cnt(feedback_str + feedback_to_add)
                    > self.MAX_TOKENS_ALLOWED_IN_FEEDBACK
                ):
                    pass
                feedback_str += feedback_to_add
        feedback_str = utils.truncate_string_per_token(
            feedback_str, self.MAX_TOKENS_ALLOWED_IN_FEEDBACK
        )

        logger.debug(
            "Tokens in feedback str: %s", utils.estimate_token_cnt(feedback_str)
        )

        # Remove: Ignoring invalid distribution
        feedback_str = "\n".join(
            [
                x
                for x in feedback_str.split("\n")
                if ("Ignoring invalid distribution" not in x)
            ]
        )

        res = {
            "expected_to_pass": expected_to_pass,
            "actually_passed": actually_passed,
            "actually_failed": actually_failed,
            "neither_passed_nor_failed": neither_passed_nor_failed,
            "generate_feedback_for_failed_tc_df": generate_feedback_for_failed_tc_df,
            "failed_collector_df": failed_collector_df,
            "feedback_str": feedback_str,
            "explicit_linter_feecback": linter_error_df,
            "summary": {
                "passed": len(actually_passed),
                "failed": len(actually_failed) + len(neither_passed_nor_failed),
                "total": len(expected_to_pass),
            },
        }
        res["final_judgement_outcome"] = (
            True if (res["summary"]["passed"] == res["summary"]["total"]) else False
        )
        return res
