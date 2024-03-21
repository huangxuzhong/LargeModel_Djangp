from datetime import datetime, timedelta  
def is_current_time_within_range(start_time_str, end_time_str):  
    try:
        # 转换时间字符串为 datetime 对象  
        start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')  
        end_time = datetime.strptime(end_time_str, '%Y-%m-%d %H:%M')  
        # 获取当前时间  
        current_time = datetime.now()  
        # 确保开始时间在结束时间之前  
        if start_time > end_time:  
            start_time, end_time = end_time, start_time  
        # 检查当前时间是否在范围内  
        return start_time <= current_time <= end_time
    except Exception as e:
        print(str(e))
        return False