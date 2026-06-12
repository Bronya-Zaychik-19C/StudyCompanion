# -*- coding: utf-8 -*-
"""
StudyCompanion - 日程管理 Agent 工具
供 AI 调用的日程管理函数
"""

from datetime import datetime, timedelta
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ScheduleTools:
    """日程管理工具集"""
    
    def __init__(self, schedule_manager):
        """
        初始化工具集
        
        Args:
            schedule_manager: ScheduleManager 实例
        """
        self.manager = schedule_manager
        
        logger.info("🔧 日程工具集初始化完成")
    
    async def create_schedule_tool(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建日程工具（供 AI 调用）
        
        Parameters:
            title: 日程标题
            start_time: 开始时间（ISO格式字符串）
            duration_minutes: 持续时长
            category: 类别
            description: 描述
            reminder_minutes_before: 提前提醒时间
        
        Returns:
            执行结果
        """
        try:
            title = parameters.get('title')
            start_time_str = parameters.get('start_time')
            duration = parameters.get('duration_minutes', 60)
            
            if not title or not start_time_str:
                return {
                    'success': False,
                    'error': '缺少必要参数：title 或 start_time'
                }
            
            # 解析时间
            start_time = datetime.fromisoformat(start_time_str)
            
            # 创建日程
            schedule_id = await self.manager.create_schedule(
                title=title,
                start_time=start_time,
                duration_minutes=duration,
                category=parameters.get('category', 'study'),
                description=parameters.get('description', ''),
                reminder_minutes_before=parameters.get('reminder_minutes_before', 15),
                created_by_voice=True
            )
            
            return {
                'success': True,
                'schedule_id': schedule_id,
                'message': f"已创建日程：{title}",
                'details': {
                    'title': title,
                    'start_time': start_time.strftime('%Y-%m-%d %H:%M'),
                    'duration': f"{duration}分钟"
                }
            }
        
        except Exception as e:
            logger.error(f"💥 创建日程失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_today_schedule_tool(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """获取今日日程工具"""
        try:
            schedules = await self.manager.get_today_schedules()
            
            # 格式化输出
            schedule_list = []
            for s in schedules:
                start = datetime.fromisoformat(s['start_time'])
                schedule_list.append({
                    'id': s['id'],
                    'title': s['title'],
                    'start_time': start.strftime('%H:%M'),
                    'category': s['category'],
                    'status': s['status']
                })
            
            return {
                'success': True,
                'count': len(schedules),
                'schedules': schedule_list
            }
        
        except Exception as e:
            logger.error(f"💥 获取日程失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def complete_schedule_tool(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """完成日程工具"""
        try:
            schedule_id = parameters.get('schedule_id')
            
            if not schedule_id:
                return {
                    'success': False,
                    'error': '缺少参数：schedule_id'
                }
            
            await self.manager.complete_schedule(schedule_id)
            
            return {
                'success': True,
                'message': f"日程 {schedule_id} 已完成"
            }
        
        except Exception as e:
            logger.error(f"💥 完成日程失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_tool_definitions(self) -> list:
        """获取工具定义（供 LLM 使用）"""
        return [
            {
                'type': 'function',
                'function': {
                    'name': 'create_schedule',
                    'description': '创建新的日程安排。当用户表达要安排任务时使用。',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'title': {
                                'type': 'string',
                                'description': '日程标题，如"复习数学"'
                            },
                            'start_time': {
                                'type': 'string',
                                'description': '开始时间，ISO格式，如"2025-11-23T14:00:00"'
                            },
                            'duration_minutes': {
                                'type': 'integer',
                                'description': '持续时长（分钟），默认60'
                            },
                            'category': {
                                'type': 'string',
                                'enum': ['study', 'work', 'exercise', 'leisure', 'other'],
                                'description': '日程类别'
                            },
                            'description': {
                                'type': 'string',
                                'description': '详细描述'
                            },
                            'reminder_minutes_before': {
                                'type': 'integer',
                                'description': '提前多少分钟提醒，默认15'
                            }
                        },
                        'required': ['title', 'start_time']
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'get_today_schedule',
                    'description': '获取今天的所有日程安排',
                    'parameters': {
                        'type': 'object',
                        'properties': {}
                    }
                }
            },
            {
                'type': 'function',
                'function': {
                    'name': 'complete_schedule',
                    'description': '标记某个日程为已完成',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'schedule_id': {
                                'type': 'integer',
                                'description': '日程ID'
                            }
                        },
                        'required': ['schedule_id']
                    }
                }
            }
        ]


