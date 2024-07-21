"""Base class for evaluation"""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import asdict, dataclass

from LLM.llm_api import LLMAPI
from config import Config


@dataclass
class EvaluationData:
    """Evaluation dictionary"""

    passed_tests: int  # Number of passed tests
    failed_tests: int  # Number of failed tests
    error_feedback: str  # Error feedback
    formatted_feedback: str  # Formatted feedback used in RRR
    compile_status: Optional[bool] = None  # Status of compilation
    test_status: Optional[bool] = None  # Status of tests
    evaluation_metadata: Optional[dict] = None  # Evaluation metadata
    compile_status: Optional[bool] = None  # Status of compilation

    dict = asdict


class BaseEvaluator(ABC):
    """Base class for evaluation"""

    @abstractmethod
    def evaluate(self, code: str) -> EvaluationData:
        """Returns the evaluation status"""

    def content_filer(self, language: str, code: str) -> bool:
        """Returns whether the content is safe to run"""
        llm_API = LLMAPI(
            Config.llm_source,
            open_ai_configs=Config.openai_configs,
        )
        response=llm_API.get_response(f"Answer is yes/no only. Is the following code malicious/unsafe to run?CODE:```{language}\n{code}```")
        print(f"{response=}")
        if "yes" in response.lower():
            return False
        return True
