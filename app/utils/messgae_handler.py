from datetime import datetime 
import json
from django.db.models import Q
import django
django.setup()#不加这句导入models会报exceptions.AppRegistryNotReady
from app import models
from django.core.cache import cache  

def train_status_handler(json_msg:json,TcpScoket):
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
            #自动生成模型
            # models.LargeModel.save_model(adapter_name_or_path=task.output_dir,model_params=task.model_params)
            #发送获取checkpoint命令
            device_key=json_msg.get("origin")
            TcpScoket.send_data({"type":"get_checkpoints","args":{"output_path":task.output_dir}},device_key)
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
    online_devices = cache.get("online_devices")
    flag=False  
    if online_devices is None:  
        flag=True
    else:
        set1 = set([key for key in device_list])  
        set2 = set(online_devices)
        if set1!=set2:
            flag=True
    if not flag:
        return
    cache.set("online_devices", [key for key in device_list], timeout=100)  # 设置一个缓存超时时间   
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
    ready_workspace_id = [int(chat_task.get('workspace_id').split("_")[1]) for chat_task in chat_task_list if chat_task.get('status') == 'ready']
    # 更新 ready 的 Workspace  
    models.Workspace.objects.filter(id__in=ready_workspace_id).update(published=True)  
    
    # 获取所有 Workspace 的 ID  
    all_workspace_ids = set(models.Workspace.objects.values_list('id', flat=True))  
    
    # 在 Python 中找出所有不在 ready_workspace_id 中的 Workspace 的 ID  
    unready_workspace_ids = all_workspace_ids - set(ready_workspace_id)  
    
    # 更新剩下的 Workspace 为 not published  
    models.Workspace.objects.filter(id__in=list(unready_workspace_ids)).update(published=False)


def gpu_memory_list_handler(json_msg: json):
    device_key=json_msg.get("origin")
    gpu_memory_list = json_msg.get("data").get('data') if json_msg.get("data").get('data') is not None else []
    models.Device.objects.filter(device_key=device_key).update(gpu_memory=gpu_memory_list)


def get_checkpoints_handler(json_msg: json):
    device_key=json_msg.get("origin")
    output_path = json_msg.get("data").get('output_path')
    checkpoints = json_msg.get("data").get('result')
    if checkpoints is not None:
        models.Task.objects.filter(Q(output_dir=output_path) & Q(resource=device_key)).update(checkpoints=checkpoints)


def export_model_handler(json_msg: json):
    task_id=json_msg.get("task")  
    message = json_msg.get("data").get('message')
    result = json_msg.get("data").get('result')
    task=models.ExportModelTask.objects.filter(id=task_id).first()
    if task is not None:
        task.end_time=datetime.now()
        task.status='success' if result else "failed"
        task.save()
    #创建新模型
    if result:
        finetuning_task=task.finetuning_task
        if finetuning_task is not None:
            large_model=models.LargeModel()
            large_model.model_name=task.extra_data.get("model_name")
            large_model.description=task.extra_data.get("description")
            large_model.finetuning_task=finetuning_task
            large_model.type=finetuning_task.model_params.get('type')
            large_model.resource=finetuning_task.resource
            large_model.model_path=task.export_dir
            large_model.is_partial=False
            large_model.save()
    


