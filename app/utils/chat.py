import asyncio

class ChatStorage():
    msgs={}
    @staticmethod
    def add_message(msg):
        uuid=msg.get("uuid")
        response=msg.get("result")
        ChatStorage.msgs[uuid]=response
       
    
    @staticmethod
    def get_message(uuid):
        response= ChatStorage.msgs.get(uuid)
        if response is not None:
            del ChatStorage.msgs[uuid]
        return response
    
    
    @staticmethod
    async def _wait_for_message(uuid):
        while True:
            response=ChatStorage.get_message(uuid)
            if response is None:
                await asyncio.sleep(0.2)
            else:
                return response
            
            
    @staticmethod
    async def async_get_message(uuid,timeout=20):
        try:
            result = await asyncio.wait_for(ChatStorage._wait_for_message(uuid), timeout)
            return result
        except asyncio.TimeoutError as e:
            raise e
    
    
    
async def my_coroutine():
    # 这里是你的异步操作，例如网络请求、文件读写等
    await asyncio.sleep(1)
    return "异步操作完成"

async def wait_for_result_with_timeout(coroutine, timeout):
    try:
        result = await asyncio.wait_for(coroutine, timeout)
        return result
    except asyncio.TimeoutError:
        return "操作超时"

async def main():
    result = await wait_for_result_with_timeout(my_coroutine(), 2)
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
