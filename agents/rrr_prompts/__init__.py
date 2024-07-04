from agents.rrr_prompts.java_rrr_prompts import JavaPrompts
from agents.rrr_prompts.python_rrr_prompts import PythonPrompts
from agents.rrr_prompts.csharp_rrr_prompts import CsharpPrompts


class Prompts:
    def __init__(self, language, nl_description, file_path):

        if language == "java":
            self._prompts = JavaPrompts(nl_description, file_path)
        elif language == "python":
            self._prompts = PythonPrompts(nl_description, file_path)
        elif language == "csharp":
            self._prompts = CsharpPrompts(nl_description, file_path)

    def __getattr__(self, attr):
        return getattr(self._prompts, attr)
