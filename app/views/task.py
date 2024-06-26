from datetime import datetime

from django.db.models import Q
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.utils import json
from rest_framework.viewsets import GenericViewSet
import rest_framework.permissions
from app import models
from app.models import Task
from app.utils.command import remove_files
from app.utils.json_response import DetailResponse, ErrorResponse


class TaskSerializer(serializers.ModelSerializer):
    create_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    start_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    end_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", allow_null=True)
    device_name = serializers.SerializerMethodField()
    creator_name = serializers.SerializerMethodField()

    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data["create_time"] = datetime.now()
        data["start_time"] = None
        data["end_time"] = None
        data["model_params"] = {"type": data["type"], "base": data["base"]}
        return super().to_internal_value(data)

    def get_device_name(sefl, obj):
        return obj.device.device_name if obj.device is not None else None

    def get_creator_name(sefl, obj):
        return obj.creator.username if obj.creator is not None else None

    class Meta:
        model = Task

        fields = "__all__"


class TaskViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    # 任务列表
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def task_list(self, request):

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
        instances = models.Task.objects.filter(q_objects)

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
    def delete_task_by_id(self, request):
        my_id = request.query_params.get("id")
        if my_id is not None and my_id != "":
            if models.Task.objects.filter(id=my_id).exists():
                task = models.Task.objects.get(id=my_id)
                related_models = models.LargeModel.objects.filter(finetuning_task=task)
                if len(related_models):
                    return ErrorResponse("存在与此任务关联的模型，无法删除任务")
                # 删除GPU服务器上的训练文件夹
                remove_files(
                    device_key=task.device.device_key, file_paths=[task.output_dir]
                )
                task.delete()
                return DetailResponse()
        return ErrorResponse()

    # 添加任务
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def add_task(self, request):
        data = json.loads(request.body)
        data["device"] = (
            models.Device.objects.filter(id=data.get("resource")).first().id
        )
        data["creator"] = request.user.id
        if "all" in data.get("use_gpus"):
            device = models.Device.objects.filter(id=data.get("resource")).first()
            gpu_num = [
                str(i) for i in range(device.gpu_num if device is not None else 1)
            ]
            data["use_gpus"] = ",".join(gpu_num)
        else:
            data["use_gpus"] = ",".join(list(map(str, data.get("use_gpus", ["0"]))))
        serializer = TaskSerializer(data=data)
        if serializer.is_valid():
            name_is_exit = models.Task.objects.filter(
                task_name=serializer.validated_data["task_name"]
            ).exists()
            if name_is_exit:
                return JsonResponse(
                    {
                        "code": 200,
                        "succeeded": False,
                        "msg": "已存在同名任务，请更换任务名称!",
                    }
                )
            serializer.save()
            return JsonResponse({"code": 200, "succeeded": True})
        else:
            for field, errors in serializer.errors.items():

                for error in errors:

                    print(f"Field '{field}': {error}")
        return JsonResponse({"code": 200, "succeeded": False})

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def query_task_by_id(self, request):
        id = request.query_params.get("id")
        if id is not None and id != "":
            if models.Task.objects.filter(id=id).exists():
                instance = models.Task.objects.get(id=id)
                serializer = TaskSerializer(instance)
                return DetailResponse(data=serializer.data)
        return ErrorResponse()

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def query_loss_by_task_id(self, request):
        id = request.query_params.get("id")
        if id is not None and id != "":
            if models.Task.objects.filter(id=id).exists():
                instance = models.Task.objects.get(id=id)
                return DetailResponse(data=instance.loss_log)
        return ErrorResponse()

    # 获取所有已完成任务的名称
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def filter_task(self, request):
        q_objects = Q()
        status = request.query_params.get("status")
        if status is not None:
            q_objects &= Q(status=status)
        stage = request.query_params.get("stage")
        if stage is not None:
            q_objects &= Q(config__stage=stage)  # 查询json字段
        instances = [
            {
                "task_id": task.id,
                "task_name": task.task_name,
                "finetuning_type": task.get_finetuning_type(),
                "model_type": task.get_model_type(),
            }
            for task in models.Task.objects.filter(q_objects)
        ]
        return DetailResponse(data={"total": len(instances), "items": instances})

    # 获取指定任务的checkpoints
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def query_checkpoints_by_task_id(self, request):
        id = request.query_params.get("id")
        if id is not None and id != "":
            if models.Task.objects.filter(id=id).exists():
                instance = models.Task.objects.get(id=id)
                return DetailResponse(
                    data=(
                        json.loads(instance.checkpoints) if instance.checkpoints else []
                    )
                )
        return ErrorResponse()
