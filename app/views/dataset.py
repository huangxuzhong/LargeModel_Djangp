from datetime import datetime
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
from app.utils.json_response import DetailResponse, ErrorResponse
from app.utils.llama_factory_api import start_train
from app.utils.socket_client import TcpScoket

import os
class DatasetSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
            # 在这里对data进行预处理
        data['create_time'] = datetime.now()
        data['resource'] = data['filePath']
        return super().to_internal_value(data)
    
    class Meta:
        model = Dataset

        fields = '__all__'


class DatasetViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    #
 

 
    #数据集列表
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def get_all_dataset(self, request):
   
        max_result = int(request.query_params.get('maxResult', 99999))
        skip_count = int(request.query_params.get('skipCount', 0))
        dataset_type = request.query_params.get('dataset_type')
        dataset_name = request.query_params.get('dataset_name')
        create_time = request.query_params.get('create_time')
        q_objects = Q()
      
        if dataset_type is not None and dataset_type != '':
            q_objects &= Q(type=dataset_type)
        if dataset_name is not None and dataset_name != '':
            q_objects &= Q(dataset_name__contains=dataset_name)
         
        if create_time is not None and create_time != '':
            start_time = datetime.strptime(create_time, "%Y-%m-%d")
            end_time = datetime.strptime(create_time, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q_objects &= Q(create_time__gte=start_time) & Q(create_time__lte=end_time)
            print('start_time', start_time)
            print('end_time', end_time)
        instances = models.Dataset.objects.filter(q_objects)
        # 查看sql语句
        print(instances.query)
        serializer = DatasetSerializer(instances[skip_count:skip_count + max_result], many=True)
        return DetailResponse(data={'total': len(instances), 'items': serializer.data})
   
    #删除数据集
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def delete_dataset_by_id(self, request):
        my_id = request.query_params.get('id')
        if my_id is not None and my_id != '':
            if models.Dataset.objects.filter(id=my_id).exists():
                instances = models.Dataset.objects.get(id=my_id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()

    #添加数据集
    @action(methods=["POST"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def add_dataset(self,request):
        data = json.loads(request.body)
        serializer = DatasetSerializer(data=data)
        if serializer.is_valid():
            name_is_exit = models.Dataset.objects.filter(dataset_name=serializer.validated_data['dataset_name']).exists()
            if  name_is_exit:
                return JsonResponse({"code": 200, "succeeded": False,"msg": "已存在同名数据集，请更换数据集名称!"})
            serializer.save()
            return JsonResponse({"code": 200, "succeeded": True})
        return JsonResponse({"code": 200, "succeeded": False})
        
    

    #接收上传数据集
    @action(methods=["POST"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def upload_dataset(self,request):
        if  request.FILES.get('file'): 
            uploaded_file = request.FILES['file']
            # dataset_name=request.data.get("datasetName")
            # name_is_exit = models.Dataset.objects.filter(dataset_name=dataset_name).exists()
            # if  name_is_exit:
            #     return ErrorResponse(msg="已存在同名数据集，请更换数据集名称!")
            file_path = os.path.join('uploads','datasets', uploaded_file.name)
            # 确保目录存在
            if not os.path.exists(os.path.join('uploads','datasets')):
                os.makedirs(os.path.join('uploads','datasets'))
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)
            return DetailResponse(msg= '文件上传成功', data={'file_path': file_path})
        else:
            return ErrorResponse(msg='文件上传失败')
        
    
     #删除上传的数据集
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def remove_dataset(self,request):
        file_path= request.query_params.get("filePath")
        if  os.path.exists(file_path):
            os.remove(file_path)
            return DetailResponse(msg= '文件删除成功', data={'file_path': file_path})
        else:
            return ErrorResponse(msg='文件删除失败，文件不存在')
        
        

    #下载数据集
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def download_dataset(self,request):
        file_path=  os.path.normpath(request.query_params.get("filePath"))
        if  os.path.isfile(file_path): 
                 response=FileResponse(open(file_path, 'rb'))
                 utf8_encoded_string = quote(os.path.basename(file_path), encoding='utf-8')
                 response['Content-Type'] = 'application/octet-stream'
                 response['Content-Disposition'] = f"attachment;filename*=UTF-8''{utf8_encoded_string}"
                
            # with open(file_path, 'rb') as f:
                 return response
        else:
            return ErrorResponse(msg='文件不存在')
        
    #预览数据集
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def  preview_dataset(self,request):
        dataset_id=request.query_params.get("datasetId")
        data_item_index=int(request.query_params.get("dataItemIndex"))
        dataset=models.Dataset.objects.get(id=dataset_id)
        if  os.path.exists(dataset.resource):
            # 打开并读取JSON文件
            with open(dataset.resource, 'r', encoding='utf-8') as file:
                data = json.load(file)
                data_item=data[data_item_index:data_item_index+1][0]
                return DetailResponse(data={"total_count":len(data),"current_index":data_item_index,"data_item":data_item})
        else:
            return ErrorResponse(msg="文件不存在")
      
        

      