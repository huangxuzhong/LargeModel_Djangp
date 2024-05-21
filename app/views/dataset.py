import base64
from datetime import datetime
import io
import shutil
import stat
from urllib.parse import quote, urlencode

from django.db.models import Q
from django.http import FileResponse, JsonResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.utils import json
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication
import rest_framework.permissions
from app import models
from app.models import Dataset
from app.utils.file import (
    add_dir_to_zip,
    read_specific_element_from_json_array_with_ijson,
)
from app.utils.json_response import DetailResponse, ErrorResponse, SuccessResponse


import os
import zipfile
from datasets import load_dataset, load_from_disk


class DatasetSerializer(serializers.ModelSerializer):
    create_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data["create_time"] = datetime.now()
        data["resource"] = data["filePath"]
        return super().to_internal_value(data)

    class Meta:
        model = Dataset

        fields = "__all__"


class DatasetViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    #

    # 数据集列表
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def get_all_dataset(self, request):

        max_result = int(request.query_params.get("maxResult", 99999))
        skip_count = int(request.query_params.get("skipCount", 0))
        dataset_type = request.query_params.get("dataset_type")
        dataset_name = request.query_params.get("dataset_name")
        create_time = request.query_params.get("create_time")
        q_objects = Q()

        if dataset_type is not None and dataset_type != "":
            q_objects &= Q(type=dataset_type)
        if dataset_name is not None and dataset_name != "":
            q_objects &= Q(dataset_name__contains=dataset_name)

        if create_time is not None and create_time != "":
            start_time = datetime.strptime(create_time, "%Y-%m-%d")
            end_time = datetime.strptime(create_time, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
            q_objects &= Q(create_time__gte=start_time) & Q(create_time__lte=end_time)
            print("start_time", start_time)
            print("end_time", end_time)
        instances = models.Dataset.objects.filter(q_objects)
        # 查看sql语句
        print(instances.query)
        serializer = DatasetSerializer(
            instances[skip_count : skip_count + max_result], many=True
        )
        return DetailResponse(data={"total": len(instances), "items": serializer.data})

    # 删除数据集
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def delete_dataset_by_id(self, request):
        my_id = request.query_params.get("id")
        if my_id is not None and my_id != "":
            if models.Dataset.objects.filter(id=my_id).exists():
                instances = models.Dataset.objects.get(id=my_id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()

    # 添加数据集
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def add_dataset(self, request):
        data = json.loads(request.body)
        serializer = DatasetSerializer(data=data)
        if serializer.is_valid():
            name_is_exit = models.Dataset.objects.filter(
                dataset_name=serializer.validated_data["dataset_name"]
            ).exists()
            if name_is_exit:
                return JsonResponse(
                    {
                        "code": 200,
                        "succeeded": False,
                        "msg": "已存在同名数据集，请更换数据集名称!",
                    }
                )
            serializer.save()
            return JsonResponse({"code": 200, "succeeded": True})
        return JsonResponse({"code": 200, "succeeded": False})

    # 接收上传数据集
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def upload_dataset(self, request):
        if request.FILES.get("file"):
            uploaded_file = request.FILES["file"]
            # dataset_name=request.data.get("datasetName")
            # name_is_exit = models.Dataset.objects.filter(dataset_name=dataset_name).exists()
            # if  name_is_exit:
            #     return ErrorResponse(msg="已存在同名数据集，请更换数据集名称!")
            file_path = os.path.join("uploads", "datasets", uploaded_file.name)
            # 确保目录存在
            if not os.path.exists(os.path.join("uploads", "datasets")):
                os.makedirs(os.path.join("uploads", "datasets"))
            with open(file_path, "wb+") as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            # 解压ZIP文件
            if uploaded_file.name.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(file_path, "r") as zip_ref:
                        zip_ref.extractall(os.path.join("uploads", "datasets"))
                        file_path = file_path.rstrip(".zip")
                except zipfile.BadZipFile:
                    return ErrorResponse("上传的文件不是一个有效的ZIP文件。")
                except Exception as e:
                    return ErrorResponse(f"解压过程中发生错误: {e}")
            return DetailResponse(
                msg="文件上传成功", data={"file_path": file_path.replace("\\", "/")}
            )
        else:
            return ErrorResponse(msg="文件上传失败")

    # 删除上传的数据集
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def remove_dataset(self, request):
        file_path = request.query_params.get("filePath")
        if os.path.exists(file_path):
            os.remove(file_path)
            return DetailResponse(msg="文件删除成功", data={"file_path": file_path})
        else:
            return ErrorResponse(msg="文件删除失败，文件不存在")

    # 下载数据集
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.AllowAny],
    )
    def download_dataset(self, request):
        file_path = os.path.normpath(request.query_params.get("filePath"))
        if os.path.isfile(file_path):
            response = FileResponse(open(file_path, "rb"))
            utf8_encoded_string = quote(os.path.basename(file_path), encoding="utf-8")
            response["Content-Type"] = "application/octet-stream"
            response["Content-Disposition"] = (
                f"attachment;filename*=UTF-8''{utf8_encoded_string}"
            )

            return response
        elif os.path.isdir(file_path):
            # 如果是文件夹，则压缩文件夹并返回压缩文件
            zip_filename = os.path.basename(file_path) + ".zip"
            zip_dir_path = os.path.join("uploads", "datasets", "zip")
            zip_file_path = os.path.join(zip_dir_path, zip_filename)
            if not os.path.isfile(zip_file_path):
                if not os.path.isdir(zip_dir_path):
                    os.mkdir(zip_dir_path)
                # 创建一个ZipFile对象来写入压缩文件
                with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    add_dir_to_zip(zipf, file_path)

            response = FileResponse(open(zip_file_path, "rb"))
            utf8_encoded_string = quote(
                os.path.basename(zip_file_path), encoding="utf-8"
            )
            response["Content-Type"] = "application/octet-stream"
            response["Content-Disposition"] = (
                f"attachment;filename*=UTF-8''{utf8_encoded_string}"
            )

            # 清理临时压缩文件（可选，取决于你是否需要保留它）
            # os.remove(zip_file_path)

            return response
        else:
            return ErrorResponse(msg="文件不存在")

    # 预览数据集
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def preview_dataset(self, request):
        dataset_id = request.query_params.get("datasetId")
        data_item_index = int(request.query_params.get("dataItemIndex"))
        dataset = models.Dataset.objects.get(id=dataset_id)
        if os.path.exists(dataset.resource):
            element, len = read_specific_element_from_json_array_with_ijson(
                dataset.resource, data_item_index
            )

            return DetailResponse(
                data={
                    "total_count": len,
                    "current_index": data_item_index,
                    "data_item": element,
                    "dataset_id": dataset_id,
                    "dataset_name": dataset.dataset_name,
                }
            )

            # # 打开并读取JSON文件
            # with open(dataset.resource, 'r', encoding='utf-8') as file:

            #     data = json.load(file)
            #     data_item=data[data_item_index:data_item_index+1][0]
            #     return DetailResponse(data={"total_count":len(data),"current_index":data_item_index,"data_item":data_item,
            #                                 "dataset_id":dataset_id,"dataset_name":dataset.dataset_name})
        else:
            return ErrorResponse(msg="文件不存在")

    # 预览图片数据集
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def preview_images(self, request):
        dataset_id = request.query_params.get("datasetId")
        max_result = int(request.query_params.get("maxResult", 99999))
        skip_count = int(request.query_params.get("skipCount", 0))

        dataset = models.Dataset.objects.get(id=dataset_id)
        dir = dataset.resource.rstrip(".zip")
        # dir=os.path.join('uploads','datasets',dataset.resource.rstrip(".zip"))
        if os.path.exists(dir):
            try:
                data = load_dataset(dir, split="train")
            except ValueError:
                data = load_from_disk(dir)
            items = []
            for i in range(skip_count, min(max_result + skip_count, len(data))):
                image = data[i]["image"]
                buffered = io.BytesIO()
                image.save(buffered, format="JPEG")  # 或者使用其他格式，如PNG
                img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
                images_base64 = (
                    "data:image/jpeg;base64," + img_str
                )  # 添加MIME类型和Base64前缀
                text = data[i]["text"]
                items.append({"image": images_base64, "text": text})
            return DetailResponse(
                data={
                    "total": len(data),
                    "items": items,
                    "dataset_id": dataset_id,
                    "dataset_name": dataset.dataset_name,
                }
            )
        else:
            return ErrorResponse(msg="文件不存在")

    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def edit_images(self, request):
        data = json.loads(request.body)
        dataset_id = data.get("datasetId")
        index = data.get("index")
        new_text = data.get("newText", "")
        dataset = models.Dataset.objects.get(id=dataset_id)
        dir = dataset.resource.rstrip(".zip")

        if os.path.exists(dir):
            try:
                data = load_dataset(dir, split="train")
            except ValueError:
                data = load_from_disk(dir)

            def ff(data, i):
                if i == index:
                    data["text"] = new_text
                return data

            if index < len(data):
                # 修改数据集
                data = data.map(ff, with_indices=True)

                def remove_readonly(
                    func, path, _
                ):  # 错误回调函数，改变只读属性位，重新删除
                    "Clear the readonly bit and reattempt the removal"
                    os.chmod(path, stat.S_IWRITE)
                    func(path)

                # 删除元素数据集
                shutil.rmtree(dir, onerror=remove_readonly)
                zip_filename = os.path.basename(dataset.resource) + ".zip"
                zip_file_path = os.path.join("uploads", "datasets", "zip", zip_filename)
                if os.path.isfile(zip_file_path):
                    os.unlink(file_path)
                # 保存新数据集
                file_path = os.path.join(
                    "uploads",
                    "datasets",
                    f"{dataset.dataset_name}_{ datetime.now().timestamp()}",
                )
                data.save_to_disk(file_path)
                dataset.resource = file_path
                dataset.save()
                return SuccessResponse()
            else:
                return ErrorResponse(msg="下标超出索引范围")
        else:
            return ErrorResponse(msg="文件不存在")
