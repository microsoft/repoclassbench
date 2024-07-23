class class_A:
    def __init__(self):
        print("init of class A called")
        self.a1 = 1
        self.a2 = 2
        
    def cal(self):
        self.a3 =  3
        
    def foo(self):
        self.a4 = 4

class B(class_A):
    b4 = 4
    # def __init__(self):
    #     self.b1 = 2
    #     self.b2 = 10
        
    def cal(self):
        self.b3 =  5

class C(B):
    c4 = 4

    def cal(self):
        self.c3 =  5
        
print(B.b4)

b_obj = B()
# print("b1 is: ", b_obj.b1)
# print("b2 is: ", b_obj.b2)
# print("b3 is: ", b_obj.b3)
print("b4 is: ", b_obj.b4)
print("a1 is: ", b_obj.a1)
print("a2 is: ", b_obj.a2)
