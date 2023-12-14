class MessageStack:  
    def __init__(self,max_size=200):  
        self.items = [] 
        self.max_size=max_size 
  
    def is_empty(self):  
        return len(self.items) == 0  
  
    def push(self, item):
        if(self.size()>=self.max_size):
            self.pop()  
        self.items.append(item)  
  
    def pop(self):  
        if self.is_empty():  
            raise Exception("Stack is empty")  
        return self.items.pop()  
  
    def peek(self):  
        if self.is_empty():  
            raise Exception("Stack is empty")  
        return self.items[-1]  
  
    def size(self):  
        return len(self.items)