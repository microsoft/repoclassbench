from abc import ABC, abstractmethod


class BasePrompts(ABC):

    @abstractmethod
    def get_initial_generation_prompt(self, snippets: str):
        pass

    @abstractmethod
    def get_tools_prompt(self, generated_code: str, feedback: str):
        pass

    @abstractmethod
    def get_reflection_prompt(
        self, generated_code: str, feedback: str, tool_outputs: str
    ):
        pass

    @abstractmethod
    def get_improved_generation_prompt(
        self,
        generated_code: str,
        feedback: str,
        tool_outputs: str,
        reflection: str,
    ):
        pass
