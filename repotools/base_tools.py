"""Base class for evaluation"""

from abc import ABC, abstractmethod


class BaseTools(ABC):
    """Base class for tools"""

    @abstractmethod
    def get_imports(self, file_content: str) -> str:
        """Returns the suggested imports given the file content"""

    @abstractmethod
    def get_relevant_code(self, search_string: str) -> str:
        """Returns the relevant code snippets given the search string"""

    @abstractmethod
    def get_signature(self, class_name: str, method_name: str) -> str:
        """Returns the signature of the method given the class name and method name"""

    @abstractmethod
    def get_method_body(self, class_name: str, method_name: str) -> str:
        """Returns the body of the method given the class name and method name"""

    @abstractmethod
    def get_class_info(self, class_name: str, ranking_query_string: str = None) -> str:
        """Returns the class information given the class name"""

    @abstractmethod
    def get_related_snippets(self, search_string: str) -> str:
        """Returns the repocoder code snippets given the search string"""

