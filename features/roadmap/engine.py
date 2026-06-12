# -*- coding: utf-8 -*-
"""
StudyCompanion - 学习路径规划引擎
根据诊断结果推荐学习顺序
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class RoadmapEngine:
    """学习路径规划引擎"""

    def __init__(self, ai_client=None, knowledge_base=None):
        self.ai_client = ai_client
        self.knowledge_base = knowledge_base
        self.user_progress: Dict[str, Dict] = {}  # user_id -> progress data
        logger.info("🗺️ 路径规划引擎就绪")

    def set_progress(
        self, user_id: str, completed_topics: List[str],
        weak_topics: List[str] = None
    ):
        """设置用户学习进度"""
        self.user_progress[user_id] = {
            'completed': completed_topics,
            'weak': weak_topics or []
        }

    def add_completed(self, user_id: str, topic_id: str):
        """标记知识点为已完成"""
        if user_id not in self.user_progress:
            self.user_progress[user_id] = {'completed': [], 'weak': []}
        if topic_id not in self.user_progress[user_id]['completed']:
            self.user_progress[user_id]['completed'].append(topic_id)

    def add_weak(self, user_id: str, topic_id: str):
        """标记知识点为薄弱"""
        if user_id not in self.user_progress:
            self.user_progress[user_id] = {'completed': [], 'weak': []}
        if topic_id not in self.user_progress[user_id]['weak']:
            self.user_progress[user_id]['weak'].append(topic_id)

    def get_recommendations(
        self, user_id: str, subject_id: str = "math_one", count: int = 5
    ) -> List[Dict]:
        """获取推荐学习路径"""
        user_data = self.user_progress.get(user_id, {'completed': [], 'weak': []})

        # 使用知识库的推荐
        if self.knowledge_base:
            recommendations = self.knowledge_base.recommend_next(
                subject_id,
                user_data['completed'],
                user_data['weak']
            )
            return recommendations[:count]

        # Fallback: 从知识库获取所有知识点
        all_topics = self.knowledge_base.get_all_topics_flat(subject_id)
        completed_set = set(user_data['completed'])
        weak_set = set(user_data['weak'])

        remaining = [t for t in all_topics if t.get('id') not in completed_set]
        # 薄弱优先
        remaining.sort(key=lambda t: (
            0 if t.get('id') in weak_set else 1,
            -{'高频': 3, '中频': 2}.get(t.get('weight', ''), 1),
            t.get('chapter_index', 999)
        ))

        return [{
            'topic_id': t.get('id'),
            'name': t.get('name'),
            'chapter': t.get('chapter_name'),
            'difficulty': t.get('difficulty', 3),
            'weight': t.get('weight', '一般'),
            'is_weak': t.get('id') in weak_set
        } for t in remaining[:count]]

    async def generate_study_plan(
        self, user_id: str, subject_id: str = "math_one",
        available_days: int = 30
    ) -> Dict[str, Any]:
        """生成详细学习计划"""
        recommendations = self.get_recommendations(user_id, subject_id, count=20)

        if self.ai_client and recommendations:
            topic_list = '\n'.join(
                f"- {r['name']} [{r['chapter']}] 考频:{r['weight']} 难度:{'⭐'*r['difficulty']}"
                + (' [薄弱]' if r.get('is_weak') else '')
                for r in recommendations[:15]
            )

            plan_prompt = (
                f"用户准备考研数学一，可用{available_days}天。\n"
                f"推荐学习的知识点（按优先级排序）：\n{topic_list}\n\n"
                f"请制定一份学习计划：\n"
                f"1. 按章节划分每周的学习内容\n"
                f"2. 标注每天建议的学习时长\n"
                f"3. 指出最需要投入时间的薄弱环节\n"
                f"4. 建议何时开始做真题\n"
                f"回复控制在300字以内，要有可操作性。"
            )

            ai_plan = await self.ai_client.chat([
                {"role": "system", "content": "你是考研规划师，帮助制定科学的学习计划。"},
                {"role": "user", "content": plan_prompt}
            ])

            return {
                'recommendations': recommendations[:10],
                'ai_study_plan': ai_plan,
                'available_days': available_days
            }

        return {
            'recommendations': recommendations[:10],
            'available_days': available_days
        }

    async def get_chapter_progress(
        self, user_id: str, subject_id: str = "math_one"
    ) -> Dict:
        """获取按章节的进度统计"""
        if not self.knowledge_base:
            return {}

        completed = self.user_progress.get(user_id, {}).get('completed', [])
        return self.knowledge_base.get_progress_summary(subject_id, completed)
