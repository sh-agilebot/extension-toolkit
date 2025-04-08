# 获取全局logger实例，只能在简单服务中使用
logger = globals().get('logger')
if logger is None:
    # 本地调试时，使用自带日志库
    import logging
    logger = logging.getLogger(__name__)

def add(a: int, b: int) -> int:
    """
    执行两个整数的加法运算

    参数：
    - a (int): 第一个加数
    - b (int): 第二个加数

    返回：
    - int: 返回加法结果
    """
    try:
        result = a + b
        return result

    except Exception as ex:
        logger.error(ex)
        return 0
