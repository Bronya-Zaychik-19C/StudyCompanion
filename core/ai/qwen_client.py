# -*- coding: utf-8 -*-
"""
StudyCompanion - Qwen 文本聊天客户端
通过 DashScope API 调用 Qwen 模型
"""

import json
import logging
from typing import Optional, List, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class QwenChatClient:
    """Qwen 文本聊天客户端"""

    def __init__(self, api_key: str, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com/v1/chat/completions"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        logger.info(f"🤖 AI 客户端初始化 ({base_url.split('//')[1].split('/')[0]} | {model})")

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> str:
        """
        发送聊天请求

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            AI 回复文本
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.base_url,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

            return data["choices"][0]["message"]["content"]

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096
    ):
        """流式聊天，逐 token 返回；失败时自动降级为非流式"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream("POST", self.base_url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        logger.warning(f"流式不可用({response.status_code})，降级为非流式")
                        # Fallback: non-streaming
                        result = await self.chat(messages, temperature, max_tokens)
                        yield result
                        return
                    async for line in response.aiter_lines():
                        if line.startswith("data:"):
                            data_str = line[5:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            logger.warning(f"流式失败({e})，降级为非流式")
            result = await self.chat(messages, temperature, max_tokens)
            yield result

    async def classify_intent(self, user_input: str) -> Dict[str, Any]:
        """分类用户意图"""
        messages = [
            {
                "role": "system",
                "content": (
                    "你是意图分类器。分析用户输入，输出 JSON 格式。\n"
                    '{\n'
                    '  "intent": "feynman" | "schedule" | "study_log" | "emotion" | "chat",\n'
                    '  "concept": "提取的学习概念（仅 feynman 意图）",\n'
                    '  "confidence": 0.0-1.0\n'
                    '}\n\n'
                    "规则：\n"
                    "- feynman: 用户想学习/理解某个知识（我想学导数、讲解牛顿定律、搞懂微积分）\n"
                    "- schedule: 创建/管理日程（帮我安排、创建提醒、明天下午）\n"
                    "- study_log: 记录学习（学了、完成了、复习了）\n"
                    "- emotion: 情绪表达（好累、开心、焦虑）\n"
                    "- chat: 普通对话（你好、谢谢、今天天气）\n\n"
                    "只输出 JSON，不要其他内容。"
                )
            },
            {"role": "user", "content": user_input}
        ]

        response = await self.chat(messages, temperature=0.1, max_tokens=200)

        try:
            # 尝试提取 JSON
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            pass

        # 默认返回 chat
        return {"intent": "chat", "confidence": 0.3}

    async def generate_feynman_response(
        self,
        concept: str,
        stage: str,
        user_input: str,
        history: List[Dict[str, str]]
    ) -> str:
        """生成费曼学习法的 AI 回复"""
        system_prompt = self._get_feynman_system_prompt(concept, stage)

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-6:])  # 最近 6 条历史
        messages.append({"role": "user", "content": user_input})

        return await self.chat(messages, temperature=0.7, max_tokens=512)

    def _get_feynman_system_prompt(self, concept: str, stage: str) -> str:
        """获取费曼学习法的系统提示词"""
        base = (
            "你是小助，一个温柔有耐心的 AI 学习私教。你正在用费曼学习法引导用户学习「{concept}」。\n\n"
            "你的角色：\n"
            "- 称呼用户为「哥哥」\n"
            "- 温柔耐心，绝不批评\n"
            "- 用生活化的类比帮助理解\n"
            "- 不直接给答案，引导用户自己思考\n\n"
        ).format(concept=concept)

        stage_guides = {
            "explain": (
                "当前阶段：引导解释。\n"
                "用户刚开始学习这个概念。请：\n"
                "1. 先让用户用自己的话解释「{concept}」\n"
                "2. 问开放性问题，鼓励用户多说\n"
                "3. 即使说得不准确也要先肯定\n"
                "4. 不要说教，而是引导\n"
                "回答要简短（2-3句），以问题结尾。"
            ).format(concept=concept),
            "identify": (
                "当前阶段：识别薄弱点。\n"
                "用户已经尝试解释了。请：\n"
                "1. 找到用户回答中的模糊之处\n"
                "2. 针对性地追问\n"
                "3. 如果用户回答准确，换个角度挑战他\n"
                "4. 用反例或边界情况测试理解\n"
                "回答要简短（2-3句），以问题结尾。"
            ),
            "simplify": (
                "当前阶段：简化类比。\n"
                "用户可能遇到了难点。请：\n"
                "1. 用一个日常生活中通俗的例子类比「{concept}」\n"
                "2. 避免专业术语，用大白话\n"
                "3. 问用户「这样理解了吗?」\n"
                "4. 如果用户表示理解了，鼓励他自己尝试类比\n"
                "回答要简短生动（2-4句）。"
            ).format(concept=concept),
            "review": (
                "当前阶段：回顾总结。\n"
                "学习接近尾声。请：\n"
                "1. 用 2-3 句话总结今天学到的要点\n"
                "2. 问用户还有没有疑问\n"
                "3. 肯定用户的努力\n"
                "回答温暖简短（3-4句）。"
            ),
        }

        return base + stage_guides.get(stage, stage_guides["explain"])
