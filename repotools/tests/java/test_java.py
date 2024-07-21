import unittest
from repotools import Tools
from repoclassbench import Dataset
import time

class TestJava(unittest.TestCase):
    """Class to test the Java dataset."""
    def test_get_class_info(self):
        """Test get_class_info"""
        tools = Tools(language="java", class_name=None, repo_root_dir="repotools/tests/java/example_repo/repo1", file_path="src/main/java/io/github/AddComplex2.java")

        assert """For class io.Complex:
Constructor of class io.Complex has signature: 
Complex.Complex(float r, float i)

Objects of the class io.Complex have the following instance members: 
-Complex.setImaginary(float i) : void  (instance variable)
-Complex.getImaginary() : float  (instance variable)
-Complex.getRealPart() : float  (instance variable)
-Complex.setReal(float r) : void  (instance variable)""" in tools.get_class_info("Complex","addition")
    
    def test_get_signature(self):
        """Test get_signature"""
        tools = Tools(language="java", class_name=None, repo_root_dir="repotools/tests/java/example_repo/repo1", file_path="src/main/java/io/github/AddComplex2.java")
        assert "void public Complex.setImaginary(float i)" in tools.get_signature("Complex","setImaginary")
    
    def test_get_method_body(self):
        """Test get_method_body"""
        tools = Tools(language="java", class_name=None, repo_root_dir="repotools/tests/java/example_repo/repo1", file_path="src/main/java/io/github/AddComplex2.java")
        assert '    }\n    public void setImaginary(float i){\n        this.i=i;\n    }' in tools.get_method_body("Complex","setImaginary")
    
    def test_get_imports(self):
        """Test get_imports"""
        tools = Tools(language="java", class_name=None, repo_root_dir="repotools/tests/java/example_repo/repo1", file_path="src/main/java/io/github/AddComplex2.java")        
        print(tools.get_imports("""public class A {
            public static void main(String[] args) {
                Complex c1;
            }
        }"""))
        assert "For Complex you can use 'io.Complex'" in tools.get_imports("""public class A {
            public static void main(String[] args) {
                Complex c1;
            }
        }""")
    
    def test_get_related_snippets(self):
        """Test get_related_snippets"""
        tools = Tools(language="java", class_name=None, repo_root_dir="repotools/tests/java/example_repo/repo1", file_path="src/main/java/io/github/AddComplex2.java")
        assert """public class Complex{
    private float r,i;

    public Complex(float r, float i){
        this.r=r;
        this.i=i;
    }""" in tools.get_related_snippets("Class dealing with Complex numbers")
        
    def test_get_relevant_code(self):
        """Test get_relevant_code"""
        tools = Tools(language="java", class_name=None, repo_root_dir="repotools/tests/java/example_repo/repo1", file_path="src/main/java/io/github/AddComplex2.java")
        assert "For class io.Complex:" in tools.get_relevant_code("Setting imaginary numbers")