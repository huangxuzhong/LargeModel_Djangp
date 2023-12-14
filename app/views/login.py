import base64
import hashlib
from datetime import datetime, timedelta

import rest_framework.permissions
from django.contrib import auth
from django.contrib.auth import login,authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt

from rest_framework import serializers, views, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.status import HTTP_401_UNAUTHORIZED
from rest_framework.utils import json
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
# from rest_framework_jwt.utils import jwt_decode_handler

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.backends import TokenBackend
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from django.conf import settings

from app import models
from app.models import Users
from app.utils.json_response import ErrorResponse, DetailResponse, SuccessResponse
from app.utils.request_util import save_login_log
from app.utils.serializers import CustomModelSerializer
from app.utils.validator import CustomValidationError
from rest_framework.decorators import action, permission_classes


class LoginSerializer(TokenObtainPairSerializer):
    """
    登录的序列化器:
    重写djangorestframework-simplejwt的序列化器
    """
    captcha = serializers.CharField(
        max_length=6, required=False, allow_null=True, allow_blank=True
    )

    class Meta:
        model = Users
        fields = "__all__"
        read_only_fields = ["id"]

    default_error_messages = {"no_active_account": _("账号/密码错误")}

    def validate(self, attrs):
        #是否以管理员身份登录
        is_admin_login= bool(self.initial_data.get('isAdminLogin',False))
        if is_admin_login:
            exists=models.Users.objects.filter(is_staff=True ,username=attrs['username']).exists()
            if not exists:
                 return {"code": 200, "msg": "请输入正确用户名/密码","succeeded":False}
        #检查激活
        exists2=models.Users.objects.filter(username=attrs['username']).exists()
        if exists2:
           user=models.Users.objects.get(username=attrs['username']) 
           if not user.is_active:
                return {"code": 200, "msg": "当前用户已被禁用，请联系管理员","succeeded":False} 
                         
        data = super().validate(attrs)
        data["name"] = self.user.username
        # data["userId"] = self.user.id
        # data["avatar"] = self.user.avatar
        # data['user_type'] = self.user.user_type
        # dept = getattr(self.user, 'dept', None)
        # if dept:
        #     data['dept_info'] = {
        #         'dept_id': dept.id,
        #         'dept_name': dept.name,
        #     }
        # role = getattr(self.user, 'role', None)
        # if role:
        #     data['role_info'] = role.values('id', 'name', 'key')
        request = self.context.get("request")
        request.user = self.user
        # 记录登录日志
        # save_login_log(request=request)
        # 是否开启单点登录
        # if dispatch.get_system_config_values("base.single_login"):
        #     # 将之前登录用户的token加入黑名单
        #     user = Users.objects.filter(id=self.user.id).values('last_token').first()
        #     last_token = user.get('last_token')
        #     if last_token:
        #         try:
        #             token = RefreshToken(last_token)
        #             token.blacklist()
        #         except:
        #             pass
        #     # 将最新的token保存到用户表
        #     Users.objects.filter(id=self.user.id).update(last_token=data.get('refresh'))
        return {"code": 200, "msg": "请求成功","succeeded":True, "data": data}


class CustomTokenRefreshView(TokenRefreshView):
    """
    自定义token刷新
    """

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        try:
            token = RefreshToken(refresh_token)
            data = {
                "access": str(token.access_token),
                "refresh": str(token)
            }
        except:
            return ErrorResponse(status=HTTP_401_UNAUTHORIZED)
        return DetailResponse(data=data)


class LoginView(TokenObtainPairView):
    """
    登录接口
    """
    serializer_class = LoginSerializer
    permission_classes = []
    
    
    def admin_login(self,request):
        if request.method == 'POST':
            username = request.POST['username']
            password = request.POST['password']
            user = authenticate(request, username=username, password=password)
            if user is not None and user.is_staff:
                self.login(request, user)
                return JsonResponse({'status': 'success', 'message': '登录成功'})
            else:
                return JsonResponse({'status': 'error', 'message': '请使用管理员账户登录'})
        else:
            return JsonResponse({'status': 'error', 'message': '请求方法不支持'})


class LoginTokenSerializer(TokenObtainPairSerializer):
    """
    登录的序列化器:
    """

    class Meta:
        model = Users
        fields = "__all__"
        read_only_fields = ["id"]

    default_error_messages = {"no_active_account": _("账号/密码不正确")}

    def validate(self, attrs):
        if not getattr(settings, "LOGIN_NO_CAPTCHA_AUTH", False):
            return {"code": 4000, "msg": "该接口暂未开通!", "data": None}
        data = super().validate(attrs)
        data["name"] = self.user.name
        data["userId"] = self.user.id
        return {"code": 2000, "msg": "请求成功", "data": data}


class LoginTokenView(TokenObtainPairView):
    """
    登录获取token接口
    """

    serializer_class = LoginTokenSerializer
    permission_classes = []


class LogoutView(APIView):
    def post(self, request):
        Users.objects.filter(id=self.request.user.id).update(last_token=None)
        return DetailResponse(msg="注销成功")


class ApiLoginSerializer(CustomModelSerializer):
    """接口文档登录-序列化器"""

    username = serializers.CharField()
    password = serializers.CharField()

    class Meta:
        model = Users
        fields = ["username", "password"]


class ApiLogin(APIView):
    """接口文档的登录接口"""

    serializer_class = ApiLoginSerializer
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        user_obj = auth.authenticate(
            request,
            username=username,
            password=hashlib.md5(password.encode(encoding="UTF-8")).hexdigest(),
        )
        if user_obj:
            login(request, user_obj)
            return redirect("/")
        else:
            return ErrorResponse(msg="账号/密码错误")


# @permission_classes([rest_framework.permissions.AllowAny])
class DemoViewSet(GenericViewSet):
    permission_classes = [rest_framework.permissions.AllowAny]
    #
    @action(methods=["GET"], detail=False,permission_classes=[rest_framework.permissions.IsAuthenticated])
    def get_user_info(self, request):
        user = JWTAuthentication().authenticate(request)[0]
        print('userid', user.id)
        # return JsonResponse({"user": user.id})
        return DetailResponse(data={"user": user.username})

    @action(methods=["POST"], detail=False, permission_classes=[rest_framework.permissions.AllowAny])
    def register(self,request):
        data = json.loads(request.body)

        username = data["username"]
        email = data["email"]
        password = data["password"]

        user_is_exit = models.Users.objects.filter(username=username).exists()


        if  user_is_exit:
            return JsonResponse({"code": 200, "msg": "用户名已占用!"})
        # elif email_is_exit:
        #     return JsonResponse({"code": -1, "data": "邮箱已占用!"})
        #
        else:
            user_table = models.Users()
            user_table.username = username
            user_table.password=password
            # user_table.set_password(password)
            user_table.email = email
            user_table.save()

            return JsonResponse({"code": 200, "data": "successful","successed":True})


@csrf_exempt
@permission_classes([rest_framework.permissions.IsAuthenticated])
@login_required
def token_test(request):
    token = request.META.get('HTTP_AUTHORIZATION', None)
    user = JWTAuthentication().authenticate(request)[0]
    print('userid', user.id)
    # return JsonResponse({"user": user.username})
    return SuccessResponse(data={"user": user.username})
