import threading
import django

from app.utils.socket_client import TcpScoket

from app.utils.websocket import WebSocketManager

# 在Django设置完成后立即运行的启动代码
django.setup()
def isKeyProcess():
  import os
  return os.environ.get('RUN_MAIN')=='true'
if (isKeyProcess()):
    websocket=WebSocketManager()
    instance=TcpScoket()
    print("ssssssssssss")
   