import json
import queue
import socket
import struct
import threading
from time import sleep
import configparser
import time
from app.utils.chat import ChatStorage
import django
from django.core.cache import cache
import pika
from app.utils.messgae_handler import (
    chat_task_list_handler,
    device_status_handler,
    train_task_list_handler,
    upload_model_to_hf_handler,
    export_model_handler,
    get_checkpoints_handler,
    gpu_memory_list_handler,
    loss_log_handler,
    train_status_handler,
)
from django_redis import get_redis_connection

django.setup()  # 不加这句导入models会报exceptions.AppRegistryNotReady
from app import models
from app.utils.websocket import WebSocketManager
import logging


class Comm:

    local_machine_id = None
    connection = None
    public_connection = None
    channel = None
    public_channel = None
    connected = False
    instance = None
    public_lock = threading.Lock()
    reconnect_lock = threading.Lock()

    def __init__(self) -> None:
        Comm.instance = self

    def start(self):
        with Comm.reconnect_lock:
            if Comm.connected:
                return
            try:
                # 读取配置文件
                config = configparser.ConfigParser()
                config.read("config.ini")
                server_ip = config.get("server", "ip")
                rabbitmq_username = config.get("rabbitmq", "username")
                rabbitmq_password = config.get("rabbitmq", "password")
                rabbitmq_port = int(config.get("rabbitmq", "port"))
                Comm.local_machine_id = "django"
            except Exception as e:
                logging.error(str(e))
                return
            try:
                user_info = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)

                Comm.connection = pika.BlockingConnection(
                    pika.ConnectionParameters(server_ip, rabbitmq_port, "/", user_info)
                )
                Comm.channel = Comm.connection.channel()
                Comm.public_connection = pika.BlockingConnection(
                    pika.ConnectionParameters(
                        server_ip, rabbitmq_port, "/", user_info, heartbeat=0
                    )
                )
                Comm.public_channel = Comm.public_connection.channel()

                Comm.channel.queue_declare(queue=Comm.local_machine_id)

                Comm.channel.basic_consume(
                    queue=Comm.local_machine_id,  # 接收指定queue的消息
                    auto_ack=True,  # 指定为True，表示消息接收到后自动给消息发送方回复确认，已收到消息
                    on_message_callback=self.__handle_read,  # 设置收到消息的回调函数
                )
                Comm.connected = True
                print("已连接到rabbitmq")
            except Exception as e:
                logging.error(str(e))
                if not Comm.connected:
                    print("连接rabbitmq 失败，将在10秒后自动重连")
                    Comm.close_connection()
                    time.sleep(10)
                    self.start()
                    return
        try:
            # 一直处于等待接收消息的状态，如果没收到消息就一直处于阻塞状态，收到消息就调用上面的回调函数
            Comm.channel.start_consuming()
        except Exception as e:
            logging.error(str(e))
            print("rabbitmq 异常，将在10秒后自动重连")
            Comm.close_connection()
            time.sleep(10)
            self.start()

    def __handle_read(self, ch, method, properties, msg):
        try:
            json_msg = json.loads(msg)
            print(f"收到来自服务器的数据：{msg.decode('utf-8')}")
            self._handle_msg(json_msg)
        except json.decoder.JSONDecodeError as e:
            print(f"JSON解析失败:{msg.decode('utf-8')}")
        except Exception as e:
            print(f"处理数据异常:{e},数据{msg}")

    def _handle_msg(self, json_msg):
        # response_type=json_msg.get("data").get("response_type")

        uuid = json_msg.get("data").get("uuid")
        response_type = json_msg.get("data").get("response_type")
        if json_msg.get("task") is not None:
            json_msg["task"] = json_msg.get("task").split("_")[1]

        if uuid is not None:
            ChatStorage.add_message(json_msg.get("data"))
            return

        if response_type == "train_status":
            con = get_redis_connection("default")
            con.rpush("train_logs", json.dumps(json_msg))
            train_status_handler(json_msg, Comm)
            return
        # 训练过程中的loss信息
        loss_value = json_msg.get("data").get("loss_value")
        if loss_value is not None:
            loss_log_handler(json_msg)

        # 模型推理任务列表
        if response_type == "chat_task_list":
            chat_task_list_handler(json_msg)
            return
        if response_type == "train_task_list":
            train_task_list_handler(json_msg)
            return
        # gpu内存信息
        if response_type == "gpu_memory_list":
            gpu_memory_list_handler(json_msg)
            return
        # checkpoint列表
        if response_type == "get_checkpoints":
            get_checkpoints_handler(json_msg)
            return
        # 模型合并结果
        if response_type == "export_model":
            export_model_handler(json_msg)
            return
        # 上传模型到HF
        if response_type == "upload_model_to_hf":
            upload_model_to_hf_handler(json_msg)
            return
        #  算力服务器keepalive
        if response_type == "keepalive":
            device_status_handler(json_msg)
            return
        else:  # 训练过程中产生的输出信息
            con = get_redis_connection("default")
            con.rpush("train_logs", json.dumps(json_msg))

    @staticmethod
    def send_data(data, target):
        # 使用缓存来避免查询数据库
        con = get_redis_connection("default")
        target_status = con.hget("device_status", target)

        is_online = (
            json.loads(target_status)["is_online"]
            if target_status is not None
            else False
        )
        if not is_online:
            return False

        try:
            with Comm.public_lock:
                if not Comm.connected:
                    Comm.instance.start()
                    return
                body = {"origin": Comm.local_machine_id, "target": target, "data": data}
                Comm.public_channel.queue_declare(queue=target)
                Comm.public_channel.basic_publish(
                    exchange="",  # 当前是一个简单模式，所以这里设置为空字符串就可以了
                    routing_key=target,  # 指定消息要发送到哪个queue
                    body=json.dumps(body),  # 指定要发送的消息
                )
                print(f"发送数据{body}")
        except pika.exceptions.ChannelWrongStateError as e:
            logging.error(str(e))
            print("rabbitmq 连接异常，将在10秒后自动重连")
            Comm.close_connection()
            Comm.instance = Comm()
            Comm.instance.start()
        return True

    @staticmethod
    def close_connection():
        # 关闭连接
        try:
            if hasattr(Comm.channel, "is_open") and Comm.channel.is_open:
                Comm.channel.close()
            if hasattr(Comm.connection, "is_open") and Comm.connection.is_open:
                Comm.connection.close()
            if hasattr(Comm.public_channel, "is_open") and Comm.public_channel.is_open:
                Comm.public_channel.close()
            if (
                hasattr(Comm.public_connection, "is_open")
                and Comm.public_connection.is_open
            ):
                Comm.public_connection.close()
        except Exception as e:
            logging.error(str(e))
        finally:
            Comm.connected = False
