import asyncio
import datetime
import json
import threading
import time
from typing import Dict
import websockets
from .stack import MessageQueue


class WebSocketManager:
    _singal_instance = None
    task_to_websocket = {}
    # message_buffer=Dict[str,Stack]={}
    message_buffer = MessageQueue(max_size=200)

    def __new__(cls):
        if cls._singal_instance is None:
            cls._singal_instance = super().__new__(cls)
            # __init__()
            listen_thread = threading.Thread(target=cls._singal_instance.__stat_listen)
            listen_thread.start()
            send_thread = threading.Thread(target=cls._singal_instance._start_send_data)
            send_thread.start()
        return cls._singal_instance

    def __init__(self):
        print("init")

    def __stat_listen(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.get_event_loop().run_until_complete(
            websockets.serve(self.handle_connection, "localhost", 8460)
        )
        asyncio.get_event_loop().run_forever()

    def _start_send_data(self):
        asyncio.set_event_loop(asyncio.new_event_loop())
        asyncio.get_event_loop().run_until_complete(self._send_data())
        asyncio.get_event_loop().run_forever()

    async def _send_data(self):

        while True:
            try:
                await asyncio.sleep(1)

                if self.message_buffer.is_empty():
                    continue
                message = self.message_buffer.pop()
                task = str(message["task"])
                clients = self.task_to_websocket.get(task)
                if clients is not None:
                    for client in clients:
                        try:
                            await client.send(json.dumps(message))
                        except websockets.ConnectionClosed:
                            await client.close()
                            clients.remove(client)
            except Exception as e:
                print(e)

    @staticmethod
    def add_message(msg):
        WebSocketManager.message_buffer.push(msg)

    async def handle_connection(self, websocket, path):
        user = await websocket.recv()
        # 将客户端添加到已连接的客户端字典中
        if self.task_to_websocket.get(user) is None:
            self.task_to_websocket[user] = [websocket]
        else:
            self.task_to_websocket[user].append(websocket)
        print(f"{user} 已连接")

        try:
            while True:
                # time.sleep(1)#注意，此句会导致消息发送不出去
                await asyncio.sleep(1)
                msg = await websocket.recv()
                print("接收到：{msg}")

        except websockets.ConnectionClosed:
            # 当客户端断开连接时，将其从已连接的客户端字典中移除
            clients = self.task_to_websocket.get(user)
            if clients is not None:
                clients.remove(websocket)
                print(f"{user} 已断开连接")

    def create_websocket(self, task_id):
        pass
