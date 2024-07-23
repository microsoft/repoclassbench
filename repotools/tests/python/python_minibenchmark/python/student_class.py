class Student:
    name = 'unknown' # class attribute
    def __init__(self, 
                 a: int
                 ) -> int:
        self.age = 20  # instance attribute

    @classmethod
    def tostring(
        cls
        ,
        a:int, 
        ):
        # '''To string method'''
        print('Student Class Attributes: name=',cls.name)


def initiate_goliath():
    return "goliath_student"

class class_A:
    def __init__(self):
        print("Alternative definition of class A")
        