
class Complex:
    #NOTE: class variable shared by all instances of the class
    count = 0 # class variable to keep track of the number of Complex instances
    
    def __init__(self, r: int, i, checking: str="checking_str", **kwargs):
        """Initializes a complex number with real and imaginary parts."""
        self.r = r
        self.i = i
        Complex.count += 1
    
    def hello(self):
        print("hello")

    def complex_msr_getReal(self):
        """Returns the real part of the complex number."""
        return self.r

    def complex_msr_getImaginary(self):
        """Returns the imaginary part of the complex number."""
        return self.i

    def complex_msr_setReal(self, r):
        """Sets the real part of the complex number."""
        self.r = r

    def complex_msr_setImaginary(self, i):
        """Sets the imaginary part of the complex number."""
        self.i = i

    def complex_msr_add(self, other):
        """Adds two complex numbers and returns the result."""
        real = self.r + other.r
        imag = self.i + other.i
        return Complex(real, imag)

    def complex_msr_subtract(self, other):
        """Subtracts two complex numbers and returns the result."""
        real = self.r - other.r
        imag = self.i - other.i
        return Complex(real, imag)

    def complex_msr_multiply(self, other):
        """Multiplies two complex numbers and returns the result."""
        self.random_setter = 1
        real = self.r * other.r - self.i * other.i
        imag = self.r * other.i + self.i * other.r
        return Complex(real, imag)
    
    @classmethod
    def get_count(cls):
        """Returns the number of Complex instances."""
        return cls.count
    
    @staticmethod
    def is_complex(num, 
                   random_num = 3, 
                   **kwargs) -> bool:
        """Checks if a given number is a complex number."""
        return isinstance(num, Complex)
    
    def __str__(self):
        """Returns the string representation of the complex number."""
        return f"{self.r} + {self.i}i"
    
    def __add__(self, other):
        """Overloads the + operator for complex numbers."""
        return self.complex_msr_add(other)
    
    def __sub__(self, other):
        """Overloads the - operator for complex numbers."""
        return self.complex_msr_subtract(other)
    
    def __mul__(self, other):
        """Overloads the * operator for complex numbers."""
        return self.complex_msr_multiply(other)
    
def random_parent_func_stuff():
    return 1