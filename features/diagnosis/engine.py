# -*- coding: utf-8 -*-
"""
StudyCompanion - 知识点诊断引擎
AI 出题 → 用户答题 → 评估薄弱点
"""

import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class DiagnosisEngine:
    """知识点诊断引擎"""

    def __init__(self, ai_client=None, knowledge_base=None):
        self.ai_client = ai_client
        self.knowledge_base = knowledge_base
        self.sessions: Dict[str, Dict] = {}
        logger.info("🔍 诊断引擎就绪")

    async def start_diagnosis(
        self, session_id: str, subject_id: str = "math_one",
        chapter_index: int = None, topic_id: str = None
    ) -> Dict[str, Any]:
        """开始一次诊断测试"""
        # 获取要测试的知识点
        if topic_id:
            result = self.knowledge_base.get_topic(subject_id, topic_id)
            topics = [result['topic']] if result else []
        elif chapter_index is not None:
            topics = self.knowledge_base.get_chapter_topics(subject_id, chapter_index)
        else:
            topics = self.knowledge_base.get_all_topics_flat(subject_id)[:5]  # 默认测5个

        self.sessions[session_id] = {
            'subject_id': subject_id,
            'topics': topics,
            'current_index': 0,
            'results': [],
            'history': []
        }

        # 生成第一道题
        question = await self._generate_question(session_id)
        if question.get('answer'):
            self.sessions[session_id]['current_answer'] = question['answer']
        return question

    async def _generate_question(self, session_id: str) -> Dict:
        """AI 生成诊断题"""
        session = self.sessions.get(session_id)
        if not session:
            return {"done": True}

        idx = session['current_index']
        if idx >= len(session['topics']):
            return {"done": True, "summary": await self._generate_report(session_id)}

        topic = session['topics'][idx]
        knowledge_context = ""
        if self.knowledge_base:
            knowledge_context = self.knowledge_base.build_context_for_ai(
                session['subject_id'], topic_id=topic.get('id')
            )

        if self.ai_client:
            prompt = (
                f"你是考研数学一出题老师。请就以下知识点出一道选择题(4个选项)：\n\n"
                f"{knowledge_context}\n\n"
                f"要求：\n"
                f"1. 题目要有考研真题的风格\n"
                f"2. 4个选项(A/B/C/D)中只有1个正确\n"
                f"3. 错误选项要设置典型陷阱\n"
                f"4. 难度匹配该知识点({topic.get('difficulty', 3)}/5)\n\n"
                f"请返回JSON格式：\n"
                f'{{"question": "题目内容", "options": ["A. ...", "B. ...", "C. ...", "D. ..."], "answer": "A", "explanation": "解题思路和知识点解析"}}'
            )
            response = await self.ai_client.chat([
                {"role": "system", "content": "你是考研数学出题专家。只输出JSON。"},
                {"role": "user", "content": prompt}
            ], temperature=0.8)

            try:
                start = response.find('{')
                end = response.rfind('}') + 1
                question_data = json.loads(response[start:end])
            except (json.JSONDecodeError, KeyError):
                question_data = {
                    "question": f"请简述{topic.get('name', '这个知识点')}的核心内容",
                    "options": [],
                    "answer": "",
                    "explanation": ""
                }
        else:
            question_data = {
                "question": f"请解释：{topic.get('name', '这个知识点')}（{topic.get('chapter_name', '')}）",
                "options": [],
                "answer": "",
                "explanation": ""
            }

        question_data['topic'] = topic.get('name', '')
        question_data['topic_id'] = topic.get('id', '')
        question_data['difficulty'] = topic.get('difficulty', 3)

        return question_data

    async def submit_answer(self, session_id: str, answer: str) -> Dict:
        """提交答案并获取反馈"""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "会话未找到"}

        idx = session['current_index']
        current_topic = session['topics'][idx] if idx < len(session['topics']) else None

        correct = answer.upper() == session.get('current_answer', '').upper()

        session['results'].append({
            'topic_id': current_topic.get('id') if current_topic else '',
            'topic_name': current_topic.get('name') if current_topic else '',
            'correct': correct,
            'user_answer': answer
        })

        # 记录到历史
        await self._record_result(session_id, current_topic.get('id') if current_topic else '', correct)

        feedback = await self._generate_feedback(session_id, answer, correct)

        # 移到下一题
        session['current_index'] += 1

        return {
            'correct': correct,
            'feedback': feedback,
            'progress': f"{idx + 1}/{len(session['topics'])}"
        }

    async def _generate_feedback(self, session_id, answer, correct):
        """AI 生成答题反馈"""
        if not self.ai_client:
            return "答案已记录" if correct else "再想想这道题"

        session = self.sessions.get(session_id)
        idx = session['current_index']
        topic = session['topics'][idx] if idx < len(session['topics']) else None

        if correct:
            prompt = f"用户答对了关于「{topic.get('name') if topic else ''}」的题。简短表扬(1句话)，然后提示这个考点在考研中常见的变体考法。"
        else:
            prompt = f"用户答错了关于「{topic.get('name') if topic else ''}」的题，他的答案是{answer}。温和指出错误，用1-2句话提示正确的思考方向。不要直接给答案。"

        return await self.ai_client.chat([
            {"role": "system", "content": "你是考研辅导老师小助，温柔鼓励。回复简短。"},
            {"role": "user", "content": prompt}
        ])

    async def _generate_report(self, session_id) -> Dict:
        """生成诊断报告"""
        session = self.sessions.get(session_id)
        if not session:
            return {}

        results = session['results']
        total = len(results)
        correct = sum(1 for r in results if r['correct'])
        wrong = total - correct

        # 按知识点分类
        weak_topics = [r for r in results if not r['correct']]
        strong_topics = [r for r in results if r['correct']]

        report = {
            'total': total,
            'correct': correct,
            'wrong': wrong,
            'accuracy': round(correct / total * 100, 1) if total > 0 else 0,
            'weak_points': [{'name': r['topic_name'], 'id': r['topic_id']} for r in weak_topics],
            'strong_points': [{'name': r['topic_name'], 'id': r['topic_id']} for r in strong_topics]
        }

        if self.ai_client:
            prompt = (
                f"用户完成了{total}道题的诊断测试，正确{correct}道，正确率{report['accuracy']}%。\n"
                f"薄弱点：{', '.join(r['topic_name'] for r in weak_topics) if weak_topics else '无'}\n"
                f"请用2-3句话总结，并给出针对性的学习建议。语气温暖鼓励。"
            )
            report['ai_summary'] = await self.ai_client.chat([
                {"role": "system", "content": "你是考研辅导老师小助。"},
                {"role": "user", "content": prompt}
            ])

        return report

    async def next_question(self, session_id: str) -> Dict:
        """获取下一道题"""
        question = await self._generate_question(session_id)
        if question.get('done'):
            return question

        if question.get('answer'):
            self.sessions[session_id]['current_answer'] = question['answer']

        return question

    async def _record_result(self, session_id, topic_id, correct):
        """记录答题结果"""
        session = self.sessions.get(session_id)
        if session is not None and 'history' in session:
            session['history'].append({
                'topic_id': topic_id,
                'correct': correct
            })
