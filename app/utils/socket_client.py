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

from app.utils.messgae_handler import chat_task_list_handler, device_status_handler, loss_log_handler, train_status_handler
django.setup()#不加这句导入models会报exceptions.AppRegistryNotReady
from app import models
from app.utils.websocket import WebSocketManager  
  

class TcpScoket():
    read_buffer=queue.Queue() 
    send_buffer=queue.Queue()
    local_machine_id=None
    def __init__(self):
       self.connect_to_server()
       #开启心跳包机制
       self.keep_alvie_thread= threading.Thread(target=self._keep_alvie)
       self.keep_alvie_thread.start()
        
    def connect_to_server(self):
         #读取配置文件
        config = configparser.ConfigParser()  
        config.read('socket.ini')  
        
        server_port = config.get('server', 'port')  
        server_ip = config.get('server', 'ip')
        TcpScoket.local_machine_id=config.get('local', 'device_id')
      
      
        # 创建socket对象
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # 连接服务器
            self.client_socket.connect((server_ip, int(server_port)))
            self.client_socket.setblocking(False)
            TcpScoket.send_data('我是web服务程序',"server")
            TcpScoket.send_data('请转发给llama1',"llama1")
        except ConnectionRefusedError:
            print("socket连接失败")
            timer = threading.Timer(5,   self.connect_to_server)#5秒后重新连接
            timer.start()
            return
        # 创建事件对象
        self.read_stop_event = threading.Event()
        self.send_stop_event = threading.Event()
        self.read_thread = threading.Thread(target=self.__handle_read,args=(self.read_stop_event,))
        self.read_thread.start()
        self.send_thread = threading.Thread(target=self.__handle_send,args=(self.send_stop_event,))
        self.send_thread.start()
    
    
    def _keep_alvie(self):
        while True:
            time.sleep(5)
            if self.client_socket is not None:
                TcpScoket.send_data({"type":"keepalive"},"server")
           

    def __handle_read(self,stop_event):
        
        # 接收服务器发送的数据
        while not stop_event.is_set():
            try:
                time.sleep(0.1)
                length_bytes = self.client_socket.recv(4)  
                # if not length_bytes:  # 没有数据则退出循环  
                #     break  
                # 将字节转换回整数，得到消息长度  
                message_length = struct.unpack('>I', length_bytes)[0]  
                # 读取消息内容  
                msg = self.client_socket.recv(message_length)  
                json_msg = json.loads(msg)
                print(f"收到来自服务器的数据：{msg.decode('utf-8')}")
                self._handle_msg(json_msg)
            except BlockingIOError:
                # 如果发生阻塞错误，说明没有数据可接收
                continue
            except json.decoder.JSONDecodeError as e:
                self.client_socket.recv(99999)#清空接收区缓存
                print(f"JSON解析失败/n{msg.decode('utf-8')}")
            except ConnectionResetError:
                print("socket连接失败")
                self.send_stop_event.set()
                timer = threading.Timer(5,   self.connect_to_server)#5秒后重新连接
                timer.start()
                return
            except Exception as e:
                print(e)
                
                
    def _handle_msg(self,json_msg):
        # response_type=json_msg.get("data").get("response_type")
        uuid=json_msg.get("data").get("uuid")
        response_type=json_msg.get("data").get("response_type")
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
           train_status_handler(json_msg)
        #训练过程中的loss信息
        loss_value=json_msg.get("data").get("loss_value")
        if loss_value is not None:
            loss_log_handler(json_msg)

        #模型推理任务列表
        
        if response_type=="chat_task_list":
            chat_task_list_handler(json_msg)
            return

        

        

    def __handle_send(self,stop_event):
         # 向消息服务器发送数据
         while not stop_event.is_set():
            #   sleep(50)
              data=self.send_buffer.get(block=True)
              try:
                  self.client_socket.send(data)
              except ConnectionResetError:
                print("socket连接失败")
                self.read_stop_event.set()
                timer = threading.Timer(5,   self.connect_to_server)#5秒后重新连接
                timer.start()
                return
              except Exception as e:
                print(e)


              
    @staticmethod
    def send_data(data,target):
        body={"origin":TcpScoket.local_machine_id,"target":target,"data":data}
        str_body= bytes(json.dumps(body), 'utf-8')
        message = struct.pack('>I', len(str_body)) + str_body  
        TcpScoket.send_buffer.put(message)

    def disconnect_to_server(self):
        # 关闭连接
        self.client_socket.close()
        self.send_thread.stop();
        self.read_thread.stop();