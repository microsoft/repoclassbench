import os
import sys
import json
import unittest
from repotools import Tools
from project_utils.constants import PythonConstants


def get_virtual_env_name():
    # Infer the name from the path to the Python executable
    executable_path = sys.executable
    path_parts = executable_path.split(os.sep)
    # Look for a directory name typically associated with a virtual environment
    if 'bin' in path_parts:
        env_index = path_parts.index('bin') - 1
        return path_parts[env_index]

    # If none of the above methods worked, we're likely not in a virtual environment
    return None


class TestPython(unittest.TestCase):
    @classmethod
    def setup_class(cls):
        cls.REPO_ROOT_DIR = os.path.join(
            PythonConstants.ProjectDir, "repotools/tests/python/python_minibenchmark")
        cls.RELATIVE_FILE_PATH = "python/test_imports.py"
        cls.CONDA_ENV_NAME = get_virtual_env_name()

        cls.tools_obj = Tools(language="python", class_name=None, repo_root_dir=cls.REPO_ROOT_DIR,
                              file_path=cls.RELATIVE_FILE_PATH, env_name=cls.CONDA_ENV_NAME)
        cls.tools_obj.load_all_fqdns()
        cls.tools_obj.create_fqdn_index()
        cls.tools_obj.prep_embedding_tool()

    def test_get_class_info(self):
        """Test get_class_info"""
        assert (os.path.exists(self.REPO_ROOT_DIR))
        tool_test = "get_class_info('class_A')"
        curr_output = self.tools_obj.execute_statements(tool_test)

        # Output for get_class_info('class_A')
        exp_output = "Class signature: class class_A:\nFile where defined: python/exp.py\nClass full name: python.exp.class_A\nFunctions accessible:\n* Signature: def __init__(self): | Member of `class_A` class\n* Signature: def cal(self): | Member of `class_A` class\n* Signature: def foo(self): | Member of `class_A` class\nClass variables accessible: None\nInstance variables accessible:\n* a1\n* a2\n* a3\n* a4"

        assert (exp_output in curr_output['output'])

    def test_get_imports(self):
        """Test get_imports"""
        assert (os.path.exists(self.REPO_ROOT_DIR))
        tool_test = f"get_imports('{self.RELATIVE_FILE_PATH}')"
        curr_output = self.tools_obj.execute_statements(tool_test)

        # Output for get_imports()
        exp_outputs = ["## Suggestions for symbol `Employee`:\n* from python.check_property import Employee | `python.check_property.Employee` ,  represents a class in the module `python/check_property.py`",
                       "## Suggestions for symbol `class_A`:\n* from python.student_class import class_A | `python.student_class.class_A` ,  represents a class in the module `python/student_class.py`\n* from python.exp import class_A | `python.exp.class_A` ,  represents a class in the module `python/exp.py`",
                       "## Suggestions for symbol `B`:\n* from python.exp import B | `python.exp.B` ,  represents a class in the module `python/exp.py`"]

        for exp_output_snippet in exp_outputs:
            assert (exp_output_snippet in curr_output['output'])

        # defined symbols must not be suggested
        not_expected_to_present = "## Suggestions for symbol `C`:\n* from python.exp import C | `python.exp.C` ,  represents a class in the module `python/exp.py`\n"
        assert (not_expected_to_present not in curr_output['output'])

    def test_get_signature(self):
        """Test get_signature"""
        assert (os.path.exists(self.REPO_ROOT_DIR))
        tool_test = "get_signature('class_A', 'cal')"
        curr_output = self.tools_obj.execute_statements(tool_test)
        expected_output = "## Details about shortlisted result ID 0:\nSignature: def cal(self): | Defined in `./python/exp.py` | Member of `class_A` class"
        assert (expected_output in curr_output['output'])

    def test_get_method_body(self):
        """Test get_method_body"""
        assert (os.path.exists(self.REPO_ROOT_DIR))

        tools_test = ["get_method_body('class_A', 'cal')",
                      "get_method_body('ComplexList', 'msr_add')"]

        expected_outputs = ["## Details about shortlisted result ID 0:\nSignature: def cal(self): | Defined in `./python/exp.py` | Member of `class_A` class\n```python\ndef cal(self):\n        self.a3 =  3\n```",
                            "## Details about shortlisted result ID 0:\nSignature: def msr_add(self): | Defined in `./python/complex_class.py` | Member of `ComplexList` class\n```python\ndef msr_add(self):\n        \"\"\"Adds the elements of two lists of complex numbers and returns the result as a list.\"\"\"\n        if len(self.list1) == len(self.list2):\n            result = [parent_complex_class.Complex(x.r, x.i) + y for x, y in zip(self.list1, self.list2)]\n            return result\n        else:\n            raise ValueError(\"Lists must be of the same length\")\n```"]

        assert (len(tools_test) == len(expected_outputs))

        for tool_test, expected_output in zip(tools_test, expected_outputs):
            curr_output = self.tools_obj.execute_statements(tool_test)
            assert (expected_output in curr_output['output'])

    def test_get_related_snippets(self):
        """Test get_related_snippets"""
        assert (os.path.exists(self.REPO_ROOT_DIR))
        tool_test = "get_related_snippets('about Goliath')"
        curr_output = self.tools_obj.execute_statements(tool_test)
        expected_outputs = ["def initiate_goliath():\n    \"\"\"Returns the string 'goliath'.",
                            "def initiate_goliath():\n    return \"goliath_student\""
                            ]
        for expected_output in expected_outputs:
            assert (expected_output in curr_output['output'])

    def test_get_relevant_code(self):
        """Test get_relevant_code"""
        assert (os.path.exists(self.REPO_ROOT_DIR))
        tool_test = "get_relevant_code('class to deal with Polar Complex numbers')"
        curr_output = self.tools_obj.execute_statements(tool_test)
        expected_outputs = ["Class signature: class PolarComplex(Complex):\nFile where defined: python/complex_class.py\n\nDocstring: \"\"\"A class that represents a complex number in polar form.\"\"\"",
                            "class PolarComplex(Complex):\n    \"\"\"A class that represents a complex number in polar form.\"\"\"\n    angle = 1\n    checker = 4\n    yello = parent_complex_class.Complex(1,\n                                        2)\n    \n    def __init__(self, magnitude, angle):\n        \"\"\"Initializes a complex number in polar form with magnitude and angle.\"\"\"",
                            ]
        for expected_output in expected_outputs:
            assert (expected_output in curr_output['output'])
