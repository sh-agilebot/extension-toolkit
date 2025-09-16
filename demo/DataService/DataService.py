from pathlib import Path
import sqlite3

# 获取全局logger实例，只能在简单服务中使用
logger = globals().get('logger')
if logger is None:
    # 本地调试时，使用自带日志库
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


def __init_db():
    """
    初始化数据库
    """
    try:
        current_dir = Path(__file__).parent.resolve()
        data_dir = current_dir / 'data'

        # 如果data目录不存在，手动创建
        if not data_dir.exists():
            data_dir.mkdir(parents=True)
        db_path = data_dir / 'data.db'

        # 连接到数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        logger.info("数据库打开成功")

        # 创建表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS `robot_config` (
                `id`            INTEGER PRIMARY KEY AUTOINCREMENT,
                `key`           VARCHAR(255)    NOT NULL UNIQUE,
                `value`         TEXT     NOT NULL
            );
        ''')
        logger.info("表创建成功")
        conn.commit()

        return conn
    except Exception as e:
        logger.error(f"初始化数据库失败: {e}")
        return None


conn = __init_db()
"""
全局变量，用于持有唯一的数据库连接实例
"""


def get_robot_config(key: str):
    """根据 key 获取配置值。"""
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM robot_config WHERE key = ?', (key,))
        result = cursor.fetchone()
        return result[0] if result else None
    except sqlite3.Error as e:
        logger.error(f"获取配置 '{key}' 失败: {e}")
        return None


def set_robot_config(key: str, value: str):
    """设置或更新一个配置项。"""
    try:
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO robot_config (key, value) VALUES (?, ?)', (key, str(value)))
        conn.commit()
        logger.info(f"配置 '{key}' 已设置为 '{value}'。")
        return True
    except sqlite3.Error as e:
        logger.error(f"设置配置 '{key}' 失败: {e}")
        return False

def delete_robot_config(key: str):
    """根据 key 删除一个配置项。"""
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM robot_config WHERE key = ?', (key,))
        conn.commit()
        logger.info(f"配置 '{key}' 已删除。")
        return True
    except sqlite3.Error as e:
        logger.error(f"删除配置 '{key}' 失败: {e}")
        return False
