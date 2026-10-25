"""单次同步（不进入定时循环）：Web 控制台手动同步、外部触发和本地测试使用

    python run_fetch_once.py [--source manual|energy|...] [--attempts 轮数]
"""
import argparse
import os
import sys
import logging

if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from const import load_project_env, get_data_dir
from error_watcher import ErrorWatcher

load_project_env()

ErrorWatcher.init(root_dir=os.path.join(get_data_dir(), "errors"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s] ---- %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
log_path = os.path.join(get_data_dir(), "app.log")
try:
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s  [%(levelname)-8s] ---- %(message)s", "%Y-%m-%d %H:%M:%S"))
    logging.getLogger().addHandler(fh)
except Exception:
    pass

from data_fetcher import DataFetcher
from fetch_runner import run_fetch

parser = argparse.ArgumentParser(description="单次同步国家电网数据")
parser.add_argument("--source", default="manual", help="来源，写入同步状态（manual / energy 等）")
parser.add_argument("--attempts", type=int, default=1, help="整轮最多尝试几轮（默认 1）")
args = parser.parse_args()

phone = os.getenv("PHONE_NUMBER")
password = os.getenv("PASSWORD")
logging.info(
    "开始单次同步, 来源=%s, 最多 %d 轮, 登录方式=%s, DB=%s",
    args.source, args.attempts, os.getenv("LOGIN_METHOD"), os.getenv("DB_TYPE"),
)
fetcher = DataFetcher(phone, password)
result = run_fetch(fetcher, source=args.source, attempts=max(1, args.attempts))
if result is None:
    logging.error("已有同步任务正在运行，请稍后再试")
    sys.exit(2)
logging.info("单次同步结束: %s", result)
sys.exit(0 if result != "failed" else 1)
