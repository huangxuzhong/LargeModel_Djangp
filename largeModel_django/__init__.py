import threading
import django

from app.utils.check_user_expired import RunCheckUserExpiration
from app.utils.rabbitmq_comm import Comm
from app.utils.socket_client import TcpSocket

from app.utils.websocket import WebSocketManager

# 在Django设置完成后立即运行的启动代码
django.setup()


def isKeyProcess():
    import os

    return os.environ.get("RUN_MAIN") == "true"


if isKeyProcess():
    # websocket = WebSocketManager()
    comm = Comm()
    threading.Thread(target=comm.start).start()
    # instance = TcpSocket()
    RunCheckUserExpiration()
    print("everything is ready")
