# -*- coding: utf-8 -*-
"""
StudyCompanion - 知识库引擎
加载和管理学科知识体系
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """学科知识库"""

    def __init__(self, data_dir: str = "data/knowledge"):
        self.data_dir = Path(data_dir)
        self.subjects: Dict[str, Dict] = {}

    def load_subject(self, file_path: str) -> Dict[str, Any]:
        """加载一个学科的知识库"""
        path = Path(file_path)
        if not path.exists():
            path = self.data_dir / file_path

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        subject_id = data.get('id', path.stem)
        self.subjects[subject_id] = data
        logger.info(f"📚 加载知识库: {data.get('name')} ({len(data.get('chapters', []))} 章)")
        return data

    def get_subject(self, subject_id: str) -> Optional[Dict]:
        """获取学科"""
        return self.subjects.get(subject_id)

    def get_chapter(self, subject_id: str, chapter_index: int) -> Optional[Dict]:
        """获取指定章节"""
        subject = self.subjects.get(subject_id)
        if subject and 0 <= chapter_index < len(subject.get('chapters', [])):
            return subject['chapters'][chapter_index]
        return None

    def get_topic(self, subject_id: str, topic_id: str) -> Optional[Dict]:
        """根据 topic_id 查找知识点"""
        subject = self.subjects.get(subject_id)
        if not subject:
            return None
        for chapter in subject.get('chapters', []):
            for topic in chapter.get('topics', []):
                if topic.get('id') == topic_id:
                    return {'chapter': chapter['name'], 'topic': topic}
        return None

    def search_topics(self, subject_id: str, keyword: str) -> List[Dict]:
        """按关键词搜索知识点"""
        subject = self.subjects.get(subject_id)
        if not subject:
            return []

        results = []
        keyword_lower = keyword.lower()
        for chapter in subject.get('chapters', []):
            for topic in chapter.get('topics', []):
                search_text = (
                    topic.get('name', '') + ' ' +
                    ' '.join(topic.get('exam_points', [])) + ' ' +
                    ' '.join(topic.get('common_mistakes', []))
                ).lower()

                if keyword_lower in search_text:
                    results.append({
                        'chapter': chapter['name'],
                        'topic': topic,
                        'score': 1.0
                    })
        return results

    def get_all_topics_flat(self, subject_id: str) -> List[Dict]:
        """获取所有知识点的平铺列表"""
        subject = self.subjects.get(subject_id)
        if not subject:
            return []

        topics = []
        for chapter in subject.get('chapters', []):
            for topic in chapter.get('topics', []):
                topics.append({
                    'chapter_name': chapter['name'],
                    'chapter_index': chapter.get('index', 0),
                    **topic
                })
        return topics

    def get_chapter_topics(self, subject_id: str, chapter_index: int) -> List[Dict]:
        """获取某个章节的所有知识点"""
        chapter = self.get_chapter(subject_id, chapter_index)
        if not chapter:
            return []
        return [{'chapter_name': chapter['name'], **t} for t in chapter.get('topics', [])]

    def build_context_for_ai(
        self,
        subject_id: str,
        topic_id: Optional[str] = None,
        chapter_index: Optional[int] = None
    ) -> str:
        """构建给 AI 的知识上下文"""
        subject = self.subjects.get(subject_id)
        if not subject:
            return ""

        if topic_id:
            result = self.get_topic(subject_id, topic_id)
            if result:
                topic = result['topic']
                chapter = result['chapter']
                return (
                    f"学科: {subject['name']}\n"
                    f"章节: {chapter}\n"
                    f"知识点: {topic['name']}\n"
                    f"难度: {'⭐' * topic.get('difficulty', 3)}\n"
                    f"考频: {topic.get('weight', '一般')}\n"
                    f"考点: {', '.join(topic.get('exam_points', []))}\n"
                    f"易错点: {', '.join(topic.get('common_mistakes', []))}\n"
                )

        if chapter_index is not None:
            chapter = self.get_chapter(subject_id, chapter_index)
            if chapter:
                lines = [f"学科: {subject['name']}", f"章节: {chapter['name']}"]
                for topic in chapter.get('topics', []):
                    lines.append(f"  - {topic['name']} (难度:{topic.get('difficulty',3)} 考频:{topic.get('weight','一般')})")
                return '\n'.join(lines)

        # 返回学科概览
        lines = [f"学科: {subject['name']} ({subject.get('description', '')})"]
        for ch in subject.get('chapters', []):
            lines.append(f"\n第{ch.get('index', '?')}章: {ch['name']}")
            for topic in ch.get('topics', []):
                lines.append(f"  [{topic.get('id','')}] {topic['name']} {'⭐'*topic.get('difficulty',3)} {topic.get('weight','一般')}")
        return '\n'.join(lines)

    def get_progress_summary(
        self, subject_id: str, completed_topics: List[str]
    ) -> Dict:
        """根据已完成的 topic 列表计算进度"""
        all_topics = self.get_all_topics_flat(subject_id)
        total = len(all_topics)
        completed = len([t for t in all_topics if t.get('id') in completed_topics])

        # 按章节统计
        chapters = {}
        for t in all_topics:
            ch = t.get('chapter_name', '未知')
            if ch not in chapters:
                chapters[ch] = {'total': 0, 'completed': 0}
            chapters[ch]['total'] += 1
            if t.get('id') in completed_topics:
                chapters[ch]['completed'] += 1

        return {
            'total': total,
            'completed': completed,
            'percent': round(completed / total * 100, 1) if total > 0 else 0,
            'by_chapter': chapters
        }

    def recommend_next(
        self,
        subject_id: str,
        completed_topics: List[str],
        weak_topics: List[str] = None
    ) -> List[Dict]:
        """推荐下一步学习的内容"""
        all_topics = self.get_all_topics_flat(subject_id)
        weak_topics = weak_topics or []

        # 优先级: 薄弱点 > 同章节未完成 > 下一章节
        recommendations = []

        for t in all_topics:
            tid = t.get('id')
            if tid in completed_topics:
                continue

            priority = 0
            if tid in weak_topics:
                priority = 100 - t.get('difficulty', 3)  # 薄弱优先
            else:
                # 按章节顺序 + 考频
                weight_map = {'高频': 50, '中频': 30, '低频': 10, '一般': 20}
                priority = weight_map.get(t.get('weight', '一般'), 20) - t.get('chapter_index', 0) * 2

            recommendations.append({
                'topic_id': tid,
                'name': t.get('name'),
                'chapter': t.get('chapter_name'),
                'difficulty': t.get('difficulty', 3),
                'weight': t.get('weight', '一般'),
                'priority': priority
            })

        recommendations.sort(key=lambda x: -x['priority'])
        return recommendations[:5]
