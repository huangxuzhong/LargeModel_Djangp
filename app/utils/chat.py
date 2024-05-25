import asyncio
from datetime import datetime
import threading
from django.core.cache import cache


class ChatStorage:
    # msgs = {}

    @staticmethod
    def add_message(msg):
        uuid = msg.get("uuid")
        response = msg.get("result")
        cache.set(
            f"chatmsg_{uuid}",
            {"response": response, "create_time": datetime.now()},
            timeout=600,
        )  # 设置一个缓存超时时间
        # ChatStorage.msgs[uuid] = {"response": response, "create_time": datetime.now()}

    @staticmethod
    def get_message(uuid):

        msg = cache.get(f"chatmsg_{uuid}")
        # msg = ChatStorage.msgs.get(uuid)
        # if msg is not None:
        #     del ChatStorage.msgs[uuid]
        return msg["response"] if msg is not None else None

    @staticmethod
    async def _wait_for_message(uuid):
        while True:
            response = ChatStorage.get_message(uuid)
            if response is None:
                await asyncio.sleep(0.2)
            else:
                return response

    @staticmethod
    async def async_get_message(uuid, timeout=20):
        try:
            result = await asyncio.wait_for(
                ChatStorage._wait_for_message(uuid), timeout
            )
            return result
        except asyncio.TimeoutError as e:
            raise e


#     @staticmethod
#     # 清除10分钟内未被读取的消息
#     def clear_messages():
#         keys_to_delete = []
#         for key in ChatStorage.msgs:
#             delta = datetime.now() - ChatStorage.msgs[key]["create_time"]
#             # 获取差值的秒数
#             seconds_difference = delta.total_seconds()
#             if seconds_difference > 600:
#                 keys_to_delete.append(key)
#         # 在迭代结束后删除这些键
#         for key in keys_to_delete:
#             del ChatStorage.msgs[key]

#     @staticmethod
#     def start_cleanup_timer(interval=600):

#         def cleanup():

#             ChatStorage.clear_messages()

#             ChatStorage.start_cleanup_timer(interval)  # 递归调用以保持定时器运行

#         timer = threading.Timer(interval, cleanup)

#         timer.start()


# ChatStorage.start_cleanup_timer(600)


# async def my_coroutine():
#     # 这里是你的异步操作，例如网络请求、文件读写等
#     await asyncio.sleep(1)
#     return "异步操作完成"


# async def wait_for_result_with_timeout(coroutine, timeout):
#     try:
#         result = await asyncio.wait_for(coroutine, timeout)
#         return result
#     except asyncio.TimeoutError:
#         return "操作超时"


# async def main():
#     result = await wait_for_result_with_timeout(my_coroutine(), 2)
#     print(result)


# if __name__ == "__main__":
#     asyncio.run(main())
