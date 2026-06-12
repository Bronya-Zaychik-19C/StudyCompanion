# -*- coding: utf-8 -*-
"""
StudyCompanion - 考点预测 + 真题模拟引擎
"""

import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ExamEngine:
    """考点预测与模拟引擎"""

    def __init__(self, ai_client=None, knowledge_base=None):
        self.ai_client = ai_client
        self.knowledge_base = knowledge_base
        logger.info("📝 考试引擎就绪")

    async def predict_hotspots(
        self, subject_id: str, chapter_index: Optional[int] = None
    ) -> Dict[str, Any]:
        """预测高频考点"""
        if chapter_index is not None:
            topics = self.knowledge_base.get_chapter_topics(subject_id, chapter_index)
            chapter_name = self.knowledge_base.get_chapter(subject_id, chapter_index)['name']
        else:
            topics = self.knowledge_base.get_all_topics_flat(subject_id)

        # 按考频和难度排序
        weight_order = {'高频': 3, '中频': 2, '低频': 1, '一般': 1}
        sorted_topics = sorted(
            topics,
            key=lambda t: (weight_order.get(t.get('weight', '一般'), 0), t.get('difficulty', 3)),
            reverse=True
        )

        hotspots = sorted_topics[:10]  # Top 10

        if self.ai_client:
            topic_list = '\n'.join(
                f"{i+1}. {t.get('name','')} [{t.get('chapter_name','')}] 考频:{t.get('weight','')} 难度:{'⭐'*t.get('difficulty',3)}"
                for i, t in enumerate(hotspots)
            )
            chapter_info = f"第{chapter_index}章: {chapter_name}" if chapter_index is not None else "全部章节"

            analysis = await self.ai_client.chat([
                {"role": "system", "content": "你是考研数学命题分析专家。"},
                {"role": "user", "content": (
                    f"基于以下{chapter_info}的高频知识点，请：\n"
                    f"1. 预测今年最可能出题的方向（3个以内）\n"
                    f"2. 给出每个方向的命题概率和理由\n"
                    f"3. 建议如何针对性复习\n\n"
                    f"知识点列表：\n{topic_list}\n\n"
                    f"回复控制在200字以内。"
                )}
            ])

            return {
                'hotspots': [{'name': t.get('name'), 'chapter': t.get('chapter_name'),
                              'weight': t.get('weight'), 'difficulty': t.get('difficulty')}
                             for t in hotspots],
                'ai_analysis': analysis,
                'chapter_name': chapter_name if chapter_index else '全部'
            }

        return {
            'hotspots': [{'name': t.get('name'), 'chapter': t.get('chapter_name')}
                         for t in hotspots]
        }

    async def generate_mock_exam(
        self, subject_id: str, question_count: int = 5,
        chapter_index: Optional[int] = None
    ) -> Dict[str, Any]:
        """生成模拟试卷"""
        if chapter_index is not None:
            topics = self.knowledge_base.get_chapter_topics(subject_id, chapter_index)
        else:
            topics = self.knowledge_base.get_all_topics_flat(subject_id)

        # 按考频加权随机选择
        import random
        weight_map = {'高频': 5, '中频': 3, '低频': 1, '一般': 1}
        weights = [weight_map.get(t.get('weight', '一般'), 1) for t in topics]
        selected = random.choices(topics, weights=weights, k=min(question_count, len(topics)))

        questions = []
        for topic in selected:
            knowledge_context = ""
            if self.knowledge_base:
                knowledge_context = self.knowledge_base.build_context_for_ai(
                    subject_id, topic_id=topic.get('id')
                )

            if self.ai_client:
                prompt = (
                    f"请出一道考研数学一真题风格的题目。\n\n"
                    f"{knowledge_context}\n\n"
                    f"要求：\n"
                    f"1. 仿照历年真题的出题方式\n"
                    f"2. 选择题(4选项)或填空题\n"
                    f"3. 包含考研常见的陷阱\n"
                    f"4. 难度匹配({topic.get('difficulty',3)}/5)\n\n"
                    f"返回JSON：{{\"question\":\"...\",\"options\":[\"A. ...\",...],\"answer\":\"...\",\"explanation\":\"...\",\"exam_tip\":\"考研备考提示\"}}"
                )
                response = await self.ai_client.chat([
                    {"role": "system", "content": "你是考研数学命题专家。只输出JSON。"},
                    {"role": "user", "content": prompt}
                ], temperature=0.9)

                try:
                    start = response.find('{')
                    end = response.rfind('}') + 1
                    q = json.loads(response[start:end])
                except (json.JSONDecodeError, KeyError):
                    q = {
                        "question": f"请简述{topic.get('name','')}的要点",
                        "options": [],
                        "answer": "",
                        "explanation": ""
                    }
            else:
                q = {
                    "question": f"简答题：{topic.get('name','')}",
                    "options": [],
                    "answer": "",
                    "explanation": ""
                }

            q['topic_name'] = topic.get('name', '')
            q['topic_id'] = topic.get('id', '')
            q['chapter'] = topic.get('chapter_name', '')
            questions.append(q)

        return {'questions': questions, 'total': len(questions)}
