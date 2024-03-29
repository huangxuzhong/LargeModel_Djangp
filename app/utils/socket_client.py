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
from app.utils.messgae_handler import chat_task_list_handler, device_status_handler, export_model_handler, get_checkpoints_handler, gpu_memory_list_handler, loss_log_handler, train_status_handler
django.setup()#不加这句导入models会报exceptions.AppRegistryNotReady
from app import models
from app.utils.websocket import WebSocketManager  
from channels.db import database_sync_to_async    
from django.db import transaction 

class TcpScoket():
    read_buffer=queue.Queue() 
    send_buffer=queue.Queue()
    local_machine_id=None
    def __init__(self):
        #读取配置文件
        config = configparser.ConfigParser()  
        config.read('socket.ini')  
        self.server_port = config.get('server', 'port')  
        self.server_ip = config.get('server', 'ip')
        TcpScoket.local_machine_id=config.get('local', 'device_id')
        self.running=True
        self.run()
       

    def run(self):
        self.connect_to_server()
        self.read_thread = threading.Thread(target=self.__handle_read)
        self.read_thread.start()
        self.send_thread = threading.Thread(target=self.__handle_send)
        self.send_thread.start()
        #开启心跳包机制
        self.keep_alvie_thread= threading.Thread(target=self._keep_alvie)
        self.keep_alvie_thread.start()

    def connect_to_server(self):
        
        while self.running :
          
            try:
                # 创建socket对象
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                # 连接服务器
                self.client_socket.connect((self.server_ip, int(self.server_port)))
                # self.client_socket.setblocking(False)
                TcpScoket.send_data('我是web服务程序',"server")
                TcpScoket.send_data('请转发给llama1',"llama1")
                return
            except Exception as e:
                time.sleep(5)
        
          
    
    def close_connection(self):  
        if self.client_socket is not None:  
            self.client_socket.close()  
            self.client_socket = None  

    def _keep_alvie(self):
        while True:
            time.sleep(5)
            if self.client_socket is not None:
               TcpScoket.send_data({"type":"keepalive"},"server")
           

    def __handle_read(self):
        
        # 接收服务器发送的数据
        while self.running:
            try:
                if self.client_socket is None:
                    time.sleep(5)
                    continue
                length_bytes = self.client_socket.recv(4)  
                # 将字节转换回整数，得到消息长度  
                message_length = struct.unpack('>I', length_bytes)[0]  
                # 读取消息内容  
                msg = self.client_socket.recv(message_length)
            except Exception as e:
                print("socket连接失败")
                self.close_connection()  
                self.connect_to_server()
                continue
            try:  
                json_msg = json.loads(msg)
                print(f"收到来自服务器的数据：{msg.decode('utf-8')}")      
            except json.decoder.JSONDecodeError as e:
                print(f"JSON解析失败:{msg.decode('utf-8')}")
                continue
            try:
                self._handle_msg(json_msg)
            except Exception as e:
                print(e)
    
    def __handle_send(self):
         # 向消息服务器发送数据
         while self.running:       
              try:
                if self.client_socket is None:
                    time.sleep(5)
                    continue          
                data=self.send_buffer.get(block=True)
                self.client_socket.send(data)
              except Exception as e:                 
                print("socket连接失败")
                print(e)
                self.close_connection()  
                self.connect_to_server()
            
                
    def _handle_msg(self,json_msg):
        # response_type=json_msg.get("data").get("response_type")
     
        uuid=json_msg.get("data").get("uuid")
        response_type=json_msg.get("data").get("response_type")
        if json_msg.get("task") is not None:
           json_msg["task"]=  json_msg.get("task").split("_")[1]   
        #算力服务器状态信息
        if response_type=='devices_status':
            device_status_handler(json_msg)
            return;
        # if response_type=="chat":
        if uuid is not None:   
            ChatStorage.add_message(json_msg.get("data"))
        else:#训练过程中产生的输出信息
            WebSocketManager.add_message(json_msg)
        
        if response_type=="train_status":
            train_status_handler(json_msg,TcpScoket)
        #训练过程中的loss信息
        loss_value=json_msg.get("data").get("loss_value")
        if loss_value is not None:
            loss_log_handler(json_msg)

        #模型推理任务列表
        if response_type=="chat_task_list":
            chat_task_list_handler(json_msg)
            return
        #gpu内存信息
        if response_type=="gpu_memory_list":
            gpu_memory_list_handler(json_msg)
            return
        #checkpoint列表
        if response_type=="get_checkpoints":
            get_checkpoints_handler(json_msg)
            return
        #模型合并结果
        if response_type=="export_model":
            export_model_handler(json_msg)
            return
     

        

        


              
    @staticmethod
    def send_data(data,target):
        if target !="server":
            # 使用缓存来避免查询数据库          
            device_list = cache.get("online_devices")  
            is_online = target  in device_list if device_list is not None else False  
            if not is_online:  
                return False  
        body={"origin":TcpScoket.local_machine_id,"target":target,"data":data}
        str_body= bytes(json.dumps(body), 'utf-8')
        message = struct.pack('>I', len(str_body)) + str_body  
        TcpScoket.send_buffer.put(message)
        return True

    def disconnect_to_server(self):
        # 关闭连接
        self.client_socket.close()
        self.send_thread.stop();
        self.read_thread.stop();


# def get_device_by_key(target):  

#     with transaction.atomic():  
#         return models.Device.objects.filter(device_key=target).first()