import threading
import django

from app.utils.check_device_online import RunCheckDeviceOnline
from app.utils.check_user_expired import RunCheckUserExpiration
from app.utils.rabbitmq_comm import Comm


# 在Django设置完成后立即运行的启动代码
django.setup()


def isKeyProcess():
    import os

    return os.environ.get("RUN_MAIN") == "true"


if isKeyProcess():
    # 开启消息队列通讯
    comm = Comm()
    threading.Thread(target=comm.start).start()
    # 检查gpu服务器在线状态
    RunCheckDeviceOnline()
    # 检查用户有效期
    RunCheckUserExpiration()
    print("everything is ready")
