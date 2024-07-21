"""CSharp evaluator"""

from dataclasses import dataclass
import os
import pathlib
import re
import shutil
import subprocess

from repoclassbench.evaluator.base_evaluator import BaseEvaluator, EvaluationData
from typing import List, Optional, Tuple


@dataclass
class CSharpEvaluationMetadata:
    """Metadata required for creating the evaluator object"""

    eval_dir: str  # Directory where the evaluation will be done
    testcase_list: List[Tuple[str, str]]  # Test case identifier and type

    def __init__(self, original_dir, eval_dir: str, testcase_list=[]):
        self.original_dir = original_dir
        self.eval_dir = eval_dir
        self.testcase_list = testcase_list


class CSharpEvaluator(BaseEvaluator):
    """CSharp class for running evaluation"""

    def __init__(
        self,
        repo_name: str,
        file_name: str,
        evaluation_metadata: CSharpEvaluationMetadata,
        executable_path: str,
    ) -> None:
        assert pathlib.Path(
            executable_path
        ).is_file(), f"Executable path {self.executable_path} does not exist"
        self.executable_path = str(pathlib.Path.cwd() / executable_path)
        self.repo_name = repo_name
        self.file_name = file_name
        self.evaluation_metadata = evaluation_metadata
        self.final_code_dir = self.evaluation_metadata.eval_dir
        self.total_tests = len(self.evaluation_metadata.testcase_list)

        # Delete eval dir if it exists from a previous run
        if pathlib.Path(self.evaluation_metadata.eval_dir).exists():
            shutil.rmtree(self.evaluation_metadata.eval_dir)

        ## Create a copy of the original repo for evaluation
        shutil.copytree(
            self.evaluation_metadata.original_dir,
            self.evaluation_metadata.eval_dir,
            dirs_exist_ok=True,
        )

        subprocess.check_call(
            "git restore .", shell=True, cwd=self.evaluation_metadata.eval_dir
        )
        try:
            subprocess.check_output(
                f"stdbuf -o0 {self.executable_path} clean",
                shell=True,
                cwd=self.evaluation_metadata.eval_dir,
                env=os.environ.copy(),
            )
        except subprocess.CalledProcessError as cpe:
            # TODO: add logging code
            pass

    def sanitize_err_lines(self, lines: List[str]):
        sanitized_lines = []
        pattern1 = "(are you missing a using directive or an assembly reference?)"
        pattern2_str = f"\\[{self.final_code_dir}.*\\.csproj\\]"
        pattern2 = re.compile(pattern2_str)
        for line in lines:
            line = line.replace(pattern1, "")
            line = pattern2.sub("", line)
            # See if below line is required
            # line = line.replace(self.containing_dir, "")
            sanitized_lines.append(line)
        return sanitized_lines

    def build_proj(self) -> Tuple[bool, Optional[str], Optional[str]]:
        """Attempts to build the project. Output consists of build status and optional error message"""
        # Ideally below command is better. But in practice, can cause some weird errors
        # build_cmd = f"stdbuf -o0 dotnet build {self.sln_path} --nologo -v m"
        build_cmd = f"stdbuf -o0 {self.executable_path} build --nologo -v m"
        start_header = "Build FAILED.\n"
        try:
            _ = subprocess.check_output(
                build_cmd, shell=True, cwd=self.evaluation_metadata.eval_dir,
                env=os.environ.copy(),
            ).decode()
        except subprocess.CalledProcessError as e:
            err_msg: str = e.output.decode()
            start_idx = err_msg.index(start_header) + len(start_header)
            lines = err_msg[start_idx:].splitlines()
            selected_lines = []
            for line in lines:
                if line.endswith("Warning(s)"):
                    break
                selected_lines.append(line)
            err_lines = [line for line in selected_lines if "error" in line]
            # non_err_lines = [ line for line in selected_lines if "error" not in line ]
            # err_lines.extend(non_err_lines)
            err_lines = self.sanitize_err_lines(err_lines)
            formatted_feedback = (
                "\n".join(err_lines)[:1000]
                + "... The generated class is incorrect and fails to compile."
            )
            return False, err_msg, formatted_feedback
        return True, None, None

    def build_filter_cmd(self, test_filter: List[Tuple[str, str]]) -> str:
        filter_str = []
        for test_entry in test_filter:
            # TestType=\"TestID\" \| ...
            test_id = test_entry[0]
            test_type = test_entry[1]
            if test_type is None:
                # Plain test identifier, no type qualification
                filter_str.append(test_id)
            else:
                # Qualify each test id with its corresp type
                filter_str.append(f"{test_type}={test_id}")
        # When returned, filter string will look something like this:
        # --filter Name=Test1\|FullyQualifiedName=Test2\|Test3
        return "\\|".join(filter_str).replace(" ", "\\ ")

    def run_tests(
        self, test_filter: List[Tuple[str, str]]
    ) -> Tuple[bool, Optional[str], Optional[str], List[str]]:
        filter_str = self.build_filter_cmd(test_filter)
        # Do not use minimal verbosity (-v m). We need normal verbosity to find an anchor in the err msg
        test_cmd = (
            f"stdbuf -o0 {self.executable_path} test --nologo --filter {filter_str}"
        )
        try:
            op = subprocess.check_output(
                test_cmd, cwd=self.final_code_dir, shell=True,
                env=os.environ.copy(),
            ).decode()
            # op = check_output(test_cmd, cwd=self.repo_root_dir).decode()
        except subprocess.CalledProcessError as e:
            op: str = e.output.decode()
            err_msg, failed_testcases = self.parse_test_err_msg(op)
            formatted_feedback = (
                err_msg[:1000]
                + "... The generated method compiles but there is an error while running the unit test. You cannot change the Test code, but you have made an error in your generation which you need to fix."
            )
            # TODO: add code to retrieve failed testcases' src codes
            return False, op, formatted_feedback, failed_testcases
        return True, None, None, []

    def parse_test_err_msg(self, err_msg: str, test_framework="xunit"):
        err_msg = err_msg.strip()
        feedback = []
        if test_framework == "xunit":
            pattern_str = "^\\s+Failed (.*) \\[(.*) m?s\\]$"
            pattern = re.compile(pattern_str)
            lines = err_msg.splitlines()
            err_found_flag = False
            err_lines = []
            testcase_ids = []
            for line in lines:
                match = pattern.match(line)
                if match:
                    # This is the line we are looking for
                    testcase_ids.append(match.group(1))
                    err_found_flag = True
                    err_lines.append(line)
                    continue
                if err_found_flag:
                    if "--- End of stack trace from previous location ---" in line:
                        feedback.append("\n".join(err_lines))
                        err_found_flag = False
                    else:
                        # If we have found the error line, keep appending
                        err_lines.append(line)
            # # Sanitize feedback before returning
            # # No need to preserve abs paths in the feedback. Keep relative paths
            # ds_path = os.path.dirname(self.repo_root_dir.rstrip('/'))
            # if ds_path[-1] != '/':
            #     ds_path += '/'
            return "\n\n".join(feedback), testcase_ids
        else:
            # TODO: Add code for other test frameworks
            raise NotImplementedError("Test framework not supported")

    def evaluate(self, code: str) -> EvaluationData:
        """Method to evaluate the code."""
         
        if not self.content_filer("csharp", code):
            raise Exception("Code is malicious")

        # Write the code to the file
        with open(os.path.join(self.final_code_dir, self.file_name), "w") as file:
            file.write(code)

        compilation_status, build_err, formatted_feedback = self.build_proj()

        if not compilation_status:
            return EvaluationData(
                passed_tests=0,
                failed_tests=self.total_tests,
                compile_status=False,
                test_status=False,
                error_feedback=build_err,
                formatted_feedback=formatted_feedback,
            )

        test_status, test_err, formatted_feedback, failed_tests = self.run_tests(
            self.evaluation_metadata.testcase_list
        )

        return EvaluationData(
            passed_tests=self.total_tests - len(failed_tests),
            failed_tests=len(failed_tests),
            compile_status=True,
            test_status=test_status,
            error_feedback=test_err,
            formatted_feedback=formatted_feedback,
        )
