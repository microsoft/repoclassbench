
class PropertyClass:
    def __init__(self):
        self.a = 1
    
    @property
    def b(self):
        return self.a

#FIXME: Handle this test case later
class Person:
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

class Employee(Person):
    @Person.name.getter
    def name(self):
        return f"Employee: {self._name}"