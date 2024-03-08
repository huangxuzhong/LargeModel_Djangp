import ijson 
#流式解析json大文件
def read_specific_element_from_json_array_with_ijson(file_path, index):  

    with open(file_path, 'rb') as file:  
        objects = ijson.items(file, 'item')  # 假设数组元素是顶级元素，且没有嵌套在其它键下  
        length=0
        for i, obj in enumerate(objects):  
            length+=1
            if i == index:  
                element=obj
    return element,length           



# def read_specific_element_from_json_array_with_ijson(file_path,index):
#       with open(file_path, 'r', encoding='utf-8') as file:
#         parser = ijson.parse(file)
#         array_length = 0
        
#         for prefix, event, value in parser:
           
#            if array_length == index:
#                 element= value
#            array_length += 1
#         return element,array_length
