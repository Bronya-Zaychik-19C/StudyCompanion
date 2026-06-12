# -*- coding: utf-8 -*-
"""
StudyCompanion - 学科感知费曼学习法引擎
基于知识库的 AI 引导式学习
"""

import logging
from typing import Dict, Any, List, Optional
from enum import Enum
from config.personas import get_system_prompt, get_feynman_hook

logger = logging.getLogger(__name__)


class FeynmanStage(Enum):
    EXPLAIN = "explain"
    IDENTIFY = "identify"
    SIMPLIFY = "simplify"
    REVIEW = "review"


class FeynmanEngine:
    """费曼学习法引擎 - 学科感知版"""

    def __init__(self, ai_client=None, knowledge_base=None, question_bank=None):
        self.ai_client = ai_client
        self.knowledge_base = knowledge_base
        self.question_bank = question_bank
        self.sessions: Dict[str, Dict] = {}
        logger.info("🧠 费曼引擎就绪" + (" (AI+知识库+真题)" if ai_client and knowledge_base and question_bank else ""))

    async def start_session(
        self, session_id: str, concept: str,
        subject_id: str = "math_one", topic_id: str = None,
        persona_id: str = "mentor"
    ) -> str:
        """开始费曼学习会话"""
        self.sessions[session_id] = {
            'concept': concept,
            'subject_id': subject_id,
            'topic_id': topic_id,
            'persona_id': persona_id,
            'stage': FeynmanStage.EXPLAIN,
            'history': [],
            'round': 0
        }

        # 构建知识上下文
        knowledge_context = ""
        if self.knowledge_base:
            if topic_id:
                knowledge_context = self.knowledge_base.build_context_for_ai(
                    subject_id, topic_id=topic_id
                )
            else:
                # 搜索匹配的知识点
                matches = self.knowledge_base.search_topics(subject_id, concept)
                if matches:
                    best = matches[0]
                    self.sessions[session_id]['topic_id'] = best['topic']['id']
                    knowledge_context = self.knowledge_base.build_context_for_ai(
                        subject_id, topic_id=best['topic']['id']
                    )

        if self.ai_client:
            persona_prompt = get_system_prompt(persona_id)
            hook = get_feynman_hook(persona_id, concept)
            system_prompt = (
                f"{persona_prompt}\n\n"
                f"当前正在用费曼学习法引导学习「{concept}」。\n"
                f"知识点信息：\n{knowledge_context}\n\n"
                f"{hook}\n"
                f"用考研真题的语境来提问。先问一个开放性问题。2-3句即可。"
            )
            response = await self.ai_client.chat([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"我想学习{concept}，请引导我"}
            ], max_tokens=4096)
        else:
            response = f"好的哥哥！我们来理解一下「{concept}」。这是考研数学一的重要考点，你先说说你目前的理解？"

        self.sessions[session_id]['history'].append({"role": "assistant", "content": response})
        logger.info(f"📚 费曼学习: {concept}" + (f" [{topic_id}]" if topic_id else ""))
        return response

    async def process_response(self, session_id: str, user_input: str) -> Dict[str, Any]:
        session = self.sessions.get(session_id)
        if not session:
            return {"response": "会话未找到", "stage": "unknown"}

        session['history'].append({"role": "user", "content": user_input})
        session['round'] += 1

        # 判断阶段
        stage = self._determine_next_stage(session)
        session['stage'] = stage

        # 获取知识上下文
        knowledge_context = ""
        if self.knowledge_base and session.get('topic_id'):
            knowledge_context = self.knowledge_base.build_context_for_ai(
                session.get('subject_id', 'math_one'),
                topic_id=session.get('topic_id')
            )

        if self.ai_client:
            response = await self._ai_response(session, user_input, stage, knowledge_context)
        else:
            response = self._template_response(session['concept'], stage, user_input)

        session['history'].append({"role": "assistant", "content": response})
        return {"response": response, "stage": stage.value}

    async def _ai_response(self, session, user_input, stage, knowledge_context):
        persona_id = session.get('persona_id', 'mentor')
        persona_prompt = get_system_prompt(persona_id)

        stage_guides = {
            FeynmanStage.EXPLAIN: (
                "用户刚尝试解释了。根据你的风格回应：肯定用户，追问一个更具体的问题。"
                "如果用户说得不准确，指出问题让用户再想想。"
                "用考研中常见的命题角度来提问。2-3句。"
            ),
            FeynmanStage.IDENTIFY: (
                "找用户回答中的模糊之处追问。"
                "可以用考研真题或典型例题来测试理解。"
                "如果遗漏了重要考点，直接指出来。"
                "2-3句话，以提问结尾。"
            ),
            FeynmanStage.SIMPLIFY: (
                "用户遇到了困难。"
                "用生活中的例子来类比这个数学概念，或者用更简单的方式讲解核心。"
                "通俗易懂。2-4句。"
            ),
            FeynmanStage.REVIEW: (
                "总结这个知识点在考研中的考查方式和常见易错点。"
                "问用户还有什么疑问。3-4句收尾。"
            ),
        }

        system_prompt = (
            f"{persona_prompt}\n\n"
            f"当前知识点：{session['concept']}\n"
            f"知识点信息：\n{knowledge_context}\n\n"
            f"{stage_guides.get(stage, stage_guides[FeynmanStage.EXPLAIN])}"
        )

        return await self.ai_client.chat([
            {"role": "system", "content": system_prompt},
            *session['history'][-12:],
            {"role": "user", "content": user_input}
        ], max_tokens=4096)

    def _determine_next_stage(self, session: Dict) -> FeynmanStage:
        round_num = session['round']
        last_msg = ""
        for msg in reversed(session['history']):
            if msg['role'] == 'user':
                last_msg = msg['content']
                break

        confused = any(w in last_msg for w in ["不懂", "不知道", "不会", "难", " confuse"])
        confident = any(w in last_msg for w in ["懂了", "明白", "原来如此", "理解", "就是"])

        if round_num <= 1:
            return FeynmanStage.EXPLAIN
        elif confused:
            return FeynmanStage.SIMPLIFY
        elif round_num >= 6 or confident:
            return FeynmanStage.REVIEW
        else:
            return FeynmanStage.IDENTIFY

    def _template_response(self, concept, stage, user_input):
        import random
        templates = {
            FeynmanStage.EXPLAIN: [f"很好！能再具体说说吗？"],
            FeynmanStage.IDENTIFY: [f"能举个例子吗？"],
            FeynmanStage.SIMPLIFY: [f"我换个方式解释一下..."],
            FeynmanStage.REVIEW: [f"我们来总结一下今天的内容"]
        }
        return random.choice(templates.get(stage, templates[FeynmanStage.EXPLAIN]))

    async def start_session_stream(self, session_id, concept, subject_id="math_one", topic_id=None, persona_id="mentor", prior_history=None):
        """流式开始费曼学习，可传入之前的对话历史"""
        initial_history = list(prior_history[-6:]) if prior_history else []
        self.sessions[session_id] = {
            'concept': concept, 'subject_id': subject_id, 'topic_id': topic_id,
            'persona_id': persona_id, 'stage': FeynmanStage.EXPLAIN, 'history': initial_history, 'round': 0
        }
        knowledge_context = ""
        if self.knowledge_base:
            if topic_id:
                knowledge_context = self.knowledge_base.build_context_for_ai(subject_id, topic_id=topic_id)
            else:
                matches = self.knowledge_base.search_topics(subject_id, concept)
                if matches:
                    self.sessions[session_id]['topic_id'] = matches[0]['topic']['id']
                    knowledge_context = self.knowledge_base.build_context_for_ai(subject_id, topic_id=matches[0]['topic']['id'])

        persona_prompt = get_system_prompt(persona_id)
        hook = get_feynman_hook(persona_id, concept)
        user_context = ""
        if initial_history:
            user_context = "之前的对话中用户提到了一些背景，请在引导时适当参照（比如用户说基础差就用更简单的讲法）。\n"
        exam_context = ""
        if self.question_bank and topic_id:
            exam_context = "\n历年真题：\n" + self.question_bank.build_exam_context(topic_id, limit=3)
        sp = f"{persona_prompt}\n\n{user_context}正在引导学习「{concept}」。\n知识点：\n{knowledge_context}\n{exam_context}\n\n{hook}\n用考研真题语境提问，2-3句。"

        full = ""
        async for token in self.ai_client.chat_stream([
            {"role": "system", "content": sp},
            {"role": "user", "content": f"我想学习{concept}，请引导我"}
        ], max_tokens=4096):
            full += token
            yield token
        self.sessions[session_id]['history'].append({"role": "assistant", "content": full})
        logger.info(f"📚 费曼学习(流式): {concept}")

    async def process_response_stream(self, session_id: str, user_input: str):
        """流式处理用户回答，逐 token yield"""
        session = self.sessions.get(session_id)
        if not session:
            yield "会话未找到"; return

        session['history'].append({"role": "user", "content": user_input})
        session['round'] += 1
        stage = self._determine_next_stage(session)
        session['stage'] = stage

        knowledge_context = ""
        if self.knowledge_base and session.get('topic_id'):
            knowledge_context = self.knowledge_base.build_context_for_ai(
                session.get('subject_id', 'math_one'), topic_id=session.get('topic_id'))

        persona_id = session.get('persona_id', 'mentor')
        persona_prompt = get_system_prompt(persona_id)
        guides = {
            FeynmanStage.EXPLAIN: "用户刚尝试解释了。肯定用户，追问更具体的问题。用考研命题角度提问。2-3句。",
            FeynmanStage.IDENTIFY: "找用户回答中的模糊之处追问。用考研真题测试理解。遗漏的考点直接指出。以提问结尾。",
            FeynmanStage.SIMPLIFY: "用户遇到困难。用生活类比来解释，通俗易懂。2-4句。",
            FeynmanStage.REVIEW: "总结这个知识点在考研中的考查方式和易错点。问用户还有疑问。3-4句。",
        }
        sp = f"{persona_prompt}\n\n当前知识点：{session['concept']}\n知识点信息：\n{knowledge_context}\n\n{guides.get(stage, guides[FeynmanStage.EXPLAIN])}"

        full = ""
        async for token in self.ai_client.chat_stream([
            {"role": "system", "content": sp},
            *session['history'][-12:],
            {"role": "user", "content": user_input}
        ], max_tokens=4096):
            full += token
            yield token
        session['history'].append({"role": "assistant", "content": full})

    def end_session(self, session_id: str) -> Optional[str]:
        if session_id not in self.sessions:
            return None
        session = self.sessions.pop(session_id)
        return f"费曼学习结束，共{session['round']}轮"
