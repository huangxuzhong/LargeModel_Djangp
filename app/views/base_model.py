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

        fields = '__all__'


class BaseModelViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAuthenticated]

    #基座模型列表
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAuthenticated])
    def get_all_base_model(self, request):
   
        max_result = int(request.query_params.get('maxResult', 99999))
        skip_count = int(request.query_params.get('skipCount', 0))
      
        base_model_name = request.query_params.get('base_model_name')
        q_objects = Q()
      
        if base_model_name is not None and base_model_name != '':
            q_objects &= Q(name__contains=base_model_name)
         
        instances = models.BaseModel.objects.filter(q_objects)
        print(instances.query)
        serializer = BaseModelSerializer(instances[skip_count:skip_count + max_result], many=True)
        return DetailResponse(data={'total': len(instances), 'items': serializer.data})