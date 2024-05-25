from datetime import datetime
import json
from django.db.models import Q
import django

django.setup()  # 不加这句导入models会报exceptions.AppRegistryNotReady
from app import models
from django.core.cache import cache


def train_status_handler(json_msg: json, TcpSocket):
    status = json_msg.get("data").get("status")
    task_id = json_msg.get("task")
    task = None
    if models.Task.objects.filter(id=task_id).exists():
        task = models.Task.objects.get(id=task_id)
    if status == "finish":
        if task is not None:
            task.status = "finish"
            task.end_time = datetime.now()
            task.save()
            # 自动生成模型
            # models.LargeModel.save_model(adapter_name_or_path=task.output_dir,model_params=task.model_params)
            # 发送获取checkpoint命令
            device_key = json_msg.get("origin")
            TcpSocket.send_data(
                {"type": "get_checkpoints", "args": {"output_path": task.output_dir}},
                device_key,
            )
    elif status == "terminate" or status == "error":
        if task is not None:
            task.status = "terminate"
            task.end_time = datetime.now()
            task.save()
    elif status == "正在启动任务":
        if task is not None:
            task.status = "processing"
            task.start_time = datetime.now()
            task.save()


def device_status_handler(json_msg: json):
    # device_list = json_msg.get("data").get("device_list")
    # current_online = [
    #     key for key, value in device_list.items() if value.get("is_online")
    # ]
    # online_devices = cache.get("online_devices")
    # flag = False
    # if online_devices is None:
    #     flag = True
    # else:
    #     set1 = set([key for key in current_online])
    #     set2 = set(online_devices)
    #     if set1 != set2:
    #         flag = True
    # if not flag:
    #     return
    # cache.set(
    #     "online_devices", [key for key in current_online], timeout=100
    # )  # 设置一个缓存超时时间
    # devices = models.Device.objects.all()
    # for device in devices:
    #     online = device.device_key in current_online
    #     device.is_online = online
    #     device.save()
    device_key = json_msg.get("origin")
    online_devices = cache.get("online_devices")
    flag = False
    if online_devices is None:
        flag = True
    else:
        if device_key not in online_devices:
            flag = True
    if not flag:
        return
    new_list = online_devices if online_devices is not None else []
    new_list.append(device_key)
    cache.set("online_devices", new_list, timeout=100)  # 设置一个缓存超时时间
    devices = models.Device.objects.all()
    for device in devices:
        online = device.device_key in new_list
        device.is_online = online
        device.save()


# #检查设备离线
# def check_device_offline():
#     while True:
#         try:
#             time.sleep(15)
#             cur_time=datetime.now()
#             device_list={}
#             for key in device_status.keys():
#                 last_online_time=device_status[key]["last_online_time"]
#                 # 计算时间差
#                 time_difference = cur_time - last_online_time
#                 if   time_difference.total_seconds()>15:
#                     device_status[key]["is_online"]=False
#                 device_list[key]={"is_online": device_status[key]["is_online"]}

#         except Exception as e:
#             print(e)


def loss_log_handler(json_msg: json):
    loss_value = json_msg.get("data").get("loss_value")
    task_id = json_msg.get("task")
    task = None
    if models.Task.objects.filter(id=task_id).exists():
        task = models.Task.objects.get(id=task_id)
        json_log = task.loss_log if task.loss_log is not None else []
        json_log.append(
            {
                "current_steps": loss_value.get("current_steps"),
                "loss": loss_value.get("loss"),
            }
        )
        task.loss_log = json_log
        task.save()


def train_task_list_handler(json_msg: json):
    train_task_list = json_msg.get("data").get("data")

    device_key = json_msg.get("origin")
    running_task_id = [
        int(train_task.get("train_id").split("_")[1]) for train_task in train_task_list
    ]
    cache_running_train_tasks = cache.get("running_train_tasks", [])
    set1 = set(running_task_id)
    set2 = set(cache_running_train_tasks)
    if set1.issubset(set2):
        return

    models.Task.objects.filter(id__in=running_task_id).update(status="processing")

    # 获取该gpu服务器上所有 train task 的 ID
    all_train_ids = set(
        models.Task.objects.filter(device__device_key=device_key).values_list(
            "id", flat=True
        )
    )

    unrunning_train_task_ids = all_train_ids - set(running_task_id)

    models.Task.objects.filter(
        id__in=list(unrunning_train_task_ids), status="processing"
    ).update(status="terminate")

    all_running_train_task_ids = list(
        models.Task.objects.filter(status="processing").values_list("id", flat=True)
    )
    cache.set("running_train_tasks", all_running_train_task_ids)


def chat_task_list_handler(json_msg: json):
    device_key = json_msg.get("origin")
    chat_task_list = (
        json_msg.get("data").get("data")
        if json_msg.get("data").get("data") is not None
        else []
    )
    ready_workspace_id = [
        int(chat_task.get("workspace_id").split("_")[1])
        for chat_task in chat_task_list
        if chat_task.get("status") == "ready"
    ]
    key_name = f"ready_workspace_ids_on{device_key}"
    cache_ready_workspace_id = cache.get(key_name, None)

    set1 = set(ready_workspace_id)
    set2 = set(cache_ready_workspace_id if cache_ready_workspace_id is not None else [])
    if cache_ready_workspace_id is not None and set1 == set2:
        return
    # 更新 ready 的 Workspace
    models.Workspace.objects.filter(id__in=ready_workspace_id).update(published=True)

    # 获取该gpu服务器上所有 Workspace 的 ID
    device_all_workspace_ids = set(
        models.Workspace.objects.filter(
            model__resource__device_key=device_key
        ).values_list("id", flat=True)
    )

    # 找出该gpu服务器上所有不在 ready_workspace_id 中的 Workspace 的 ID
    unready_workspace_ids = device_all_workspace_ids - set(ready_workspace_id)

    # 更新剩下的 Workspace 为 not published
    models.Workspace.objects.filter(id__in=list(unready_workspace_ids)).update(
        published=False
    )

    all_ready_workspace_ids = list(
        models.Workspace.objects.filter(published=True).values_list("id", flat=True)
    )
    cache.set(key_name, ready_workspace_id)
    cache.set("ready_workspace_ids", all_ready_workspace_ids)


def gpu_memory_list_handler(json_msg: json):
    device_key = json_msg.get("origin")
    gpu_memory_list = (
        json_msg.get("data").get("data")
        if json_msg.get("data").get("data") is not None
        else []
    )
    models.Device.objects.filter(device_key=device_key).update(
        gpu_memory=gpu_memory_list
    )


def get_checkpoints_handler(json_msg: json):
    device_key = json_msg.get("origin")
    output_path = json_msg.get("data").get("output_path")
    checkpoints = json_msg.get("data").get("result")
    if checkpoints is not None:
        models.Task.objects.filter(
            Q(output_dir=output_path) & Q(device__device_key=device_key)
        ).update(checkpoints=checkpoints)


def export_model_handler(json_msg: json):
    task_id = json_msg.get("task")
    message = json_msg.get("data").get("message")
    result = json_msg.get("data").get("result")
    task = models.ExportModelTask.objects.filter(id=task_id).first()
    if task is not None:
        task.end_time = datetime.now()
        task.status = "success" if result else "failed"
        task.save()
    # 创建新模型
    if result:
        finetuning_task = task.finetuning_task
        if finetuning_task is not None:
            large_model = models.LargeModel()
            large_model.model_name = task.extra_data.get("model_name")
            large_model.description = task.extra_data.get("description")
            large_model.finetuning_task = finetuning_task
            large_model.type = finetuning_task.model_params.get("type")
            large_model.resource = finetuning_task.device
            large_model.model_path = task.export_dir
            large_model.is_partial = False
            base_model_id = finetuning_task.get_base_model()
            base_model = models.BaseModel.objects.filter(id=base_model_id).first()
            large_model.base = base_model
            large_model.save()


def upload_model_to_hf_handler(json_msg: json):
    task_id = json_msg.get("task")
    status = json_msg.get("data").get("status")
    message = json_msg.get("data").get("message")
    task = models.UploadModelTask.objects.filter(id=task_id).first()
    if task is not None:
        task.end_time = datetime.now()
        task.status = status
        if message is not None:
            task.message = message
        task.save()
