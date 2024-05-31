from datetime import datetime
import threading
import time

import django

django.setup()
from app import models


class RunCheckUserExpiration:
    def __init__(self):
        t1 = threading.Thread(target=self._task)
        t1.start()

    def _task(self):
        while True:
            time.sleep(6)
            use_expiration_users = models.Users.objects.filter(
                is_use_validity_period=True
            )
            need_set_true = []
            need_set_false = []
            for user in use_expiration_users:
                if (
                    user.validity_period_start
                    <= datetime.now()
                    <= user.validity_period_end
                ):
                    if not user.is_active:
                        need_set_true.append(user.id)
                elif user.is_active:
                    need_set_false.append(user.id)
            models.Users.objects.filter(id__in=need_set_true).update(is_active=True)
            models.Users.objects.filter(id__in=need_set_false).update(is_active=False)
