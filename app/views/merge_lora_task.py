from datetime import datetime

from django.db.models import Q
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.utils import json
from rest_framework.viewsets import GenericViewSet
import rest_framework.permissions
from app import models
from app.models import ExportModelTask
from app.utils.json_response import DetailResponse, ErrorResponse


class TaskSerializer(serializers.ModelSerializer):
    create_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    start_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    end_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    tune_task_name = serializers.SerializerMethodField()
    creator_name = serializers.SerializerMethodField()
    new_model_name = serializers.SerializerMethodField()

    def get_tune_task_name(sefl, obj):
        return (
            obj.finetuning_task.task_name if obj.finetuning_task is not None else None
        )

    def get_creator_name(sefl, obj):
        return obj.creator.username if obj.creator is not None else None

    def get_new_model_name(sefl, obj):
        return obj.extra_data.get("model_name") if obj.extra_data is not None else None

    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data["create_time"] = datetime.now()
        data["start_time"] = None
        data["end_time"] = None
        return super().to_internal_value(data)

    class Meta:
        model = ExportModelTask

        fields = "__all__"


class ExportModelTaskViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    # 任务列表
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def merge_task_list(self, request):
        max_result = int(request.query_params.get("maxResult", 99999))
        skip_count = int(request.query_params.get("skipCount", 0))
        status = request.query_params.get("statusType")
        task_name = request.query_params.get("task_name")
        create_time = request.query_params.get("create_time")
        q_objects = Q()

        if status is not None and status != "" and status != "all":
            q_objects &= Q(status=status)
        if task_name is not None and task_name != "":
            q_objects &= Q(task_name__contains=task_name)

        if create_time is not None and create_time != "":
            start_time = datetime.strptime(create_time, "%Y-%m-%d")
            end_time = datetime.strptime(create_time, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
            q_objects &= Q(create_time__gte=start_time) & Q(create_time__lte=end_time)
        instances = models.ExportModelTask.objects.filter(q_objects)

        # 查看sql语句
        print(instances.query)
        serializer = TaskSerializer(
            instances[skip_count : skip_count + max_result], many=True
        )
        return DetailResponse(data={"total": len(instances), "items": serializer.data})

    # 删除任务
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def delete_merge_task_by_id(self, request):
        my_id = request.query_params.get("id")
        if my_id is not None and my_id != "":
            if models.ExportModelTask.objects.filter(id=my_id).exists():
                instances = models.ExportModelTask.objects.get(id=my_id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()
