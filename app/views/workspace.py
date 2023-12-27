import asyncio
from datetime import datetime

from django.db.models import Q
from django.http import  JsonResponse
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.utils import json
from rest_framework.viewsets import GenericViewSet
import rest_framework.permissions
from app import models
from app.models import Workspace,Users
from app.utils.json_response import DetailResponse, ErrorResponse
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.decorators import api_view  
from adrf.viewsets import ViewSet
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

class WorkspaceSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data['create_time'] = datetime.now()
      
        return super().to_internal_value(data)
    
    class Meta:
        model = Workspace

        fields = '__all__'


class WorkspaceViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    #创建工作区
    @action(methods=["POST"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def create_workspace(self, request):
        user = JWTAuthentication().authenticate(request)[0]
        data = json.loads(request.body)
        data["creator"]=user.id
        serializer = WorkspaceSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"code": 200, "succeeded": True})
        return JsonResponse({"code": 200, "succeeded": False})

    
    
    #工作区列表
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def get_workspace_list(self, request):
   
        max_result = int(request.query_params.get('maxResult', 99999))
        skip_count = int(request.query_params.get('skipCount', 0))
        create_time = request.query_params.get('create_time')
        q_objects = Q()
     
        if create_time is not None and create_time != '':
            start_time = datetime.strptime(create_time, "%Y-%m-%d")
            end_time = datetime.strptime(create_time, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            q_objects &= Q(create_time__gte=start_time) & Q(create_time__lte=end_time)
          
        instances = models.Workspace.objects.filter(q_objects)
        serializer = WorkspaceSerializer(instances[skip_count:skip_count + max_result], many=True)
        return DetailResponse(data={'total': len(instances), 'items': serializer.data})
   
   
      
    #删除工作区
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def delete_workspace_by_id(self, request):  
        id = int(request.query_params.get('id', -1))
        if id is not None and id != '':
            if models.Workspace.objects.filter(id=id).exists():
                instances = models.Workspace.objects.get(id=id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()
    
    
    
    #发布/回收工作区
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def publish_workspace_by_id(self, request):  
        id = int(request.query_params.get('id', -1))
        published=request.query_params.get('published')=='true'
        if id is not None and id != '':
            if models.Workspace.objects.filter(id=id).exists():
                instance = models.Workspace.objects.get(id=id)
                instance.published=published
                instance.save()
                return DetailResponse()
        return ErrorResponse()
    
    
    #chat
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

class ChatViewSet(ViewSet):
    @action(methods=["POST"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    async def chater(self, request):  
        workspace_id = int(request.query_params.get('workspace_id', -1))
        messages=request.query_params.get('messages', None)
        published=request.query_params.get('published')=='true'
        model_id=self._get_model_id()
        if model_id is not None:
                await asyncio.sleep(1)
                return JsonResponse({"message": "异步视图已执行"})
        return JsonResponse({"message": "异步视图执行"})
    
    @sync_to_async
    def _get_model_id(self,workspace_id):
       if models.Workspace.objects.filter(id=workspace_id).exists():
          instance =models.Workspace.objects.get(id=workspace_id)
          return instance.model_id
       return None