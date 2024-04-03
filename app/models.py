from datetime import datetime
import json
from django.contrib.auth.models import AbstractUser
from django.db import models


from largeModel_django import settings
from rest_framework import serializers

# Create your models here.
class Users(AbstractUser):
    username = models.CharField(max_length=150, unique=True, db_index=True, verbose_name="用户账号",
                                help_text="用户账号")
    is_use_validity_period=models.BooleanField(default=False)#是否启用有效期
    validity_period_start=models.DateTimeField(null=True)#有效期开始时间
    validity_period_end=models.DateTimeField(null=True)#有效期结束时间
    # employee_no = models.CharField(max_length=150, unique=True, db_index=True, null=True, blank=True,
    #                                verbose_name="工号", help_text="工号")
    # email = models.EmailField(max_length=255, verbose_name="邮箱", null=True, blank=True, help_text="邮箱")
    # mobile = models.CharField(max_length=255, verbose_name="电话", null=True, blank=True, help_text="电话")
    # avatar = models.CharField(max_length=255, verbose_name="头像", null=True, blank=True, help_text="头像")
    # name = models.CharField(max_length=40, verbose_name="姓名", help_text="姓名")
    # GENDER_CHOICES = (
    #     (0, "未知"),
    #     (1, "男"),
    #     (2, "女"),
    # )
    # gender = models.IntegerField(
    #     choices=GENDER_CHOICES, default=0, verbose_name="性别", null=True, blank=True, help_text="性别"
    # )
   
    # last_token = models.CharField(max_length=255, null=True, blank=True, verbose_name="最后一次登录Token",
    #                               help_text="最后一次登录Token")

    def set_password(self, raw_password):
        super().set_password(raw_password)
    


    class Meta:
        db_table = "system_users"
        verbose_name = "用户表"
        verbose_name_plural = verbose_name
        # ordering = ("-create_datetime",)


class CoreModel(models.Model):
    """
    核心标准抽象模型模型,可直接继承使用
    增加审计字段, 覆盖字段时, 字段名称请勿修改, 必须统一审计字段名称
    """
    id = models.BigAutoField(primary_key=True, help_text="Id", verbose_name="Id")
    description = models.CharField(max_length=255, verbose_name="描述", null=True, blank=True, help_text="描述")
    creator = models.ForeignKey(to=settings.AUTH_USER_MODEL, related_query_name='creator_query', null=True,
                                verbose_name='创建人', help_text="创建人", on_delete=models.SET_NULL,
                                db_constraint=False)
    modifier = models.CharField(max_length=255, null=True, blank=True, help_text="修改人", verbose_name="修改人")
    dept_belong_id = models.CharField(max_length=255, help_text="数据归属部门", null=True, blank=True,
                                      verbose_name="数据归属部门")
    update_datetime = models.DateTimeField(auto_now=True, null=True, blank=True, help_text="修改时间",
                                           verbose_name="修改时间")
    create_datetime = models.DateTimeField(auto_now_add=True, null=True, blank=True, help_text="创建时间",
                                           verbose_name="创建时间")

    class Meta:
        abstract = True
        verbose_name = '核心模型'
        verbose_name_plural = verbose_name

class BaseModel(models.Model):
    name= models.CharField(max_length=255, null=True, blank=True)
    model_path=models.CharField(max_length=255, null=True, blank=True)



class Device(models.Model):
    device_name = models.CharField(max_length=2552)
    device_key= models.CharField(max_length=50,unique=True)
    create_time = models.DateTimeField(auto_created=True, auto_now_add=True, null=True, blank=True)
    description= models.CharField(max_length=255, null=True, blank=True)
    is_online=models.BooleanField(default=False)
    gpu_memory=models.JSONField(null=True)
    is_disable=models.BooleanField(default=False)#是否禁用

#模型训练任务    
class Task(models.Model):
    task_name = models.CharField(max_length=255, null=True, blank=True)
    create_time = models.DateTimeField(auto_created=True, auto_now_add=True, null=True, blank=True)
    start_time = models.DateTimeField( null=True, blank=True )
    end_time = models.DateTimeField( null=True, )
    status= models.CharField(max_length=10, null=True, blank=True,default="unstart")
    config=models.JSONField(null=True)
    adapter_name_or_path=models.CharField(max_length=255, null=True, blank=True, default='')
    output_dir=models.CharField(max_length=255, null=True, blank=True, default='')
    model_params=models.JSONField(null=True)
    device=models.ForeignKey(Device,null=True, on_delete=models.SET_NULL)
    loss_log=models.JSONField( null=True)
    checkpoints=models.JSONField( null=True)
   

    def get_finetuning_type(self):
        return self.config.get("finetuning_type")


#模型合并任务
class ExportModelTask(models.Model):
    task_name = models.CharField(max_length=255, null=True, blank=True)
    create_time = models.DateTimeField(auto_created=True, auto_now_add=True, null=True, blank=True)
    start_time = models.DateTimeField( null=True, blank=True )
    end_time = models.DateTimeField( null=True, )
    status= models.CharField(max_length=10, null=True, blank=True,default="unstart")
    adapter_name_or_path=models.CharField(max_length=255, null=True, blank=True, default='')
    model_name_or_path=models.CharField(max_length=255, null=True, blank=True, default='')
    template=models.CharField(max_length=255, null=True, blank=True, default='default')
    export_dir=models.CharField(max_length=255, null=True, blank=True)
    finetuning_task=models.ForeignKey(Task, on_delete=models.SET_NULL, to_field='id',null=True,)
    extra_data=models.JSONField(null=True)
   
class LargeModel(models.Model):
    model_name = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)
    base=models.ForeignKey(BaseModel, on_delete=models.SET_NULL, related_name='up_model', to_field='id',null=True,)
    # base = models.CharField(max_length=255, null=True, blank=True)
    dataset = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    resource = models.CharField(max_length=255, null=True, blank=True)
    create_time = models.DateTimeField(auto_created=True, auto_now_add=True, null=True, )
    introduction = models.CharField(max_length=255, null=True, blank=True, default='')
    user_manual = models.CharField(max_length=255, null=True, blank=True, default='')
    service_name = models.CharField(max_length=255, null=True, blank=True, default='')
    interface_address = models.CharField(max_length=255, null=True, blank=True, default='')
    has_configured_extra_info = models.BooleanField(default=False)
    adapter_name_or_path= models.CharField(max_length=255, null=True, blank=True, default='')
    finetuning_task=models.ForeignKey(Task, on_delete=models.SET_NULL, to_field='id',null=True,)
    model_path=models.CharField(max_length=255, null=True, blank=True)#由lora生成且未合并权重文件的模型的model_path为NULL
    is_partial=models.BooleanField(default=True,null=True,)#由lora微调生成且未合并权重文件时为True"

    # #保存模型
    # @staticmethod
    # def save_model(adapter_name_or_path:str,model_params:json):
    #     if adapter_name_or_path is None or model_params is None:
    #         return False
    #     else:
    #         model_params["adapter_name_or_path"]=adapter_name_or_path
    #         serializer = LargeModelSerializer(data=model_params)
    #         if serializer.is_valid():
    #             serializer.save()
    #             return True
    #         return False

  
class LargeModelSerializer(serializers.ModelSerializer):
    create_time = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
    def to_internal_value(self, data):
        # 在这里对data进行预处理
        data['create_time'] = datetime.now()
        data['dataset'] = json.dumps(data['dataset'])
        return super().to_internal_value(data)
    class Meta:
        model = LargeModel
        fields = '__all__'




class Dataset(models.Model):
    dataset_name = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    resource = models.CharField(max_length=255, null=True, blank=True)
    create_time = models.DateTimeField(auto_created=True, auto_now_add=True, null=True, )
    is_rank_dataset=models.BooleanField(default=False,null=False)#是否偏好数据集
class Workspace(models.Model):
    workspace_name = models.CharField(max_length=255, null=True, blank=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    creator=models.ForeignKey(Users, on_delete=models.SET_NULL, related_name='created_workspace', to_field='id',null=True,)
    model=models.ForeignKey(LargeModel, on_delete=models.SET_NULL, related_name='related_workspace', to_field='id',null=True,)
    create_time = models.DateTimeField(auto_created=True, auto_now_add=True, null=True, )
    published=models.BooleanField(default=False,null=False)
  




class LoginLog(CoreModel):
    LOGIN_TYPE_CHOICES = (
        (1, "普通登录"),
        (2, "普通扫码登录"),
        (3, "微信扫码登录"),
        (4, "飞书扫码登录"),
        (5, "钉钉扫码登录"),
        (6, "短信登录")
    )
    username = models.CharField(max_length=150, verbose_name="登录用户名", null=True, blank=True,
                                help_text="登录用户名")
    ip = models.CharField(max_length=32, verbose_name="登录ip", null=True, blank=True, help_text="登录ip")
    agent = models.TextField(verbose_name="agent信息", null=True, blank=True, help_text="agent信息")
    browser = models.CharField(max_length=200, verbose_name="浏览器名", null=True, blank=True, help_text="浏览器名")
    os = models.CharField(max_length=200, verbose_name="操作系统", null=True, blank=True, help_text="操作系统")
    continent = models.CharField(max_length=50, verbose_name="州", null=True, blank=True, help_text="州")
    country = models.CharField(max_length=50, verbose_name="国家", null=True, blank=True, help_text="国家")
    province = models.CharField(max_length=50, verbose_name="省份", null=True, blank=True, help_text="省份")
    city = models.CharField(max_length=50, verbose_name="城市", null=True, blank=True, help_text="城市")
    district = models.CharField(max_length=50, verbose_name="县区", null=True, blank=True, help_text="县区")
    isp = models.CharField(max_length=50, verbose_name="运营商", null=True, blank=True, help_text="运营商")
    area_code = models.CharField(max_length=50, verbose_name="区域代码", null=True, blank=True, help_text="区域代码")
    country_english = models.CharField(max_length=50, verbose_name="英文全称", null=True, blank=True,
                                       help_text="英文全称")
    country_code = models.CharField(max_length=50, verbose_name="简称", null=True, blank=True, help_text="简称")
    longitude = models.CharField(max_length=50, verbose_name="经度", null=True, blank=True, help_text="经度")
    latitude = models.CharField(max_length=50, verbose_name="纬度", null=True, blank=True, help_text="纬度")
    login_type = models.IntegerField(default=1, choices=LOGIN_TYPE_CHOICES, verbose_name="登录类型",
                                     help_text="登录类型")

    class Meta:
        db_table = "system_login_log"
        verbose_name = "登录日志"
        verbose_name_plural = verbose_name
        ordering = ("-create_datetime",)
