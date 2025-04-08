from Agilebot.IR.A.arm import Arm
from Agilebot.IR.A.status_code import StatusCodeEnum
from Agilebot.IR.A.sdk_classes import Register

# 获取全局logger实例，只能在简单服务中使用
logger = globals().get('logger')
if logger is None:
    # 本地调试时，使用自带日志库
    import logging
    logger = logging.getLogger(__name__)


arm = Arm(dev_mode=True)
ret = arm.connect("10.27.1.254")
if ret != StatusCodeEnum.OK:
    logger.error("连接失败")


def add(a: int, b: int) -> int:
    """
    执行两个整数的加法运算，并写入寄存器

    参数：
    - a (int): 第一个加数
    - b (int): 第二个加数

    返回：
    - int: 返回加法结果
    """
    try:
        result = a + b
        # 将结果写入寄存器
        register = Register()
        register.id = 1
        register.name = "math_result"
        register.comment = "加法服务的结果"
        register.value = result

        ret = arm.register.write(1, register)
        if ret != StatusCodeEnum.OK:
            logger.error("更新R失败")


        return result

    except Exception as ex:
        logger.error(ex)
        return 0
