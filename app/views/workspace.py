import asyncio
from datetime import datetime

from django.db.models import Q
from django.http import JsonResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.utils import json
from rest_framework.viewsets import GenericViewSet
import rest_framework.permissions
from app import models
from app.models import Workspace, Users
from app.utils.chat import ChatStorage
from app.utils.json_response import DetailResponse, ErrorResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import api_view
from adrf.viewsets import ViewSet

from asgiref.sync import sync_to_async

from app.utils.socket_client import TcpSocket


class WorkspaceSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data["create_time"] = datetime.now()

        return super().to_internal_value(data)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        device = models.Device.objects.filter(
            device_key=instance.model.resource.device_key
        ).first()
        representation["device_name"] = device.device_name if device else None
        representation["model_type"] = instance.model.type if instance.model else None
        return representation

    class Meta:
        model = Workspace

        fields = "__all__"


class WorkspaceViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    # 创建工作区
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def create_workspace(self, request):
        user = JWTAuthentication().authenticate(request)[0]
        data = json.loads(request.body)
        data["creator"] = user.id
        if "all" in data.get("use_gpus"):
            model_id = data.get("model")
            model = models.LargeModel.objects.filter(id=model_id).first()
            gpu_num = [str(i) for i in range(model.resource.gpu_num)]
            data["use_gpus"] = ",".join(gpu_num)
        else:
            data["use_gpus"] = ",".join(list(map(str, data.get("use_gpus", ["0"]))))
        serializer = WorkspaceSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"code": 200, "succeeded": True})
        return JsonResponse({"code": 200, "succeeded": False})

    # 工作区列表
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def get_workspace_list(self, request):

        max_result = int(request.query_params.get("maxResult", 99999))
        skip_count = int(request.query_params.get("skipCount", 0))
        create_time = request.query_params.get("create_time")
        q_objects = Q()

        if create_time is not None and create_time != "":
            start_time = datetime.strptime(create_time, "%Y-%m-%d")
            end_time = datetime.strptime(create_time, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
            q_objects &= Q(create_time__gte=start_time) & Q(create_time__lte=end_time)

        instances = models.Workspace.objects.filter(q_objects)
        serializer = WorkspaceSerializer(
            instances[skip_count : skip_count + max_result], many=True
        )
        return DetailResponse(data={"total": len(instances), "items": serializer.data})

    # 删除工作区
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    def delete_workspace_by_id(self, request):
        id = int(request.query_params.get("id", -1))
        if id is not None and id != "":
            if models.Workspace.objects.filter(id=id).exists():
                instances = models.Workspace.objects.get(id=id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()

    # #发布/回收工作区
    # @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    # def publish_workspace_by_id(self, request):
    #     id = int(request.query_params.get('id', -1))
    #     published=request.query_params.get('published')=='true'
    #     if id is not None and id != '':
    #         if models.Workspace.objects.filter(id=id).exists():
    #             instance = models.Workspace.objects.get(id=id)
    #             instance.published=published
    #             instance.save()
    #             return DetailResponse()
    #     return ErrorResponse()

    # chat
    # @action(methods=["POST"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    # async def chat(self, request):
    #     workspace_id = int(request.query_params.get('workspace_id', -1))
    #     messages=request.query_params.get('messages', None)
    #     published=request.query_params.get('published')=='true'
    #     if workspace_id is not None and workspace_id != '':
    #         if models.Workspace.objects.filter(id=id).exists():
    #             instance = models.Workspace.objects.get(id=id)
    #             model_id=instance.model_id
    #             # await asyncio.sleep(1)
    #             return JsonResponse({"message": "异步视图已执行"})
    #     return JsonResponse({"message": "异步视图已执行"})

    # @action(methods=["POST"],detail=False,)
    # async def chat(self, request):
    #     # 异步处理逻辑
    #     result = await self.async_operation()
    #     return JsonResponse({"message": "异步视图已执行"})

    # async def async_operation(self):
    #     # 异步处理逻辑
    #     return '异步操作结果'


# @api_view(['POST'])
# async def chat(self, request):
#         workspace_id = int(request.query_params.get('workspace_id', -1))
#         messages=request.query_params.get('messages', None)
#         published=request.query_params.get('published')=='true'
#         if workspace_id is not None and workspace_id != '':
#             if models.Workspace.objects.filter(id=id).exists():
#                 instance = models.Workspace.objects.get(id=id)
#                 model_id=instance.model_id
#                 # await asyncio.sleep(1)
#                 return JsonResponse({"message": "异步视图已执行"})
#         return JsonResponse({"message": "异步视图已执行"})


def get_model_by_workspace(workspace_id):
    model = None
    if models.Workspace.objects.filter(id=workspace_id).exists():
        model = models.Workspace.objects.get(id=workspace_id).model
    return model


def get_base_model_by_model(model_id):
    instances = models.LargeModel.objects.select_related("base").get(id=model_id).base
    return instances


def get_workspace_by_id(workspace_id):
    instance = models.Workspace.objects.get(id=workspace_id)
    return instance


class ChatViewSet(ViewSet):

    # 模型问答
    @action(
        methods=["POST"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    async def test_chat(self, request):
        req_json = json.loads(request.body)
        workspace_id = req_json["workspace_id"]
        history = req_json.get("history", [])
        model = await sync_to_async(get_model_by_workspace)(workspace_id)
        model_id = model.id
        message = req_json["messages"]
        uuid = req_json["uuid"]
        type = "txt2img_chat" if model.type == "text_image" else "chat"
        data = {
            "chat_args": {
                "messages": message,
                "history": history,
                "uuid": uuid,
            },
            "workspace_id": f"workspace_{workspace_id}",
            "type": type,
        }
        device_key = await sync_to_async(model.get_device_key_sync)()
        TcpSocket.send_data(data, device_key)
        try:
            response = await ChatStorage.async_get_message(uuid, timeout=60)
            return DetailResponse(data={"response": response})
        except Exception as e:
            print(e)
            return ErrorResponse(msg={"message": "请求超时"})

    @sync_to_async
    def _get_model(self, workspace_id):
        if models.Workspace.objects.filter(id=workspace_id).exists():
            instance = models.Workspace.objects.get(id=workspace_id)
            return instance.model
        return None

    # 加载模型

    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    async def load_chat(self, request):
        workspace_id = request.query_params.get("workspace_id")
        uuid = request.query_params.get("uuid")
        # template=request.query_params.get('template')
        Workspace = await sync_to_async(get_workspace_by_id)(workspace_id)
        model = await sync_to_async(get_model_by_workspace)(workspace_id)
        model_id = model.id
        base_model = await sync_to_async(get_base_model_by_model)(model_id)

        if "baichuan" in base_model.name.lower():
            template = "baichuan2"
        elif "llama" in base_model.name.lower():
            template = "llama2_zh"
        else:
            template = "chatglm2"
        adapter_name_or_path = model.adapter_name_or_path
        # instance=await sync_to_async(get_base_model_by_model)(model_id)
        type = "load_txt2img_chat" if model.type == "text_image" else "load_chat"
        data = {
            "script_args": {
                "uuid": uuid,
                # "model_id":model_id,
                "workspace_id": f"workspace_{workspace_id}",
                "model_name_or_path": base_model.model_path,
                "template": template,
                "finetuning_type": "lora",
            },
            "use_gpus": Workspace.use_gpus,
            "type": type,
        }
        if adapter_name_or_path is not None and adapter_name_or_path != "":
            data["script_args"]["adapter_name_or_path"] = adapter_name_or_path
        device_key = await sync_to_async(model.get_device_key_sync)()
        TcpSocket.send_data(data, device_key)
        try:
            response = await ChatStorage.async_get_message(uuid, timeout=60)
            if response:
                return DetailResponse(msg={"message": "加载成功"})
            else:
                return ErrorResponse(msg={"message": "加载失败"})
        except asyncio.TimeoutError as e:
            return ErrorResponse(msg={"message": "请求超时", "timeout": True})

    # 卸载模型
    @action(
        methods=["GET"],
        detail=False,
        permission_classes=[rest_framework.permissions.IsAuthenticated],
    )
    async def unload_chat(self, request):
        workspace_id = request.query_params.get("workspace_id")
        uuid = request.query_params.get("uuid")
        model = await sync_to_async(get_model_by_workspace)(workspace_id)
        # if models.Workspace.objects.filter(id=workspace_id).exists():
        # model=models.Workspace.objects.get(id=workspace_id).model_id
        # model_id=model.id
        # instances = models.LargeModel.objects.select_related('base').get(id=model_id)
        type = "unload_txt2img_chat" if model.type == "text_image" else "unload_chat"
        data = {
            "script_args": {
                "uuid": uuid,
                # "workspace_id":workspace_id,
            },
            "workspace_id": f"workspace_{workspace_id}",
            "type": type,
        }
        device_key = await sync_to_async(model.get_device_key_sync)()
        TcpSocket.send_data(data, device_key)
        try:
            response = await ChatStorage.async_get_message(uuid, timeout=60)
            if response:
                return DetailResponse(data={"message": "卸载成功"})
            else:
                return ErrorResponse(msg={"message": "卸载失败"})
        except Exception as e:
            print(e)
            return ErrorResponse(msg={"message": "请求超时", "timeout": True})
