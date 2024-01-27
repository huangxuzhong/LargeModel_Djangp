from datetime import datetime

from django.db.models import Q
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.utils import json
from rest_framework.viewsets import GenericViewSet
import rest_framework.permissions
from app import models
from app.models import  Device
from app.utils.json_response import DetailResponse, ErrorResponse


class DeviceSerializer(serializers.ModelSerializer):
    create_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S',allow_null=True)
  
    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data['create_time'] = datetime.now()
        return super().to_internal_value(data)
    
    class Meta:
        model = Device

        fields = '__all__'


class DeviceViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]
 
    #设备列表
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def device_list(self, request):
   
        max_result = int(request.query_params.get('maxResult', 99999))
        skip_count = int(request.query_params.get('skipCount', 0))
        q_objects = Q()
        instances = models.Device.objects.filter(q_objects)
        serializer = DeviceSerializer(instances[skip_count:skip_count + max_result], many=True)
        return DetailResponse(data={'total': len(instances), 'items': serializer.data})
   
    #删除设备
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def delete_device_by_id(self, request):
        my_id = request.query_params.get('id')
        if my_id is not None and my_id != '':
            if models.Device.objects.filter(id=my_id).exists():
                instances = models.Device.objects.get(id=my_id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()

    #添加设备
    @action(methods=["POST"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def add_task(self,request):
        data = json.loads(request.body)
        serializer = DeviceSerializer(data=data)
        if serializer.is_valid():
            name_is_exit = models.Device.objects.filter(device_name=serializer.validated_data['device_name']).exists()
            if  name_is_exit:
                return JsonResponse({"code": 200, "succeeded": False,"msg": "已存在同名设备，请更换设备名称!"})
            serializer.save()
            return JsonResponse({"code": 200, "succeeded": True})
        else:
            for field, errors in serializer.errors.items():  
               for error in errors:  
                  print(f"Field '{field}': {error}")
        return JsonResponse({"code": 200, "succeeded": False})
        
    

  
        
        

 
        

      