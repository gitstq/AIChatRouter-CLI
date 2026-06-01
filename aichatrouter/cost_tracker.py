"""
成本追踪与分析模块 - 跟踪 API 使用量和费用。

核心功能:
    - 按模型/供应商跟踪 Token 使用量
    - 基于供应商定价计算费用
    - 日/周/月消费报告
    - 预算预警
    - 导出使用数据（JSON/CSV）
    - 使用历史持久化
"""

import csv
import io
import os
import time
from typing import Any, Dict, List, Optional

from aichatrouter.utils import (
    format_timestamp,
    get_data_dir,
    ensure_directory,
    read_json,
    write_json,
    dict_to_csv,
)


# =============================================================================
# 使用记录
# =============================================================================

class UsageRecord:
    """单次 API 使用记录。

    Attributes:
        timestamp: 使用时间戳。
        provider: 供应商名称。
        model: 模型名称。
        input_tokens: 输入 Token 数。
        output_tokens: 输出 Token 数。
        total_tokens: 总 Token 数。
        cost: 估算成本。
        duration: 请求耗时（秒）。
        task_type: 任务类型。
        session_id: 会话 ID。
    """

    def __init__(
        self,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        duration: float = 0.0,
        task_type: str = "",
        session_id: str = "",
        timestamp: Optional[float] = None,
    ) -> None:
        """初始化使用记录。

        Args:
            provider: 供应商名称。
            model: 模型名称。
            input_tokens: 输入 Token 数。
            output_tokens: 输出 Token 数。
            cost: 估算成本。
            duration: 请求耗时。
            task_type: 任务类型。
            session_id: 会话 ID。
            timestamp: 时间戳。
        """
        self.timestamp = timestamp or time.time()
        self.provider = provider
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = input_tokens + output_tokens
        self.cost = cost
        self.duration = duration
        self.task_type = task_type
        self.session_id = session_id

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典。"""
        return {
            "timestamp": self.timestamp,
            "provider": self.provider,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "duration": self.duration,
            "task_type": self.task_type,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UsageRecord":
        """从字典反序列化。"""
        return cls(
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            cost=data.get("cost", 0.0),
            duration=data.get("duration", 0.0),
            task_type=data.get("task_type", ""),
            session_id=data.get("session_id", ""),
            timestamp=data.get("timestamp"),
        )

    def __repr__(self) -> str:
        return (
            f"UsageRecord(provider={self.provider!r}, model={self.model!r}, "
            f"cost=${self.cost:.4f}, tokens={self.total_tokens})"
        )


# =============================================================================
# 成本追踪器
# =============================================================================

class CostTracker:
    """API 使用成本追踪器。

    跟踪所有 API 请求的使用量和费用，支持预算管理和报告生成。

    Attributes:
        records: 使用记录列表。
        daily_budget: 每日预算。
        weekly_budget: 每周预算。
        monthly_budget: 每月预算。
        alert_threshold: 预算预警阈值 (0-1)。
        currency: 货币单位。

    Examples:
        >>> tracker = CostTracker()
        >>> tracker.record_usage("openai", "gpt-4o", 100, 200, 0.005)
        >>> report = tracker.get_daily_report()
        >>> print(f"今日花费: ${report['total_cost']:.4f}")
    """

    def __init__(
        self,
        daily_budget: float = 10.0,
        weekly_budget: float = 50.0,
        monthly_budget: float = 200.0,
        alert_threshold: float = 0.8,
        currency: str = "USD",
        persistence_file: str = "",
    ) -> None:
        """初始化成本追踪器。

        Args:
            daily_budget: 每日预算。
            weekly_budget: 每周预算。
            monthly_budget: 每月预算。
            alert_threshold: 预算预警阈值。
            currency: 货币单位。
            persistence_file: 持久化文件路径。
        """
        self.records: List[UsageRecord] = []
        self.daily_budget = daily_budget
        self.weekly_budget = weekly_budget
        self.monthly_budget = monthly_budget
        self.alert_threshold = alert_threshold
        self.currency = currency

        if persistence_file:
            self.persistence_file = persistence_file
        else:
            data_dir = get_data_dir()
            self.persistence_file = os.path.join(data_dir, "cost_history.json")

        # 预算预警回调
        self._alert_callbacks: List = []

        # 启动时加载历史数据
        self.load()

    # -------------------------------------------------------------------------
    # 记录使用
    # -------------------------------------------------------------------------

    def record_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float = 0.0,
        duration: float = 0.0,
        task_type: str = "",
        session_id: str = "",
    ) -> UsageRecord:
        """记录一次 API 使用。

        Args:
            provider: 供应商名称。
            model: 模型名称。
            input_tokens: 输入 Token 数。
            output_tokens: 输出 Token 数。
            cost: 估算成本。
            duration: 请求耗时。
            task_type: 任务类型。
            session_id: 会话 ID。

        Returns:
            创建的使用记录。
        """
        record = UsageRecord(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            duration=duration,
            task_type=task_type,
            session_id=session_id,
        )
        self.records.append(record)

        # 检查预算预警
        self._check_budget_alerts()

        return record

    def record_from_response(
        self,
        response: Dict[str, Any],
        task_type: str = "",
        session_id: str = "",
    ) -> UsageRecord:
        """从 API 响应中记录使用。

        Args:
            response: API 响应字典。
            task_type: 任务类型。
            session_id: 会话 ID。

        Returns:
            创建的使用记录。
        """
        usage = response.get("usage", {})
        return self.record_usage(
            provider=response.get("provider", ""),
            model=response.get("model", ""),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            cost=response.get("cost", 0.0),
            duration=response.get("duration", 0.0),
            task_type=task_type,
            session_id=session_id,
        )

    # -------------------------------------------------------------------------
    # 统计查询
    # -------------------------------------------------------------------------

    def get_total_cost(self) -> float:
        """获取总花费。"""
        return sum(r.cost for r in self.records)

    def get_total_tokens(self) -> Dict[str, int]:
        """获取总 Token 使用量。"""
        return {
            "input": sum(r.input_tokens for r in self.records),
            "output": sum(r.output_tokens for r in self.records),
            "total": sum(r.total_tokens for r in self.records),
        }

    def get_request_count(self) -> int:
        """获取总请求数。"""
        return len(self.records)

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取按供应商分组的统计。

        Returns:
            供应商名称到统计信息的映射。
        """
        stats: Dict[str, Dict[str, Any]] = {}
        for record in self.records:
            if record.provider not in stats:
                stats[record.provider] = {
                    "requests": 0,
                    "total_cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "models": set(),
                }
            s = stats[record.provider]
            s["requests"] += 1
            s["total_cost"] += record.cost
            s["input_tokens"] += record.input_tokens
            s["output_tokens"] += record.output_tokens
            s["total_tokens"] += record.total_tokens
            s["models"].add(record.model)

        # 将 set 转换为 list（JSON 序列化）
        for s in stats.values():
            s["models"] = sorted(s["models"])

        return stats

    def get_model_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取按模型分组的统计。

        Returns:
            模型引用（provider/model）到统计信息的映射。
        """
        stats: Dict[str, Dict[str, Any]] = {}
        for record in self.records:
            key = f"{record.provider}/{record.model}"
            if key not in stats:
                stats[key] = {
                    "provider": record.provider,
                    "model": record.model,
                    "requests": 0,
                    "total_cost": 0.0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "avg_cost_per_request": 0.0,
                }
            s = stats[key]
            s["requests"] += 1
            s["total_cost"] += record.cost
            s["input_tokens"] += record.input_tokens
            s["output_tokens"] += record.output_tokens
            s["total_tokens"] += record.total_tokens

        # 计算平均成本
        for s in stats.values():
            if s["requests"] > 0:
                s["avg_cost_per_request"] = s["total_cost"] / s["requests"]

        return stats

    def get_task_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取按任务类型分组的统计。"""
        stats: Dict[str, Dict[str, Any]] = {}
        for record in self.records:
            task = record.task_type or "unknown"
            if task not in stats:
                stats[task] = {
                    "requests": 0,
                    "total_cost": 0.0,
                    "total_tokens": 0,
                }
            stats[task]["requests"] += 1
            stats[task]["total_cost"] += record.cost
            stats[task]["total_tokens"] += record.total_tokens

        return stats

    # -------------------------------------------------------------------------
    # 时间范围报告
    # -------------------------------------------------------------------------

    def _filter_by_time_range(
        self, start_time: float, end_time: float
    ) -> List[UsageRecord]:
        """按时间范围过滤记录。"""
        return [
            r for r in self.records
            if start_time <= r.timestamp <= end_time
        ]

    def get_daily_report(self, date: Optional[float] = None) -> Dict[str, Any]:
        """获取每日报告。

        Args:
            date: Unix 时间戳（默认为今天）。

        Returns:
            每日报告字典。
        """
        if date is None:
            date = time.time()

        # 计算当天起始和结束时间
        local_time = time.localtime(date)
        day_start = time.mktime((
            local_time.tm_year, local_time.tm_mon, local_time.tm_mday,
            0, 0, 0, local_time.tm_wday, local_time.tm_yday, -1
        ))
        day_end = day_start + 86400  # 24 小时

        records = self._filter_by_time_range(day_start, day_end)

        return self._build_report(records, "daily", format_timestamp(day_start, "%Y-%m-%d"))

    def get_weekly_report(self, date: Optional[float] = None) -> Dict[str, Any]:
        """获取每周报告。

        Args:
            date: Unix 时间戳（默认为本周）。

        Returns:
            每周报告字典。
        """
        if date is None:
            date = time.time()

        local_time = time.localtime(date)
        # 计算本周一的起始时间
        days_since_monday = local_time.tm_wday
        if days_since_monday == 6:  # 周日
            days_since_monday = 0
        monday = local_time.tm_mday - days_since_monday
        week_start = time.mktime((
            local_time.tm_year, local_time.tm_mon, monday,
            0, 0, 0, 0, local_time.tm_yday - days_since_monday, -1
        ))
        week_end = week_start + 7 * 86400

        records = self._filter_by_time_range(week_start, week_end)

        return self._build_report(
            records, "weekly",
            f"{format_timestamp(week_start, '%Y-%m-%d')} ~ {format_timestamp(week_end - 1, '%Y-%m-%d')}"
        )

    def get_monthly_report(self, date: Optional[float] = None) -> Dict[str, Any]:
        """获取每月报告。

        Args:
            date: Unix 时间戳（默认为本月）。

        Returns:
            每月报告字典。
        """
        if date is None:
            date = time.time()

        local_time = time.localtime(date)
        month_start = time.mktime((
            local_time.tm_year, local_time.tm_mon, 1,
            0, 0, 0, 0, 1, -1
        ))

        # 计算下个月第一天
        if local_time.tm_mon == 12:
            next_month_start = time.mktime((
                local_time.tm_year + 1, 1, 1,
                0, 0, 0, 0, 1, -1
            ))
        else:
            next_month_start = time.mktime((
                local_time.tm_year, local_time.tm_mon + 1, 1,
                0, 0, 0, 0, 1, -1
            ))

        records = self._filter_by_time_range(month_start, next_month_start)

        return self._build_report(records, "monthly", format_timestamp(month_start, "%Y-%m"))

    def _build_report(
        self,
        records: List[UsageRecord],
        period: str,
        period_label: str,
    ) -> Dict[str, Any]:
        """构建报告。"""
        total_cost = sum(r.cost for r in records)
        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)
        total_tokens = total_input + total_output
        request_count = len(records)

        # 按模型分组
        model_breakdown: Dict[str, Dict[str, Any]] = {}
        for r in records:
            key = f"{r.provider}/{r.model}"
            if key not in model_breakdown:
                model_breakdown[key] = {
                    "requests": 0,
                    "cost": 0.0,
                    "tokens": 0,
                }
            model_breakdown[key]["requests"] += 1
            model_breakdown[key]["cost"] += r.cost
            model_breakdown[key]["tokens"] += r.total_tokens

        # 按任务类型分组
        task_breakdown: Dict[str, Dict[str, Any]] = {}
        for r in records:
            task = r.task_type or "unknown"
            if task not in task_breakdown:
                task_breakdown[task] = {"requests": 0, "cost": 0.0}
            task_breakdown[task]["requests"] += 1
            task_breakdown[task]["cost"] += r.cost

        return {
            "period": period,
            "period_label": period_label,
            "total_cost": total_cost,
            "currency": self.currency,
            "total_tokens": total_tokens,
            "input_tokens": total_input,
            "output_tokens": total_output,
            "request_count": request_count,
            "avg_cost_per_request": total_cost / request_count if request_count > 0 else 0.0,
            "model_breakdown": model_breakdown,
            "task_breakdown": task_breakdown,
        }

    # -------------------------------------------------------------------------
    # 预算管理
    # -------------------------------------------------------------------------

    def check_budget(self) -> Dict[str, Any]:
        """检查当前预算使用情况。

        Returns:
            预算状态字典，包含日/周/月的预算使用情况。
        """
        daily_report = self.get_daily_report()
        weekly_report = self.get_weekly_report()
        monthly_report = self.get_monthly_report()

        return {
            "daily": {
                "spent": daily_report["total_cost"],
                "budget": self.daily_budget,
                "usage": daily_report["total_cost"] / self.daily_budget if self.daily_budget > 0 else 0,
                "remaining": max(0, self.daily_budget - daily_report["total_cost"]),
                "alert": (
                    daily_report["total_cost"] / self.daily_budget >= self.alert_threshold
                    if self.daily_budget > 0
                    else False
                ),
            },
            "weekly": {
                "spent": weekly_report["total_cost"],
                "budget": self.weekly_budget,
                "usage": weekly_report["total_cost"] / self.weekly_budget if self.weekly_budget > 0 else 0,
                "remaining": max(0, self.weekly_budget - weekly_report["total_cost"]),
                "alert": (
                    weekly_report["total_cost"] / self.weekly_budget >= self.alert_threshold
                    if self.weekly_budget > 0
                    else False
                ),
            },
            "monthly": {
                "spent": monthly_report["total_cost"],
                "budget": self.monthly_budget,
                "usage": monthly_report["total_cost"] / self.monthly_budget if self.monthly_budget > 0 else 0,
                "remaining": max(0, self.monthly_budget - monthly_report["total_cost"]),
                "alert": (
                    monthly_report["total_cost"] / self.monthly_budget >= self.alert_threshold
                    if self.monthly_budget > 0
                    else False
                ),
            },
        }

    def _check_budget_alerts(self) -> None:
        """检查并触发预算预警。"""
        budget_status = self.check_budget()

        alerts: List[str] = []
        for period, status in budget_status.items():
            if status["alert"]:
                alerts.append(
                    f"{period} 预算预警: 已使用 ${status['spent']:.4f} / "
                    f"${status['budget']:.2f} ({status['usage']:.1%})"
                )

        for alert_msg in alerts:
            for callback in self._alert_callbacks:
                try:
                    callback(alert_msg)
                except Exception:
                    pass

    def add_alert_callback(self, callback: Any) -> None:
        """添加预算预警回调函数。

        Args:
            callback: 回调函数，接收预警消息字符串。
        """
        self._alert_callbacks.append(callback)

    def is_over_budget(self, period: str = "daily") -> bool:
        """检查是否超出预算。

        Args:
            period: 预算周期（daily/weekly/monthly）。

        Returns:
            是否超出预算。
        """
        budget_status = self.check_budget()
        if period in budget_status:
            return budget_status[period]["usage"] >= 1.0
        return False

    # -------------------------------------------------------------------------
    # 导出
    # -------------------------------------------------------------------------

    def export_json(self, filepath: str = "") -> str:
        """导出使用数据为 JSON 格式。

        Args:
            filepath: 导出文件路径。

        Returns:
            导出文件路径。
        """
        if not filepath:
            filepath = os.path.join(get_data_dir(), "exports", "usage_export.json")

        data = {
            "export_time": format_timestamp(),
            "total_records": len(self.records),
            "total_cost": self.get_total_cost(),
            "total_tokens": self.get_total_tokens(),
            "records": [r.to_dict() for r in self.records],
        }

        write_json(filepath, data)
        return filepath

    def export_csv(self, filepath: str = "") -> str:
        """导出使用数据为 CSV 格式。

        Args:
            filepath: 导出文件路径。

        Returns:
            导出文件路径。
        """
        if not filepath:
            filepath = os.path.join(get_data_dir(), "exports", "usage_export.csv")

        ensure_directory(os.path.dirname(filepath) or ".")

        rows = []
        for r in self.records:
            rows.append({
                "timestamp": format_timestamp(r.timestamp),
                "provider": r.provider,
                "model": r.model,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "cost": f"{r.cost:.6f}",
                "duration": f"{r.duration:.2f}",
                "task_type": r.task_type,
                "session_id": r.session_id,
            })

        csv_content = dict_to_csv(rows)
        with open(filepath, "w", encoding="utf-8", newline="") as f:
            f.write(csv_content)

        return filepath

    # -------------------------------------------------------------------------
    # 持久化
    # -------------------------------------------------------------------------

    def save(self, filepath: Optional[str] = None) -> str:
        """保存使用记录到 JSON 文件。

        Args:
            filepath: 文件路径。

        Returns:
            保存的文件路径。
        """
        filepath = filepath or self.persistence_file
        data = {
            "records": [r.to_dict() for r in self.records],
            "saved_at": format_timestamp(),
        }
        write_json(filepath, data)
        return filepath

    def load(self, filepath: Optional[str] = None) -> int:
        """从 JSON 文件加载使用记录。

        Args:
            filepath: 文件路径。

        Returns:
            加载的记录数量。
        """
        filepath = filepath or self.persistence_file
        data = read_json(filepath)
        if not data:
            return 0

        records_data = data.get("records", [])
        self.records = [UsageRecord.from_dict(r) for r in records_data]
        return len(self.records)

    def clear_history(self, before_timestamp: Optional[float] = None) -> int:
        """清除使用记录。

        Args:
            before_timestamp: 清除此时间之前的记录（None 则清除全部）。

        Returns:
            清除的记录数量。
        """
        if before_timestamp is None:
            count = len(self.records)
            self.records.clear()
            return count

        original_count = len(self.records)
        self.records = [r for r in self.records if r.timestamp >= before_timestamp]
        return original_count - len(self.records)

    # -------------------------------------------------------------------------
    # 综合摘要
    # -------------------------------------------------------------------------

    def get_summary(self) -> str:
        """获取人类可读的使用摘要。

        Returns:
            格式化的使用摘要字符串。
        """
        budget = self.check_budget()
        total = self.get_total_cost()
        tokens = self.get_total_tokens()
        requests = self.get_request_count()

        lines = [
            f"=== AIChatRouter 成本报告 ===",
            f"",
            f"总请求数: {requests}",
            f"总 Token: {tokens['total']:,} (输入: {tokens['input']:,}, 输出: {tokens['output']:,})",
            f"总花费: ${total:.4f}",
            f"",
            f"--- 预算状态 ---",
            f"今日: ${budget['daily']['spent']:.4f} / ${budget['daily']['budget']:.2f} ({budget['daily']['usage']:.1%})",
            f"本周: ${budget['weekly']['spent']:.4f} / ${budget['weekly']['budget']:.2f} ({budget['weekly']['usage']:.1%})",
            f"本月: ${budget['monthly']['spent']:.4f} / ${budget['monthly']['budget']:.2f} ({budget['monthly']['usage']:.1%})",
        ]

        # 预算预警
        for period in ["daily", "weekly", "monthly"]:
            if budget[period]["alert"]:
                lines.append(f"[!] {period} 预算即将超限!")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"CostTracker(records={len(self.records)}, "
            f"total_cost=${self.get_total_cost():.4f})"
        )
