import sys, os
from abc import ABC, abstractmethod
from typing import List
import numpy as np
import parent_complex_class
from parent_complex_class import Complex, random_parent_func_stuff
# # sys.path.append("../../utils_code")
# import utils_code.lsp_helper

class PolarComplex(Complex):
    """A class that represents a complex number in polar form."""
    angle = 1
    checker = 4
    yello = parent_complex_class.Complex(1,
                                        2)
    
    def __init__(self, magnitude, angle):
        """Initializes a complex number in polar form with magnitude and angle."""
        self.magnitude = magnitude
        self.angle = angle
        
        self.random_parent_var = random_parent_func_stuff()
        self.i = 20202
        
        real = magnitude * np.cos(angle)
        imag = magnitude * np.sin(angle)
        super().__init__(real, imag)
        
    def hello(self):
        """Prints 'hello' and sets the yello attribute to 5."""
        print("hello")
        self.yello = 5

    def to_polar(self):
        """Converts the complex number to polar form and returns the magnitude and angle."""
        magnitude = np.sqrt(self.r ** 2 + self.i ** 2)
        angle = np.arctan2(self.i, self.r)
        return magnitude, angle

    def from_polar(self, magnitude, angle) -> None:
        """Converts the complex number from polar form to rectangular form."""
        self.magnitude = magnitude
        self.angle = angle
        self.r = magnitude * np.cos(angle)
        self.i = magnitude * np.sin(angle)

    def __str__(self):
        """Returns the string representation of the complex number in polar form."""
        return f"{self.magnitude} * e^({self.angle}i)"

class ListOperations(ABC):
    """An abstract base class for performing operations on two lists."""
    def __init__(self, list1: List[int], list2: List[int]):
        """Initializes two lists for operations."""
        self.list1 = list1
        self.list2 = list2

    @abstractmethod
    def msr_add(self) -> List[int]:
        """Adds the elements of two lists and returns the result as a list."""
        pass

    @abstractmethod
    def msr_multiply(self) -> List[int]:
        """Multiplies the elements of two lists and returns the result as a list."""
        pass

    def print_length(self) -> None:
        """Prints the length of the two lists."""
        print(f"Length of list1: {len(self.list1)}")
        print(f"Length of list2: {len(self.list2)}")
        
    @property
    def list1(self):
        """Returns the first list."""
        return self._list1
    
    @list1.setter
    def list1(self, value):
        """Sets the value of the first list."""
        if not isinstance(value, List):
            raise TypeError("list1 must be a list")
        self._list1 = value
    
    @property
    def list2(self):
        """Returns the second list."""
        return self._list2
    
    @list2.setter
    def list2(self, value):
        """Sets the value of the second list."""
        if not isinstance(value, List):
            raise TypeError("list2 must be a list")
        self._list2 = value
        
    @property
    def x_property(self):
        """Returns the value 2."""
        return 2
        
        
class IntegerList(ListOperations):
    """A class for performing operations on two lists of integers."""
    def msr_add(self) -> List[int]:
        """Adds the elements of two lists and returns the result as a list."""
        if len(self.list1) == len(self.list2):
            result = np.add(self.list1, self.list2).tolist()
            return result
        else:
            raise ValueError("Lists must be of the same length")

    def msr_multiply(self) -> List[int]:
        """Multiplies the elements of two lists and returns the result as a list."""
        if len(self.list1) == len(self.list2):
            result = np.multiply(self.list1, self.list2).tolist()
            return result
        else:
            raise ValueError("Lists must be of the same length")
        
        
class ComplexList(ListOperations):
    """A class for performing operations on two lists of complex numbers."""
    def msr_add(self):
        """Adds the elements of two lists of complex numbers and returns the result as a list."""
        if len(self.list1) == len(self.list2):
            result = [parent_complex_class.Complex(x.r, x.i) + y for x, y in zip(self.list1, self.list2)]
            return result
        else:
            raise ValueError("Lists must be of the same length")

    def msr_subtract(self):
        """Subtracts the elements of two lists of complex numbers and returns the result as a list."""
        if len(self.list1) == len(self.list2):
            result = [parent_complex_class.Complex(x.r, x.i) - y for x, y in zip(self.list1, self.list2)]
            return result
        else:
            raise ValueError("Lists must be of the same length")

    def msr_multiply(self):
        """Multiplies the elements of two lists of complex numbers and returns the result as a list."""
        if len(self.list1) == len(self.list2):
            result = [parent_complex_class.Complex(x.r, x.i) * y for x, y in zip(self.list1, self.list2)]
            return result
        else:
            raise ValueError("Lists must be of the same length")
        
class MyClass:
    """A class that represents a point in 2D space."""
    def __init__(self, x, y):
        """Initializes the x and y coordinates of the point."""
        self.x = x
        self.y = y

    @classmethod
    def from_tuple(cls, coords):
        """Creates a new instance of the class from a tuple of coordinates."""
        return cls(*coords)

    @classmethod
    def from_dict(cls, coords):
        """Creates a new instance of the class from a dictionary of coordinates."""
        return cls(coords['x'], coords['y'])
    
    @property
    def z(self):
        """Returns the sum of the x and y coordinates."""
        return self.x+self.y
    
    @property
    def t(self):
        """Returns the sum of the x and y coordinates plus 1."""
        return self.x+self.y+1
    
    @t.setter
    def t(self, value):
        """Sets the value of the t attribute to 7."""
        self.t = 7
    
class dummy_class:
    """A dummy class for testing purposes."""
    def __init__(self,a, b, c=3, *args, d, e=5, **kwargs):
        """Initializes the class with various arguments."""
        pass
    
class ClassArgs:
    """A class for testing the use of various types of arguments."""
    def __init__(self, a, b, /, c, d, *args, e, f, **kwargs):
        """Initializes the class with positional, keyword, and variable-length arguments."""
        self.a = a
        self.b = b
        self.c = c
        self.d = d
        self.args = args
        self.e = e
        self.f = f
        self.kwargs = kwargs

    def __repr__(self):
        """Returns the string representation of the class."""
        return f"MyClass(a={self.a}, b={self.b}, c={self.c}, d={self.d}, args={self.args}, e={self.e}, f={self.f}, kwargs={self.kwargs})"

def initiate_pegasus():
    """Returns the string 'pegasus'."""
    return "pegasus"

def initiate_goliath():
    """Returns the string 'goliath'."""
    return "goliath"