from datetime import datetime

from django.db.models import Q
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.utils import json
from rest_framework.viewsets import GenericViewSet
import rest_framework.permissions
from app import models
from app.models import Device
from app.utils.json_response import DetailResponse, ErrorResponse


class DeviceSerializer(serializers.ModelSerializer):
    create_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)

    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data["create_time"] = datetime.now()
        return super().to_internal_value(data)

    class Meta:
        model = Device

        fields = "__all__"


class DeviceViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    # 设备列表
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def device_list(self, request):

        max_result = int(request.query_params.get("maxResult", 99999))
        skip_count = int(request.query_params.get("skipCount", 0))
        q_objects = Q()
        instances = models.Device.objects.filter(q_objects)
        serializer = DeviceSerializer(
            instances[skip_count : skip_count + max_result], many=True
        )
        return DetailResponse(data={"total": len(instances), "items": serializer.data})

    # 删除设备
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAdminUser],
    )
    def delete_device_by_id(self, request):
        my_id = request.query_params.get("id")
        if my_id is not None and my_id != "":
            if models.Device.objects.filter(id=my_id).exists():
                instances = models.Device.objects.get(id=my_id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()

    # 添加设备
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAdminUser],
    )
    def add_device(self, request):
        data = json.loads(request.body)
        serializer = DeviceSerializer(data=data)
        if serializer.is_valid():
            name_is_exit = models.Device.objects.filter(
                device_name=serializer.validated_data["device_name"]
            ).exists()
            key_is_exit = models.Device.objects.filter(
                device_key=serializer.validated_data["device_key"]
            ).exists()
            if name_is_exit:
                return JsonResponse(
                    {
                        "code": 200,
                        "succeeded": False,
                        "msg": "已存在同名设备，请更换设备名称!",
                    }
                )
            if key_is_exit:
                return JsonResponse(
                    {
                        "code": 200,
                        "succeeded": False,
                        "msg": "已存在同名key，请更改key名称!",
                    }
                )
            serializer.save()
            return JsonResponse({"code": 200, "succeeded": True})
        else:
            for field, errors in serializer.errors.items():
                for error in errors:
                    print(f"Field '{field}': {error}")
        return JsonResponse({"code": 200, "succeeded": False})

    # 更改设备
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAdminUser],
    )
    def update_device_by_id(self, request):
        data = json.loads(request.body)
        id = data.get("id")
        instance = models.Device.objects.filter(id=id).first()
        if instance is not None:
            device_name = data.get("device_name")
            device_key = data.get("device_key")
            is_disable = data.get("is_disable")
            gpu_num = data.get("gpu_num")
            if device_name is not None:
                existing_device = (
                    models.Device.objects.exclude(id=id)
                    .filter(device_name=device_name)
                    .first()
                )
                if existing_device:
                    return JsonResponse(
                        {
                            "code": 200,
                            "succeeded": False,
                            "msg": "已存在同名设备，请更换设备名称!",
                        }
                    )
                instance.device_name = device_name
            if device_key is not None:
                existing_device = (
                    models.Device.objects.exclude(id=id)
                    .filter(device_key=device_key)
                    .first()
                )
                if existing_device:
                    return JsonResponse(
                        {
                            "code": 200,
                            "succeeded": False,
                            "msg": "已存在同名key，请更改key名称!",
                        }
                    )
                instance.device_key = device_key
            if is_disable is not None:
                instance.is_disable = is_disable
            if gpu_num is not None and int(gpu_num) >= 0:
                instance.gpu_num = gpu_num
            instance.save()
            return JsonResponse({"code": 200, "succeeded": True})
        return JsonResponse({"code": 200, "succeeded": False})

    # gpu数目
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def get_gpu_num_by_id(self, request):

        id = request.query_params.get("id")
        instance = models.Device.objects.filter(id=id).first()
        gpu_num = instance.gpu_num if instance is not None else 0

        return DetailResponse(data={"gpu_num": gpu_num, "device_id": id})
