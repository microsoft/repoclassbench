"""Java evaluator"""

from dataclasses import dataclass
import os
import re
import shutil
import subprocess
from repoclassbench.evaluator.base_evaluator import BaseEvaluator, EvaluationData
from tree_sitter_languages import get_parser


@dataclass
class JavaEvaluationMetadata:
    """Metadata required for creating the evaluator object"""

    test_file: str  # Name of the file to be generated
    test_class_name: str  # Name of the class to be generated


parser = get_parser("java")


def get_method_body(method_name, line, file_content):
    """Finds start and end line of a node.
    :return: start line, end line
    """
    try:
        method_name = method_name.decode("utf-8")
    except:
        pass

    method_from_start = "\n".join(
        file_content.split("\n")[line - 1 :]
    )  ##Making the assumption that the signature fits in one line
    flag = False
    flag2 = False
    flag_name = False
    bracket_count = 0
    for i, c in enumerate(method_from_start):
        if c == '"':
            flag2 = not flag2
        if not flag_name:
            if method_from_start[i : i + len(method_name)] == method_name:
                flag_name = True
            continue
        elif not flag:
            if c == "{":
                flag = True
                bracket_count = 1
            continue
        else:
            if c == "{" and (not flag2):
                bracket_count += 1
            elif c == "}" and (not flag2):
                bracket_count -= 1
        if bracket_count == 0:
            return method_from_start[: i + 1]
    ### We have failed to return the method here, so lets just return everything
    return method_from_start


def filter_nodes(root_node, node_types):
    method_definitions = []

    # Traverse the tree in a depth-first manner
    stack = [root_node]

    while stack:
        node = stack.pop()

        # Check if the node represents a method or constructor declaration in Java
        if node.type in node_types:
            method_definitions.append(node)

        # Push child nodes onto the stack for further exploration
        for child in node.children:
            stack.append(child)

    return method_definitions


def extract_method_info(node, java_code):
    method_name = None
    method_code = None
    method_signature = None

    for child in node.children:
        if child.type == "formal_parameters":
            method_signature = child.text
        if child.type == "identifier":
            method_name = child.text
            # Include parameters in method name
            if method_signature:
                method_name += method_signature
        elif child.type == "block":
            start_line = child.start_point[0]
            method_code = get_method_body(method_name, start_line, java_code)
    return method_name.decode() + method_signature.decode(), method_code


def extract_class_info(node):
    for child in node.children:
        if child.type == "identifier":
            class_name = child.text
    return class_name


def get_tree_from_text(text):
    classes = {}
    root_node = parser.parse(bytes(text, "utf8")).root_node
    class_definitions = filter_nodes(
        root_node, ["record_declaration", "class_declaration"]
    )
    for class_node in class_definitions:
        method_definitions = filter_nodes(
            root_node, ["method_declaration", "constructor_declaration"]
        )
        class_info = {}
        for method in method_definitions:
            method_name, method_code = extract_method_info(method, text)
            if method_code == None:
                continue
            class_info[method_name] = method_code
        classes[extract_class_info(class_node).decode()] = class_info
    return classes


class JavaEvaluator(BaseEvaluator):
    """Java class for running evaluation"""

    def __init__(
        self,
        repo_name: str,
        file_name: str,
        evaluation_metadata: JavaEvaluationMetadata,
    ) -> None:
        self.repo_name = repo_name
        self.file_name = file_name
        self.evaluation_metadata = evaluation_metadata

        ## Create a copy of the original repo for evaluation
        shutil.copytree(
            "temp/java/original_repo/" + self.repo_name,
            "temp/java/eval_repo/" + self.repo_name,
            dirs_exist_ok=True,
        )

        ## Setup the environment for evaluation
        self.java_home = os.path.join(
            os.path.dirname(__file__), "../../external/java/jdk-17.0.6/"
        )
        self.mvn_path = os.path.join(
            os.path.dirname(__file__), "../../external/java/apache-maven-3.8.7/bin/mvn"
        )

        self.final_code_dir = "temp/java/eval_repo/"
        ## Find the directory with the pom.xml file
        for subdir in self.file_name.split("/"):
            self.final_code_dir = os.path.join(self.final_code_dir, subdir)
            if os.path.isfile(os.path.join(self.final_code_dir, "pom.xml")):
                break

        ## Get the total number of tests
        with open(
            "temp/java/eval_repo/" + self.evaluation_metadata.test_file, "r"
        ) as file:
            self.total_tests = file.read().count("@Test")

        ## Get the correct package statement (We assume access to this)
        with open("temp/java/eval_repo/" + self.file_name, "r") as file:
            self.correct_package_statement = [
                line for line in file.read().split("\n") if "package" in line
            ][0]

    def evaluate(self, code: str) -> EvaluationData:
        """Method to evaluate the code."""

        if not self.content_filer("java", code):
            raise Exception("Code is malicious")
        
        exit()

        # Replace the package statement with the correct statement
        if "package " in code:
            code = re.sub(r"package\s+\S+\s*;", self.correct_package_statement, code)
        else:
            code = self.correct_package_statement + "\n" + code

        # Write the code to the file
        with open("temp/java/eval_repo/" + self.file_name, "w") as file:
            file.write(code)

        # Run the tests
        try:
            java_command = f'export JAVA_HOME={self.java_home} && sudo -E {self.mvn_path} test -Dtest="{self.evaluation_metadata.test_class_name}" -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false'
            java_output = subprocess.check_output(
                java_command,
                shell=True,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.final_code_dir,
            )
            if "Tests run:" not in java_output:
                raise Exception("Tests not run, evaluator failure")

            compilation_failure = False
            test_compilation_failure = False
            test_failure = False

        except subprocess.CalledProcessError as e:

            # Sanitize the output to remove ANSI escape characters
            ansi_escape_pattern = r"\x1B\[[0-?]*[ -/]*[@-~]"
            java_output = re.sub(ansi_escape_pattern, "", e.stdout)

            # Detect the type of failure
            compilation_failure_search = list(
                re.finditer(
                    r"Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin:([\w.-]+):compile",
                    java_output,
                )
            )
            compilation_failure = len(compilation_failure_search) > 0
            test_compilation_failure_search = list(
                re.finditer(
                    r"Failed to execute goal org.apache.maven.plugins:maven-compiler-plugin:([\w.-]+):testCompile",
                    java_output,
                )
            )
            test_compilation_failure = (
                len(test_compilation_failure_search) > 0 or compilation_failure
            )
            test_failure_search = list(
                re.finditer(
                    r"Failed to execute goal org.apache.maven.plugins:maven-surefire-plugin:([\w.-]+):test",
                    java_output,
                )
            )
            test_failure = len(test_failure_search) > 0 or test_compilation_failure

            if (
                not test_failure
            ):  # If the error is not a test failure at least, raise an exception
                raise Exception("Command error" + java_output)

            if compilation_failure:
                java_output = java_output[compilation_failure_search[0].start(0) :]
            elif test_compilation_failure:
                java_output = java_output[test_compilation_failure_search[0].start(0) :]
            elif test_failure:
                try:
                    java_output = java_output[java_output.index("Results :") :]
                except ValueError:
                    java_output = java_output[java_output.index("Results:") :]

            pattern = r"/([^:]+):(\[\d+,\d+\])"

            # Replace references to lines in the code with the actual lines from the file
            matches = re.findall(pattern, java_output)
            relevant_lines = []
            for match in matches:
                try:
                    with open("/" + match[0], "r") as f:
                        relevant_line = f.read().split("\n")[
                            int(match[1].split(",")[0][1:]) - 1
                        ]
                        relevant_lines.append(relevant_line)
                        java_output = java_output.replace(
                            "/" + ":".join(match), relevant_line
                        )
                except FileNotFoundError:
                    pass

        if not test_compilation_failure:
            ## REGEX TO EXTRACT THE NUMBER OF TESTS THAT RAN SUCCESSFULLY
            pattern = re.compile(
                r"Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)",
                re.DOTALL,
            )
            match = pattern.search(java_output)
            passed_tests = (
                int(match.group(1)) - int(match.group(2)) - int(match.group(3))
            )
            failed_tests = int(match.group(2)) + int(match.group(3))
        else:
            passed_tests = 0
            failed_tests = self.total_tests

        if not compilation_failure and test_failure:

            test_text = open(
                "temp/java/eval_repo/" + self.evaluation_metadata.test_file,
                encoding="utf-8",
            ).read()

            test_tree = list(get_tree_from_text(test_text).values())[0]
            print(test_tree)

            def_str = ""
            for test_name in test_tree:
                if test_name.split("(")[0] in java_output:
                    def_str += test_tree[test_name]
            formatted_feedback = (
                java_output[:1000]
                + "... The generated method compiles but there is an error while running the unit test. You cannot change the Test code, but you have made an error in your generation which you need to fix. For more information these are the tests that failed\n"
                + def_str
            )
        else:
            formatted_feedback = (
                java_output[:1000]
                + "... The generated class is incorrect and fails to compile."
            )

        return EvaluationData(
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            compile_status=not compilation_failure,
            error_feedback=java_output,
            formatted_feedback=formatted_feedback,
            test_status=failed_tests == 0,
        )
