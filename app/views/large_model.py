from datetime import datetime

from django.db.models import Q, Prefetch
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

from app.utils.rabbitmq_comm import Comm
from app.utils.socket_client import TcpSocket


class LargeModelSerializer(serializers.ModelSerializer):
    # model_name = serializers.CharField(max_length=255)
    create_time = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")
    # base_model_path = serializers.CharField()  # 添加新的字段来包含base的model_path属性

    # def get_base_model_path(self, obj):
    #     return obj.base.model_path  # 返回base对象的model_path属性
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["base_model_path"] = (
            instance.base.model_path
            if instance.model_path is None
            else instance.model_path
        )
        representation["task_name"] = (
            instance.finetuning_task.task_name
            if instance.finetuning_task is not None
            else None
        )
        return representation

    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data["create_time"] = datetime.now()
        data["dataset"] = []
        return super().to_internal_value(data)

    class Meta:
        model = LargeModel
        # fields = ['model_name' ]
        fields = "__all__"


class LargeModelViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    #
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def get_user_info(self, request):
        user = JWTAuthentication().authenticate(request)[0]
        print("userid", user.id)
        # return JsonResponse({"user": user.id})
        return DetailResponse(data={"user": user.username})

    @action(methods=["POST"], detail=False)
    def create_model(self, request):
        data = json.loads(request.body)

        try:
            if (
                models.LargeModel.objects.filter(model_name=data["model_name"]).first()
                is not None
            ):
                return ErrorResponse(msg="模型名已被使用，请更换名称")
            large_model = LargeModel()
            large_model.model_name = data["model_name"]
            large_model.description = data["description"]
            task_id = data["task"]
            task = models.Task.objects.filter(id=task_id).first()
            large_model.finetuning_task = task
            large_model.type = task.model_params.get("type")
            large_model.resource = task.device
            if data.get("merge_adapter") == True:
                export_dir = f"outputs/{data['model_name']}"
                export_model_task = models.ExportModelTask(
                    task_name=f"{data['model_name']}--合并",
                    start_time=datetime.now(),
                    adapter_name_or_path=data["checkpoint"],
                    model_name_or_path=task.config.get("model_name_or_path"),
                    template=task.config.get("template"),
                    export_dir=export_dir,
                    finetuning_task=task,
                    creator=request.user,
                    extra_data={
                        "model_name": data["model_name"],
                        "description": data["description"],
                    },
                )
                export_model_task.save()
                flag = Comm.send_data(
                    {
                        "type": "export_model",
                        "taskId": f"export_{export_model_task.id}",
                        "args": {
                            "adapter_name_or_path": export_model_task.adapter_name_or_path,
                            "model_name_or_path": export_model_task.model_name_or_path,
                            "template": export_model_task.template,
                            "export_dir": export_model_task.export_dir,
                        },
                    },
                    task.device.device_key,
                )
                if flag:
                    return DetailResponse()
                else:
                    return ErrorResponse(msg="服务器不在线")
            else:
                if (
                    task.get_finetuning_type() == "lora"
                    or task.get_finetuning_type() == "dreambooth"
                ):
                    adapter_name_or_path = data["checkpoint"]
                    pre_adapter_name_or_path = task.get_adapter_name_or_path()
                    if (
                        pre_adapter_name_or_path is not None
                        and pre_adapter_name_or_path.strip() != ""
                    ):
                        adapter_name_or_path = (
                            pre_adapter_name_or_path + "," + adapter_name_or_path
                        )
                    large_model.adapter_name_or_path = adapter_name_or_path
                    large_model.base_id = task.model_params.get("base")
                else:
                    large_model.model_path = data["checkpoint"]
                    large_model.is_partial = False
                large_model.save()
                return JsonResponse({"code": 200, "succeeded": True})
        except Exception as e:
            return ErrorResponse(msg=str(e))

        # serializer = LargeModelSerializer(data=data)
        # if serializer.is_valid():
        #     serializer.save()
        #     return JsonResponse({"code": 200, "succeeded": True})
        # return JsonResponse({"code": 200, "succeeded": False})

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def get_all_model(self, request):
        # start_train(1)
        max_result = int(request.query_params.get("maxResult", 99999))
        skip_count = int(request.query_params.get("skipCount", 0))
        model_type = request.query_params.get("model_type")
        model_name = request.query_params.get("model_name")
        create_time = request.query_params.get("create_time")
        q_objects = Q()
        # instances = models.LargeModel.objects.all()
        if model_type is not None and model_type != "":
            q_objects &= Q(type=model_type)
        if model_name is not None and model_name != "":
            q_objects &= Q(model_name__contains=model_name)
            # instances = instances.filter(model_name__contains=model_name)
        if create_time is not None and create_time != "":
            start_time = datetime.strptime(create_time, "%Y-%m-%d")
            end_time = datetime.strptime(create_time, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
            q_objects &= Q(create_time__gte=start_time) & Q(create_time__lte=end_time)
            # instances = instances.filter(create_time__gte=start_time, create_time__lte=end_time)
            print("start_time", start_time)
            print("end_time", end_time)
        instances = models.LargeModel.objects.select_related("base").filter(q_objects)
        # 查看sql语句
        # print(instances.query)
        serializer = LargeModelSerializer(
            instances[skip_count : skip_count + max_result], many=True
        )
        return DetailResponse(data={"total": len(instances), "items": serializer.data})
        # return JsonResponse({"code": 200, "data": "successful", "succeeded": True})

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def delete_model_by_id(self, request):
        my_id = request.query_params.get("id")
        if my_id is not None and my_id != "":
            if models.LargeModel.objects.filter(id=my_id).exists():
                instances = models.LargeModel.objects.get(id=my_id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()

    @action(methods=["POST"], detail=False)
    def update_extra_info(self, request):
        data = json.loads(request.body)
        my_id = data["id"]
        if my_id is None or my_id == "":
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
        task_id = data.get("taskId")
        data["taskId"] = f"model_{task_id}"
        task = models.Task.objects.get(id=task_id)
        if (
            data.get("type") == "start_train"
            or data.get("type") == "start_pixart_train"
        ):
            dataset = data.get("args").get("dataset", [])
            instances = models.Dataset.objects.filter(dataset_name__in=dataset)
            dataset_file = []
            is_rank_dataset = []
            prompt_column_names = []
            dataset = []
            for instance in instances:
                dataset_file.append(instance.resource)
                is_rank_dataset.append(instance.is_rank_dataset)
                dataset.append(instance.dataset_name)
                prompt_column_names.append(
                    "text" if instance.for_stage == "pt" else None
                )
            data["use_gpus"] = task.use_gpus
            data["args"]["dataset"] = dataset
            data["args"]["dataset_file"] = dataset_file
            data["args"]["is_rank_dataset"] = is_rank_dataset
            data["args"]["prompt_column_name"] = prompt_column_names
            flag = Comm.send_data(data, task.device.device_key)
            if not flag:
                return ErrorResponse("启动失败，服务器当前不在线！")
            return DetailResponse(data={"status": "正在开始训练"})
        elif data.get("type") == "stop_train":
            Comm.send_data(data, task.device.device_key)
            return DetailResponse(data={"status": "正在停止训练"})

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def get_create_model_args(self, request):
        # base_models=models.BaseModel.objects.all()
        # base_json=[]
        # for base_model in base_models:
        #     base_json.append({"id":base_model.id,"label":base_model.name,"model_path":base_model.model_path,
        #                       "model_type":base_model.model_type})
        # datasets=models.Dataset.objects.all()
        # dataset_json=[]
        # for dataset in datasets:
        #     dataset_json.append({"id":dataset.id,"label":dataset.dataset_name,"resource":dataset.resource})

        # 使用列表推导式
        device_list = [
            {"id": device.id, "label": device.device_name}
            for device in models.Device.objects.all()
        ]
        args = {
            # "base":base_json,
            "type": [
                {"id": "text_chat", "label": "文本对话"},
                {"id": "text_image", "label": "图像生成"},
            ],
            "resource": device_list,
            # "dataset": dataset_json,
        }
        return DetailResponse(data={"args": args})

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def query_model_by_id(self, request):
        id = request.query_params.get("id")
        if id is not None and id != "":
            if models.LargeModel.objects.filter(id=id).exists():
                instance = models.LargeModel.objects.get(id=id)
                serializer = LargeModelSerializer(instance)
                return DetailResponse(data=serializer.data)
        return ErrorResponse()

    @action(methods=["POST"], detail=False)
    def upload_model_to_hf(self, request):
        data = json.loads(request.body)
        model_id = data.get("model_id")
        model = models.LargeModel.objects.get(id=model_id)
        model_dir = (
            model.model_path
            if model.model_path is not None
            else model.adapter_name_or_path
        )
        hub_token = data.get("hf_token")
        private = data.get("is_private", False)
        repo_name = data.get("repo_name")
        upload_model_task = models.UploadModelTask(
            task_name=f"{model.model_name}--上传",
            start_time=datetime.now(),
            model=model,
            creator=request.user,
            repo_name=repo_name,
        )
        upload_model_task.save()
        flag = Comm.send_data(
            {
                "type": "upload_model_to_hf",
                "taskId": f"upload_{upload_model_task.id}",
                "args": {
                    "repo_id": repo_name,
                    "model_dir": model_dir,
                    "hub_token": hub_token,
                    "private": private,
                },
            },
            model.resource.device_key,
        )
        if not flag:
            return ErrorResponse("上传模型失败，服务器当前不在线！")
        return DetailResponse()

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.AllowAny],
    )
    def test_command(self, request):
        Comm.send_data(
            {
                "type": "get_checkpoints",
                "args": {
                    "output_path": "saves/Baichuan2-13B-Chat/lora/2024-03-11-16-52-10"
                },
            },
            "l40",
        )
        return ErrorResponse()
