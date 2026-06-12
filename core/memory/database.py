# -*- coding: utf-8 -*-
"""
StudyCompanion - 数据库管理模块
负责 SQLite 数据库的创建、连接和基础操作
"""

import aiosqlite
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器"""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init_database(self):
        """初始化数据库表结构"""
        async with aiosqlite.connect(self.db_path) as db:
            # 会话列表
            await db.execute('''
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT DEFAULT '新对话',
                    subject TEXT DEFAULT 'math_one',
                    persona TEXT DEFAULT 'mentor',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 会话消息
            await db.execute('''
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    msg_type TEXT DEFAULT 'text',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
                )
            ''')

            # 消息索引
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON chat_messages(session_id, created_at)
            ''')

            # 对话历史表
            await db.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    emotion TEXT,
                    importance_score REAL DEFAULT 0.5
                )
            ''')

            # 日程表
            await db.execute('''
                CREATE TABLE IF NOT EXISTS schedules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    reminder_time DATETIME,
                    status TEXT DEFAULT 'pending',
                    category TEXT DEFAULT 'study',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME
                )
            ''')

            # 学习记录表
            await db.execute('''
                CREATE TABLE IF NOT EXISTS study_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    duration_minutes INTEGER,
                    quality_score INTEGER CHECK(quality_score BETWEEN 1 AND 10),
                    notes TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 索引
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_conversations_timestamp
                ON conversations(timestamp DESC)
            ''')

            await db.commit()
            logger.info(f"✅ 数据库初始化完成：{self.db_path}")

    # ========== 对话管理 ==========

    async def add_conversation(
        self,
        role: str,
        content: str,
        emotion: Optional[str] = None
    ) -> int:
        """添加对话记录"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                '''INSERT INTO conversations (role, content, emotion)
                   VALUES (?, ?, ?)''',
                (role, content, emotion)
            )
            await db.commit()
            return cursor.lastrowid

    async def get_recent_conversations(
        self,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """获取最近的对话"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                '''SELECT * FROM conversations
                   ORDER BY timestamp DESC LIMIT ?''',
                (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    # ========== 日程管理 ==========

    async def create_schedule(
        self,
        title: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        **kwargs
    ) -> int:
        """创建日程"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                '''INSERT INTO schedules
                   (title, description, start_time, end_time, reminder_time, category)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (
                    title,
                    kwargs.get('description', ''),
                    start_time,
                    end_time,
                    kwargs.get('reminder_time'),
                    kwargs.get('category', 'study')
                )
            )
            await db.commit()
            logger.info(f"✅ 创建日程：{title}")
            return cursor.lastrowid

    async def get_today_schedules(self) -> List[Dict[str, Any]]:
        """获取今日日程"""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                '''SELECT * FROM schedules
                   WHERE start_time BETWEEN ? AND ?
                   ORDER BY start_time''',
                (today_start, today_end)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_schedule_status(self, schedule_id: int, status: str):
        """更新日程状态"""
        async with aiosqlite.connect(self.db_path) as db:
            completed_at = datetime.now() if status == 'completed' else None
            await db.execute(
                '''UPDATE schedules
                   SET status = ?, completed_at = ?
                   WHERE id = ?''',
                (status, completed_at, schedule_id)
            )
            await db.commit()

    # ========== 学习记录 ==========

    async def log_study_session(
        self,
        subject: str,
        duration_minutes: int,
        quality_score: int = 7,
        notes: str = ""
    ) -> int:
        """记录学习会话"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                '''INSERT INTO study_logs
                   (subject, duration_minutes, quality_score, notes)
                   VALUES (?, ?, ?, ?)''',
                (subject, duration_minutes, quality_score, notes)
            )
            await db.commit()
            logger.info(f"✅ 记录学习：{subject} {duration_minutes}分钟")
            return cursor.lastrowid

    async def get_study_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取学习统计"""
        from_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        from_date = from_date.replace(day=from_date.day - days)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                '''SELECT SUM(duration_minutes) as total_minutes,
                          AVG(quality_score) as avg_quality,
                          COUNT(*) as session_count
                   FROM study_logs
                   WHERE timestamp >= ?''',
                (from_date,)
            ) as cursor:
                row = await cursor.fetchone()

                return {
                    'total_minutes': row[0] or 0,
                    'avg_quality': round(row[1], 1) if row[1] else 0,
                    'session_count': row[2] or 0
                }

    # ========== 会话管理 ==========

    async def create_session(self, sid: str, title: str = "新对话",
                              subject: str = "math_one", persona: str = "mentor") -> str:
        """创建新会话"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''INSERT OR REPLACE INTO chat_sessions (id, title, subject, persona, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                (sid, title, subject, persona)
            )
            await db.commit()
            return sid

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """获取所有会话列表"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                '''SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT 50'''
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def get_session(self, sid: str) -> Optional[Dict]:
        """获取单个会话"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                'SELECT * FROM chat_sessions WHERE id = ?', (sid,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_session_title(self, sid: str, title: str):
        """更新会话标题"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (title, sid)
            )
            await db.commit()

    async def delete_session(self, sid: str):
        """删除会话及其消息"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('DELETE FROM chat_messages WHERE session_id = ?', (sid,))
            await db.execute('DELETE FROM chat_sessions WHERE id = ?', (sid,))
            await db.commit()

    async def save_message(self, sid: str, role: str, content: str,
                            msg_type: str = "text"):
        """保存一条消息"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                '''INSERT INTO chat_messages (session_id, role, content, msg_type)
                   VALUES (?, ?, ?, ?)''',
                (sid, role, content, msg_type)
            )
            await db.execute(
                'UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (sid,)
            )
            await db.commit()

    async def load_messages(self, sid: str) -> List[Dict[str, Any]]:
        """加载会话的所有消息"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                '''SELECT role, content, msg_type FROM chat_messages
                   WHERE session_id = ? ORDER BY created_at''',
                (sid,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]

    async def auto_title(self, sid: str, first_msg: str):
        """根据第一条消息自动生成会话标题"""
        title = first_msg[:30].replace('\n', ' ').strip()
        if not title:
            title = "新对话"
        await self.update_session_title(sid, title)
