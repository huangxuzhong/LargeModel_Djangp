"""
URL configuration for largeModel_django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers

import app
from app.views.login import CustomTokenRefreshView, LoginView, DemoViewSet
from app.views.large_model import LargeModelViewSet
from app.views.dataset import DatasetViewSet
from app.views.user import UserViewSet
from app.views.workspace  import WorkspaceViewSet,ChatViewSet
from app.views.base_model import BaseModelViewSet
from app.views.task import TaskViewSet
from app.views.device import DeviceViewSet
system_url = routers.SimpleRouter()
# system_url.register('users', DemoViewSet, basename='')
system_url.register(r'users', DemoViewSet, basename='')
system_url.register(r'models', LargeModelViewSet, basename='')
system_url.register(r'datasets', DatasetViewSet, basename='')
system_url.register(r'account', UserViewSet, basename='')
system_url.register(r'workspace', WorkspaceViewSet, basename='')
system_url.register(r'chat', ChatViewSet, basename='')
system_url.register(r'base_model', BaseModelViewSet, basename='')
system_url.register(r'tasks', TaskViewSet, basename='')
system_url.register(r'devices', DeviceViewSet, basename='')
urlpatterns = [
    path('admin/', admin.site.urls),
    path("user/login", LoginView.as_view(), name="token_obtain_pair"),
    path("user/admin_login", LoginView.as_view(), name="token_obtain_pair"),
    path("user/token_refresh",CustomTokenRefreshView.as_view())
    # path("chat/", chat,name="chat"),
    # path("users/get_user_info", DemoViewSet.as_view({'get': 'get_user_info'})),
    # path('user/tokentest',app.views.login.Demo.as_view()),

    # path('user/tokentest', app.views.login.token_test)
    # path('user/', include('app.urls')),
]

urlpatterns += system_url.urls
# 打印生成的url配置项
# for url in urlpatterns:
#     print(url)
