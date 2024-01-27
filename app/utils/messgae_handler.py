from datetime import datetime 
import json

import django
django.setup()#不加这句导入models会报exceptions.AppRegistryNotReady
from app import models


def train_status_handler(json_msg:json):
    status=json_msg.get("data").get("status")
    task_id=json_msg.get("task")  
    task=None
    if models.Task.objects.filter(id=task_id).exists():
        task=models.Task.objects.get(id=task_id)
    if status=="finish":
        if task is not None:
            task.status="finish"
            task.end_time=datetime.now()
            task.save()
            models.LargeModel.save_model(adapter_name_or_path=task.adapter_name_or_path,model_params=task.model_params)
    elif status=="terminate" or status=="error":
        if task is not None:
            task.status="finish"
            task.end_time=datetime.now()
            task.save()
    elif status=="正在启动任务":
         if task is not None:
            task.status="processing"
            task.start_time=datetime.now()
            task.save()


def device_status_handler(json_msg:json):
    device_list=json_msg.get("data").get('device_list')
    devices=models.Device.objects.all()
    for device in devices:
        target=device_list.get(device.device_key)
        if target is not None:
            device.is_online=target["is_online"]
        else:
            device.is_online=False
        device.save()
        