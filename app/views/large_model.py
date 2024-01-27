from datetime import datetime

from django.db.models import Q,Prefetch  
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.utils import json
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication
import rest_framework.permissions
from app import models
from app.models import LargeModel
from app.utils.json_response import DetailResponse, ErrorResponse
from app.utils.llama_factory_api import start_train
from app.utils.socket_client import TcpScoket

class LargeModelSerializer(serializers.ModelSerializer):
    # model_name = serializers.CharField(max_length=255)
    create_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
    # base_model_path = serializers.CharField()  # 添加新的字段来包含base的model_path属性
    
    # def get_base_model_path(self, obj):  
    #     return obj.base.model_path  # 返回base对象的model_path属性
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['base_model_path'] = instance.base.model_path
        return representation
    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data['create_time'] = datetime.now()
        data['dataset'] = json.dumps(data['dataset'])
        return super().to_internal_value(data)

    class Meta:
        model = LargeModel
        # fields = ['model_name' ]
        fields = '__all__'


class LargeModelViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    #
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def get_user_info(self, request):
        user = JWTAuthentication().authenticate(request)[0]
        print('userid', user.id)
        # return JsonResponse({"user": user.id})
        return DetailResponse(data={"user": user.username})

    @action(methods=["POST"], detail=False)
    def create_model(self, request):
        data = json.loads(request.body)
        # model_name = data["model_name"]
        # type = data["type"]
        # base = data["base"]
        # dataset = data["dataset"]
        # description = data["description"]
        # resource = data["resource"]
        #
        # large_model = models.LargeModel()
        # large_model.model_name = model_name
        # large_model.type = type
        # large_model.base = base
        # large_model.dataset = dataset
        # large_model.description = description
        # large_model.resource = resource
        # # now = datetime.now()  # 获取当前时间
        # # now_formatted = now.strftime('%Y-%m-%d %H:%M:%S')  # 格式化当前时间
        # # large_model.create_time = now_formatted
        # large_model.save()
        serializer = LargeModelSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"code": 200, "succeeded": True})
        return JsonResponse({"code": 200, "succeeded": False})

    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def get_all_model(self, request):
        # start_train(1)
        max_result = int(request.query_params.get('maxResult', 99999))
        skip_count = int(request.query_params.get('skipCount', 0))
        model_type = request.query_params.get('model_type')
        model_name = request.query_params.get('model_name')
        create_time = request.query_params.get('create_time')
        q_objects = Q()
        # instances = models.LargeModel.objects.all()
        if model_type is not None and model_type != '':
            q_objects &= Q(type=model_type)
        if model_name is not None and model_name != '':
            q_objects &= Q(model_name__contains=model_name)
            # instances = instances.filter(model_name__contains=model_name)
        if create_time is not None and create_time != '':
            start_time = datetime.strptime(create_time, "%Y-%m-%d")
            end_time = datetime.strptime(create_time, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q_objects &= Q(create_time__gte=start_time) & Q(create_time__lte=end_time)
            # instances = instances.filter(create_time__gte=start_time, create_time__lte=end_time)
            print('start_time', start_time)
            print('end_time', end_time)
        instances = models.LargeModel.objects.select_related('base').filter(q_objects)
        # 查看sql语句
        #print(instances.query)
        serializer = LargeModelSerializer(instances[skip_count:skip_count + max_result], many=True)
        return DetailResponse(data={'total': len(instances), 'items': serializer.data})
        # return JsonResponse({"code": 200, "data": "successful", "succeeded": True})

    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def delete_model_by_id(self, request):
        my_id = request.query_params.get('id')
        if my_id is not None and my_id != '':
            if models.LargeModel.objects.filter(id=my_id).exists():
                instances = models.LargeModel.objects.get(id=my_id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()

    @action(methods=["POST"], detail=False)
    def update_extra_info(self, request):
        data = json.loads(request.body)
        my_id = data["id"]
        if my_id is None or my_id == '':
            return ErrorResponse()
        if not models.LargeModel.objects.filter(id=my_id).exists():
            return ErrorResponse()
        instance = models.LargeModel.objects.get(id=my_id)
        instance.introduction = data["introduction"]
        instance.user_manual = data["user_manual"]
        instance.service_name = data["service_name"]
        instance.interface_address = data["interface_address"]
        instance.has_configured_extra_info = True
        instance.save()
        return DetailResponse()
    
    @action(methods=["POST"], detail=False)
    def control_train(self, request):
          data = json.loads(request.body)
          task_id=data.get("taskId")
          task=models.Task.objects.get(id=task_id)
          if data.get("type")=="start_train":
            dataset=data.get("args").get("dataset")
            instances =models.Dataset.objects.filter(dataset_name__in=dataset)
            dataset_file=[]
            dataset=[]
            for instance in instances:
                dataset_file.append(instance.resource)
                dataset.append(instance.dataset_name)
            data["args"]["dataset"]=dataset
            data["args"]["dataset_file"]=dataset_file
            TcpScoket.send_data(json.dumps(data),task.resource)
            return DetailResponse(data={'status': '正在开始训练'})
          elif data.get("type")=="stop_train":
            TcpScoket.send_data(json.dumps(data),task.resource)
            return DetailResponse(data={'status': '正在停止训练'})
      
      
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def get_create_model_args(self, request):
        base_models=models.BaseModel.objects.all()
        base_json=[]
        for base_model in base_models:
            base_json.append({"id":base_model.id,"label":base_model.name,"model_path":base_model.model_path})
        datasets=models.Dataset.objects.all()
        dataset_json=[]
        for dataset in datasets:
            dataset_json.append({"id":dataset.id,"label":dataset.dataset_name,"resource":dataset.resource})
        
        # 使用列表推导式  
        device_list = [{'id': device.device_key, 'label': device.device_name} for device in models.Device.objects.all()]  
        args={
            "base":base_json,
            "type": [{ "id": 'text_chat', "label": '文本对话' }],
            "resource":device_list,
            # "resource": [{ "id": '4090', "label": '4090服务器'},{ "id": 'v100', "label": 'V100服务器', },{ "id": 'l40', "label": 'L40*2'}],
            "dataset": dataset_json,
        }
        return DetailResponse(data={"args":args})
    
    
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def query_model_by_id(self, request):
        id = request.query_params.get('id')
        if id is not None and id != '':
            if models.LargeModel.objects.filter(id=id).exists():
                instance = models.LargeModel.objects.get(id=id)
                serializer = LargeModelSerializer(instance)
                return DetailResponse(data=serializer.data)
        return ErrorResponse()
    
      