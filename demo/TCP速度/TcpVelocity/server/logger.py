"""
统一的日志配置。

FastAPI 主进程、IPC 工具和机器人子进程会共同引用该 logger；这里负责：
1. 确保 `data/logs` 目录存在；
2. 将日志同时写入控制台与 `app.log`，方便在插件管理后台排查；
3. 设置统一的格式，便于快速定位来自不同模块的日志。
"""

import os
import logging

from server.config import LOG_DIR

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(LOG_DIR, "app.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)
