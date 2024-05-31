from datetime import datetime
import json
import threading
import time

import django
import logging

django.setup()
from app import models
from django_redis import get_redis_connection


class RunCheckDeviceOnline:
    def __init__(self):
        t1 = threading.Thread(target=self._task)
        t1.start()

    def _task(self):

        while True:
            time.sleep(15)
            try:
                con = get_redis_connection("default")
                device_status = con.hgetall("device_status")
                cur_time = datetime.now()
                go_online_key = []
                for key, value in device_status.items():
                    key = key.decode("utf-8")
                    value = value.decode("utf-8")
                    status_json = json.loads(value)
                    last_online_time = datetime.strptime(
                        status_json.get("last_online_time"), "%Y-%m-%d %H:%M:%S"
                    )
                    # 计算时间差
                    time_difference = cur_time - last_online_time
                    if time_difference.total_seconds() < 15:

                        go_online_key.append(key)
                    else:
                        con.hset(
                            "device_status",
                            key,
                            json.dumps(
                                {
                                    "is_online": False,
                                    "last_online_time": status_json.get(
                                        "last_online_time"
                                    ),
                                }
                            ),
                        )

                models.Device.objects.filter(device_key__in=go_online_key).update(
                    is_online=True
                )
                models.Device.objects.exclude(device_key__in=go_online_key).update(
                    is_online=False
                )

            except Exception as e:
                logging.error(str(e))
