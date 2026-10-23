"""一次完整的同步（含整轮重试），定时任务、Web 控制台手动同步和外部触发（如 energy）共用。

整轮重试与登录重试是两层：
  - 登录重试：DataFetcher 内部，每轮最多 RETRY_TIMES_LIMIT 次点击登录
  - 整轮重试：本模块，登录失败 / 取不到户号 / 所有户号都失败时，等待 FETCH_RUN_RETRY_WAIT_MINUTES 分钟后整轮再来，
    最多 attempts 轮。每轮都会重新登录，轮数不宜多，避免频繁登录触发风控
部分户号失败（其余成功）不再整轮重试，结果记为 partial，失败的户号写入 detail。
"""

import logging
import os
import time
from typing import Optional, Tuple

from fetch_lock import fetch_lock, mark_fetch_finished, update_fetch_progress


def run_attempts_default() -> int:
    try:
        return max(1, int(os.getenv("FETCH_RUN_ATTEMPTS", "2")))
    except ValueError:
        return 2


def retry_wait_seconds() -> int:
    try:
        return max(0, int(float(os.getenv("FETCH_RUN_RETRY_WAIT_MINUTES", "10")) * 60))
    except ValueError:
        return 600


def classify(summary: Optional[dict]) -> Tuple[str, str]:
    """本轮结果 → (success / partial / failed, 说明)"""
    if not summary:
        return "failed", "同步异常结束"
    if not summary.get("login"):
        return "failed", summary.get("error") or "登录失败"
    ok, failed = summary.get("ok") or [], summary.get("failed") or []
    if summary.get("error") and not ok:
        return "failed", summary["error"]
    if ok and not failed:
        return "success", f"同步完成：{len(ok)} 户"
    if ok:
        return "partial", f"部分完成：成功 {len(ok)} 户，失败 {len(failed)} 户（{', '.join(failed)}）"
    return "failed", f"所有户号都获取失败（{', '.join(failed)}）" if failed else "没有可同步的户号"


def run_fetch(fetcher, source: str, attempts: Optional[int] = None) -> Optional[str]:
    """
    在同步锁内执行，最多 attempts 轮。返回最终结果 success / partial / failed；
    已有同步在运行（拿不到锁）时返回 None，不做任何事。
    """
    attempts = attempts or run_attempts_default()
    with fetch_lock(source=source, block=False) as acquired:
        if not acquired:
            logging.warning("跳过同步（来源 %s）：已有同步任务正在运行", source)
            return None
        result, message, summary = "failed", "", None
        for attempt in range(1, attempts + 1):
            update_fetch_progress(f"正在同步国家电网数据（第 {attempt}/{attempts} 轮）...", attempt=attempt, attempts=attempts)
            try:
                summary = fetcher.fetch()
            except Exception as exc:
                logging.exception("第 %d/%d 轮同步异常: %s", attempt, attempts, exc)
                summary = {"login": False, "error": f"同步异常: {exc}", "ok": [], "failed": [], "skipped": []}
            result, message = classify(summary)
            logging.info("第 %d/%d 轮同步结果: %s，%s", attempt, attempts, result, message)
            if result != "failed" or attempt == attempts:
                break
            wait = retry_wait_seconds()
            update_fetch_progress(f"第 {attempt}/{attempts} 轮失败（{message}），{wait // 60} 分钟后重试",
                                  attempt=attempt, attempts=attempts)
            time.sleep(wait)
        if result == "failed" and attempts > 1:
            message = f"{message}（共尝试 {attempts} 轮）"
        mark_fetch_finished(result != "failed", message, result=result, detail=summary)
        return result
