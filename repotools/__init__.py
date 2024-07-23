from repotools.java_tools import JavaTools
from repotools.python_tools import PythonTools
from repotools.csharp_tools import CSharpTools


class Tools:
    """Tools class"""

    def __init__(self, language: str, repo_root_dir: str, class_name: str = None, file_path: str = None, env_name=None):
        self.language = language

        if self.language == "java":
            self._tools = JavaTools(repo_root_dir, class_name, file_path)
        if self.language == "python":
            self._tools = PythonTools(
                repo_root_dir, file_path, class_name, env_name)
        if self.language == "csharp":
            self._tools = CSharpTools(repo_root_dir, class_name, file_path)
        return None

    def __getattr__(self, attr):
        return getattr(self._tools, attr)
