# -*- coding: utf-8 -*-
"""
StudyCompanion - 日程管理器
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ScheduleManager:
    """日程管理器"""

    def __init__(self, database):
        """
        初始化日程管理器

        Args:
            database: DatabaseManager 实例
        """
        self.database = database
        logger.info("📅 日程管理器初始化完成")

    async def create_schedule(
        self,
        title: str,
        start_time: datetime,
        duration_minutes: int = 120,
        category: str = 'study',
        description: str = ''
    ) -> int:
        """
        创建日程

        Args:
            title: 日程标题
            start_time: 开始时间
            duration_minutes: 持续时长（分钟）
            category: 类别
            description: 描述

        Returns:
            日程 ID
        """
        end_time = start_time + timedelta(minutes=duration_minutes)
        reminder_time = start_time - timedelta(minutes=15)  # 提前 15 分钟提醒

        schedule_id = await self.database.create_schedule(
            title=title,
            start_time=start_time,
            end_time=end_time,
            reminder_time=reminder_time,
            description=description,
            category=category
        )

        logger.info(f"✅ 创建日程：{title} (ID: {schedule_id})")
        return schedule_id

    async def get_today_schedules(self) -> List[Dict[str, Any]]:
        """获取今日日程"""
        schedules = await self.database.get_today_schedules()
        logger.debug(f"📋 今日日程数量：{len(schedules)}")
        return schedules

    async def complete_schedule(self, schedule_id: int):
        """标记日程为已完成"""
        await self.database.update_schedule_status(schedule_id, 'completed')
        logger.info(f"✅ 日程已完成：ID {schedule_id}")

    async def cancel_schedule(self, schedule_id: int):
        """取消日程"""
        await self.database.update_schedule_status(schedule_id, 'cancelled')
        logger.info(f"❌ 日程已取消：ID {schedule_id}")

    async def generate_summary(self) -> str:
        """生成今日日程摘要"""
        schedules = await self.get_today_schedules()

        if not schedules:
            return "今天还没有安排日程哦~"

        pending = [s for s in schedules if s['status'] == 'pending']
        completed = [s for s in schedules if s['status'] == 'completed']

        summary = f"📊 今日日程摘要\n\n"
        summary += f"总计：{len(schedules)} 项\n"
        summary += f"已完成：{len(completed)} 项\n"
        summary += f"待完成：{len(pending)} 项\n\n"

        if pending:
            summary += "📝 待完成:\n"
            for s in pending[:5]:
                start = datetime.fromisoformat(s['start_time'])
                summary += f"  • {start.strftime('%H:%M')} - {s['title']}\n"

        return summary
