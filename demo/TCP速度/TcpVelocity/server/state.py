import json
import os
import threading
import time

from server.config import DATA_DIR


class SharedState:
    """
    轻量级的跨进程状态存储。

    场景：
    - HTTP 请求 `/api/set_tcp_velocity_r_index` 在主进程中调用 `set` 写入最新的 R 编号；
    - 机器人子进程在写寄存器前通过 `get` 读取编号；
    - 为避免频繁写磁盘，set 只更新内存 pending，后台线程定期 flush。

    设计要点：
    - get 每次都从磁盘读取，保证多进程读一致；
    - set 只允许同进程内多次调用，线程安全；
    - flush 采用“写临时文件再替换”保证原子性，防止重启后状态丢失。
    """

    _file_path = os.path.join(DATA_DIR, "state.json")
    _pending = {}
    _dirty = False
    _lock = threading.Lock()
    _flush_interval = 5
    _initialized = False

    @classmethod
    def _init(cls):
        """确保后台 flush 线程只启动一次。"""
        if cls._initialized:
            return
        cls._initialized = True

        t = threading.Thread(target=cls._flush_worker, daemon=True)
        t.start()

    @classmethod
    def _flush_worker(cls):
        """后台线程：定期将 pending 状态刷盘。"""
        while True:
            time.sleep(cls._flush_interval)
            cls._flush_to_file()

    @classmethod
    def _flush_to_file(cls):
        """
        将 pending 中的键值写入 JSON 文件。

        步骤：
        1. 读取现有文件（若存在）；
        2. 合并 pending；
        3. 以 `<file>.tmp` 临时文件写入新内容；
        4. os.replace 原子替换。
        """
        with cls._lock:
            if not cls._dirty:
                return

            data = {}
            if os.path.exists(cls._file_path):
                try:
                    with open(cls._file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except json.JSONDecodeError:
                    pass

            for k, v in cls._pending.items():
                data[k] = v

            cls._pending.clear()
            cls._dirty = False

        tmp = cls._file_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        os.replace(tmp, cls._file_path)

    @classmethod
    def set(cls, key: str, value):
        """写入状态（线程安全，本进程内部调用）。"""
        cls._init()
        with cls._lock:
            cls._pending[key] = value
            cls._dirty = True

    @classmethod
    def get(cls, key: str, default=None):
        """从磁盘读取状态（多进程安全，每次读最新）。"""
        cls._init()

        if not os.path.exists(cls._file_path):
            return default

        try:
            with open(cls._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return default

        return data.get(key, default)
