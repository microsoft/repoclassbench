from agents.rrr_prompts.base_rrr_prompts import BasePrompts


class PythonPrompts(BasePrompts):

    def __init__(self, nl_description: str, file_path: str) -> None:
        self.nl_description = nl_description
        self.file_path = file_path

    def get_initial_generation_prompt(self, snippets: str):
        return ""

    def get_tools_prompt(self, generated_code: str, feedback: str):
        return ""

    def get_reflection_prompt(
        self, generated_code: str, feedback: str, tool_outputs: str
    ):
        return ""

    def get_improved_generation_prompt(
        self,
        generated_code: str,
        feedback: str,
        tool_outputs: str,
        reflection: str,
    ):
        return ""
