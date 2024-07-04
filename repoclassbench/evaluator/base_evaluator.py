"""Base class for evaluation"""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


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


class BaseEvaluator(ABC):
    """Base class for evaluation"""

    @abstractmethod
    def evaluate(self, code: str) -> EvaluationData:
        """Returns the evaluation status"""
