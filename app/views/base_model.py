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
from app.models import BaseModel
from app.utils.json_response import DetailResponse, ErrorResponse


import os


class BaseModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = BaseModel

        fields = "__all__"


class BaseModelViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    # 基座模型列表
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def get_base_model_list(self, request):

        max_result = int(request.query_params.get("maxResult", 99999))
        skip_count = int(request.query_params.get("skipCount", 0))

        base_model_name = request.query_params.get("base_model_name")
        base_model_type = request.query_params.get("model_type")
        if base_model_type is not None and base_model_type != "":
            base_model_type = base_model_type.replace("base_", "")
        q_objects = Q()

        if base_model_name is not None and base_model_name != "":
            q_objects &= Q(name__contains=base_model_name)
        if base_model_type is not None and base_model_type != "":
            q_objects &= Q(model_type=base_model_type)

        instances = models.BaseModel.objects.filter(q_objects)
        print(instances.query)
        serializer = BaseModelSerializer(
            instances[skip_count : skip_count + max_result], many=True
        )
        return DetailResponse(data={"total": len(instances), "items": serializer.data})

    # 删除基座模型
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAdminUser],
    )
    def delete_base_model_by_id(self, request):
        id = request.query_params.get("id")
        if id is not None and id != "":
            if models.BaseModel.objects.filter(id=id).exists():
                instances = models.BaseModel.objects.get(id=id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()

    # 创建基座模型
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAdminUser],
    )
    def create_base_model(self, request):
        data = json.loads(request.body)
        serializer = BaseModelSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"code": 200, "succeeded": True})
        return JsonResponse({"code": 200, "succeeded": False})

    # 更改基座模型
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAdminUser],
    )
    def update_base_model_by_id(self, request):
        data = json.loads(request.body)
        id = data.get("id")
        instance = models.BaseModel.objects.filter(id=id).first()
        if instance is not None:
            name = data.get("name")
            model_path = data.get("model_path")
            if name is not None:
                instance.name = name
            if model_path is not None:
                instance.model_path = model_path
            instance.save()
            return JsonResponse({"code": 200, "succeeded": True})
        return JsonResponse({"code": 200, "succeeded": False})
