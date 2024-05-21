import os
import ijson


# 流式解析json大文件
def read_specific_element_from_json_array_with_ijson(file_path, index):

    with open(file_path, "rb") as file:
        objects = ijson.items(
            file, "item"
        )  # 假设数组元素是顶级元素，且没有嵌套在其它键下
        length = 0
        for i, obj in enumerate(objects):
            length += 1
            if i == index:
                element = obj
    return element, length


# 将文件夹压缩为zip
def add_dir_to_zip(zipf, dir_path, arc_root=None):

    if arc_root is None:

        arc_root = ""  # 如果没有指定arc_root，则使用空字符串

    else:

        # 确保arc_root以'/'结尾，这样在拼接路径时不会出现问题

        if not arc_root.endswith("/"):

            arc_root += "/"

    for root, dirs, files in os.walk(dir_path):

        # 使用arc_root和相对于dir_path的路径来构建arc_name

        rel_path = os.path.relpath(root, dir_path)

        if rel_path == ".":

            rel_path = ""

        for file in files:

            file_path = os.path.join(root, file)

            # 使用os.path.join确保路径的正确拼接，并确保以'/'分隔

            arc_name = os.path.join(arc_root, rel_path, file)

            zipf.write(file_path, arc_name)


# def read_specific_element_from_json_array_with_ijson(file_path,index):
#       with open(file_path, 'r', encoding='utf-8') as file:
#         parser = ijson.parse(file)
#         array_length = 0

#         for prefix, event, value in parser:

#            if array_length == index:
#                 element= value
#            array_length += 1
#         return element,array_length
