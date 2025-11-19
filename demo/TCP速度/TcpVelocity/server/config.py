"""
运行参数与目录配置。

该模块被 FastAPI 主进程、IPC 管理器以及机器人子进程共同引用，因此在此集中
维护各种配置信息。
"""

import os

from Agilebot import Extension

extension = Extension()

# ==========================
# 服务监听配置
# ==========================
HOST = "0.0.0.0"
"""FastAPI 监听地址。"""

PORT = int(os.getenv("PORT", 8000))
"""HTTP 服务对外端口，默认 8000，可通过环境变量 PORT 覆盖。"""

ROBOT_IP = extension.get_robot_ip() or "10.27.1.254"
"""机器人 IP"""

# ==========================
# 目录结构
# ==========================
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
"""TcpVelocity 工程根目录（包含 app、server 等子目录）。"""

ASSETS_DIR = os.path.join(ROOT_DIR, "assets")
"""前端静态资源目录，FastAPI 会将其挂载到 /assets。"""

DATA_DIR = os.path.join(ROOT_DIR, "data")
"""运行时数据目录（状态缓存、日志等都存放于此）。"""

LOG_DIR = os.path.join(DATA_DIR, "logs")
"""日志输出目录，server.logger 会在初始化时确保其存在。"""
