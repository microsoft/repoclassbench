"""
Enum class for types of Fully Qualified Class Names
"""

from enum import Enum

class FQCNKind(str, Enum):
    CLASS = 'class'
    STRUCT = 'struct'
    RECORD = 'record'
    INTERFACE = 'interface'
    ENUM = 'enum'
    STATIC_CLASS = 'static class'

class FQCN:
    fqcn: str
    fqcn_type = FQCNKind.CLASS

    def __init__(self, fqcn:str, fqcn_type=FQCNKind.CLASS) -> None:
        self.fqcn = fqcn
        self.fqcn_type = fqcn_type