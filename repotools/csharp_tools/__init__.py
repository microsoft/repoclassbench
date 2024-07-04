"""CSharp class for tools"""

from repotools.base_tools import BaseTools


class CsharpTools(BaseTools):
    """CSharp class for tools"""

    def __init__(self, repo_root_dir: str, class_name: str = None):
        self.repo_root_dir = repo_root_dir

    def get_imports(self, file_content: str) -> str:
        """Returns the suggested imports given the file content"""

    def get_relevant_code(self, search_string: str) -> str:
        """Returns the relevant code snippets given the search string"""

    def get_signature(self, class_name: str, method_name: str) -> str:
        """Returns the signature of the method given the class name and method name"""

    def get_class_info(self, class_name: str, ranking_query_string: str = None) -> str:
        """Returns the class information given the class name"""

    def get_related_snippets(self, search_string: str) -> str:
        """Returns the repocoder code snippets given the search string"""
