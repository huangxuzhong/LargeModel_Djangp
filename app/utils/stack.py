import queue


class MessageQueue:  
    def __init__(self,max_size=200):  
        self.items = queue.Queue(maxsize=max_size)  
        self.max_size=max_size 
  
    def is_empty(self):  
        return  self.items.empty()  
  
    def push(self, item):
        if(self.size()>=self.max_size):
            self.pop()  
        self.items.put(item)  
  
    def pop(self):  
        if self.is_empty():  
            raise Exception("MessageQueue is empty")  
        return self.items.get()  
  
    def size(self):  
        return self.items.qsize()