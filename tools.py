import math

def caculator(express: str) -> str:
    """计算数学表达式"""
    result = eval(express)
    return str(result)

def get_current_time() -> str:
    """获取当前时间"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
