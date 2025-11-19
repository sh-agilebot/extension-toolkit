import requests

from Agilebot import Extension, StatusCodeEnum

# 获取全局logger实例，只能在简单服务中使用
logger = globals().get("logger")
if logger is None:
    # 本地调试时，使用自带日志库
    import logging

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


ROBOT_IP = "10.27.1.254"
"""机器人IP"""


def tcp_velocity(r_index: int):
    """
    设置TCP速度写入R寄存器的索引

    本函数调用 TcpVelocity 插件，通过其 HTTP 接口 `/api/set_tcp_velocity_r_index` 设置需要保存的 R 寄存器。

    示例（在用户程序中）:
        CALL_SERVICE RunningStatus, tcp_velocity, r_index=5

    示例（本地调试）:
        python RunningStatus.py

    注意:
        调用前必须确保 TcpVelocity 插件已加载并处于运行状态。

    :param r_index: 需要写入的 R 寄存器索引
    """
    extension = Extension(ROBOT_IP)

    res, ret = extension.get("TcpVelocity")
    if ret != StatusCodeEnum.OK:
        raise Exception("获取TcpVelocity插件失败")
    if not res.state.isRunning:
        raise Exception("TcpVelocity插件未运行")
    api_url = f"http://{ROBOT_IP}:{res.state.port}/api/set_tcp_velocity_r_index"
    requests.post(api_url, json={"index": r_index}).json()


if __name__ == "__main__":
    # 本地调试：可直接运行该脚本
    # 用户程序：使用 CALL_SERVICE 指令调用
    tcp_velocity(2)
