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
            models.LargeModel.save_model(adapter_name_or_path=task.output_dir,model_params=task.model_params)
    elif status=="terminate" or status=="error":
        if task is not None:
            task.status="terminate"
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


def loss_log_handler(json_msg:json):
    loss_value=json_msg.get("data").get('loss_value')
    task_id=json_msg.get("task")  
    task=None
    if models.Task.objects.filter(id=task_id).exists():
        task=models.Task.objects.get(id=task_id)
        json_log=task.loss_log if task.loss_log is not None else []
        json_log.append({"current_steps":loss_value.get("current_steps"),"loss":loss_value.get("loss")})
        task.loss_log=json_log
        task.save()



def chat_task_list_handler(json_msg: json):
    chat_task_list = json_msg.get("data").get('data') if json_msg.get("data").get('data') is not None else []
    ready_workspace_id = [int(chat_task.get('workspace_id')) for chat_task in chat_task_list if chat_task.get('status') == 'ready']
    # 更新 ready 的 Workspace  
    models.Workspace.objects.filter(id__in=ready_workspace_id).update(published=True)  
    
    # 获取所有 Workspace 的 ID  
    all_workspace_ids = set(models.Workspace.objects.values_list('id', flat=True))  
    
    # 在 Python 中找出所有不在 ready_workspace_id 中的 Workspace 的 ID  
    unready_workspace_ids = all_workspace_ids - set(ready_workspace_id)  
    
    # 更新剩下的 Workspace 为 not published  
    models.Workspace.objects.filter(id__in=list(unready_workspace_ids)).update(published=False)
