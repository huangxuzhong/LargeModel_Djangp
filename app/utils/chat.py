import asyncio

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
