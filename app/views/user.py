
from rest_framework import serializers
from app import models
from app.models import Users
from rest_framework.decorators import action
from rest_framework.utils import json
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication
import rest_framework.permissions

from app.utils.json_response import DetailResponse, ErrorResponse


class UserSerializer(serializers.ModelSerializer):
   
    # def to_internal_value(self, data):
    #     # 在这里对data进行预处理
    #     data['create_time'] = datetime.now()
    #     data['dataset'] = json.dumps(data['dataset'])
    #     return super().to_internal_value(data)

    class Meta:
        model = Users
        # exclude = ['password' ]
        fields = ['id','username','email','is_active']
        


class UserViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.IsAdminUser]

    #
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAdminUser])
    def get_user_list(self, request):
        user = JWTAuthentication().authenticate(request)[0]
        print('userid', user.id)
        max_result = int(request.query_params.get('maxResult', 99999))
        skip_count = int(request.query_params.get('skipCount', 0))
       
        instances=models.Users.objects.filter(is_staff=False)
        serializer = UserSerializer(instances[ skip_count:skip_count + max_result], many=True)
        return DetailResponse(data={'total': len(instances), 'items': serializer.data})
    
    #删除用户
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAdminUser])
    def delete_user_by_id(self, request):
        user_id = request.query_params.get('userId')
        if user_id is not None and user_id != '':
            if models.Users.objects.filter(id=user_id).exists():
                instances = models.Users.objects.get(id=user_id)
                instances.delete()
                return DetailResponse()
        return ErrorResponse()
    
    
    #激活/冻结用户
    @action(methods=["GET"], detail=False, permission_classes=[rest_framework.permissions.IsAdminUser])
    def change_user_active_id(self, request):
        user_id = request.query_params.get('userId')
        is_active=request.query_params.get('isActive').lower() == "true" 
        if user_id is not None and user_id != '':
            if models.Users.objects.filter(id=user_id).exists():
                instance = models.Users.objects.get(id=user_id)
                instance.is_active=is_active
                instance.save()
                return DetailResponse()
        return ErrorResponse()
       