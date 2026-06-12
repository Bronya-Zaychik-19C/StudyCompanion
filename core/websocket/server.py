"""
WebSocket 服务器 - 处理客户端连接和消息路由

职责：
1. 管理 WebSocket 连接
2. 路由消息到对应处理器
3. 协调音频流和文本消息
4. 管理会话状态
"""

import asyncio
import json
import struct
from typing import Dict, Any, Callable, Optional
from fastapi import WebSocket, WebSocketDisconnect
from loguru import logger

from core.ai.router import SmartRouter
from core.ai.ollama_client import OllamaClient
from core.audio.realtime_client import QwenRealtimeClient
from core.memory.database import DatabaseManager
from core.memory.vector_store import ConversationMemory
from features.schedule.manager import ScheduleManager
from features.schedule.tools import ScheduleTools


class SessionManager:
    """单个会话管理器 - 管理一个用户的完整交互状态"""
    
    def __init__(
        self,
        session_id: str,
        websocket: WebSocket,
        config: dict,
        db_manager: DatabaseManager,
        ollama_client: OllamaClient,
        vector_memory: ConversationMemory,
        schedule_manager: ScheduleManager
    ):
        self.session_id = session_id
        self.websocket = websocket
        self.config = config
        self.db = db_manager
        self.ollama = ollama_client
        self.memory = vector_memory
        self.schedule_manager = schedule_manager
        
        # AI 路由器
        self.router = SmartRouter(ollama_client)
        
        # 日程工具
        self.schedule_tools = ScheduleTools(schedule_manager)
        
        # 实时语音客户端（懒加载）
        self.realtime_client: Optional[QwenRealtimeClient] = None
        
        # 会话状态
        self.is_active = True
        self.current_mode = "text"  # text 或 audio
        self.conversation_history = []
        
    async def initialize(self):
        """初始化会话"""
        logger.info(f"初始化会话: {self.session_id}")
        
        # 加载历史对话（最近 10 条）
        history = await self.db.get_recent_conversations(limit=10)
        for conv in reversed(history):
            self.conversation_history.append({
                "role": conv["role"],
                "content": conv["content"]
            })
        
        # 发送欢迎消息
        await self.send_message({
            "type": "system",
            "action": "connected",
            "message": "连接成功，你好！有什么我可以帮你的吗？"
        })
        
    async def send_message(self, data: dict):
        """发送消息到客户端"""
        try:
            await self.websocket.send_json(data)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            
    async def handle_message(self, message: dict):
        """处理接收到的消息"""
        action = message.get("action", "")
        
        handlers = {
            "chat": self._handle_chat,
            "stream_data": self._handle_audio_stream,
            "start_audio": self._handle_start_audio,
            "stop_audio": self._handle_stop_audio,
            "get_schedule": self._handle_get_schedule,
            "tool_call": self._handle_tool_call,
            "commit": self._handle_commit,  # 音频提交
        }
        
        handler = handlers.get(action)
        if handler:
            await handler(message)
        else:
            logger.warning(f"未知动作: {action}")
            
    async def _handle_chat(self, message: dict):
        """处理文本聊天"""
        user_input = message.get("content", "").strip()
        if not user_input:
            return
            
        logger.info(f"[{self.session_id}] 用户: {user_input}")
        
        # 保存用户消息
        await self.db.add_conversation("user", user_input)
        self.conversation_history.append({"role": "user", "content": user_input})
        
        # 智能路由
        route_result = await self.router.route(user_input)
        intent = route_result["type"]
        
        logger.info(f"意图识别: {intent}")
        
        # 根据意图处理
        if intent == "schedule":
            response = await self._process_schedule_intent(user_input)
        elif intent == "knowledge":
            response = await self._process_knowledge_intent(user_input)
        elif intent == "study_log":
            response = await self._process_study_log_intent(user_input)
        else:
            # 普通聊天或情感陪伴
            response = await self._process_chat_intent(user_input, intent)
            
        # 发送响应
        await self.send_message({
            "type": "assistant",
            "content": response,
            "intent": intent
        })
        
        # 保存助手回复
        await self.db.add_conversation("assistant", response)
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # 保存到长期记忆（异步）
        asyncio.create_task(self.memory.add_conversation(user_input, response))
        
    async def _process_schedule_intent(self, user_input: str) -> str:
        """处理日程相关意图"""
        # 使用 Ollama 分析具体操作
        analysis_prompt = f"""分析用户的日程相关请求，返回 JSON 格式：
用户说: "{user_input}"

请分析并返回：
{{
    "action": "add" | "query" | "complete" | "cancel" | "summary",
    "title": "日程标题（如果是添加）",
    "time": "时间（如果提到，格式 HH:MM）",
    "date": "日期（如果提到，格式 YYYY-MM-DD，今天则为 null）"
}}

只返回 JSON，不要其他内容。"""

        try:
            analysis = await self.ollama.generate_text(analysis_prompt, model_type="fast")
            # 尝试解析 JSON
            import re
            json_match = re.search(r'\{.*\}', analysis, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                action = parsed.get("action", "query")
                
                if action == "add":
                    title = parsed.get("title", user_input)
                    time_str = parsed.get("time")
                    result = await self.schedule_manager.add_schedule(
                        title=title,
                        description=user_input,
                        scheduled_time=time_str
                    )
                    return f"好的，已为你创建日程：{title}" + (f"，提醒时间：{time_str}" if time_str else "")
                    
                elif action == "query":
                    schedules = await self.schedule_manager.get_today_schedules()
                    if not schedules:
                        return "你今天还没有安排任何日程哦～"
                    summary = await self.schedule_manager.generate_daily_summary()
                    return summary
                    
                elif action == "summary":
                    summary = await self.schedule_manager.generate_daily_summary()
                    return summary
                    
                elif action == "complete":
                    # 简化处理：查找并完成第一个匹配的日程
                    schedules = await self.schedule_manager.get_today_schedules()
                    for s in schedules:
                        if parsed.get("title", "") in s["title"]:
                            await self.schedule_manager.complete_schedule(s["id"])
                            return f"已完成日程：{s['title']}，做得好！"
                    return "没有找到对应的日程，你可以告诉我具体是哪个任务吗？"
                    
        except Exception as e:
            logger.error(f"日程处理错误: {e}")
            
        # 兜底：查询今日日程
        summary = await self.schedule_manager.generate_daily_summary()
        return summary
        
    async def _process_knowledge_intent(self, user_input: str) -> str:
        """处理知识问答意图"""
        context = ""
        
        # 尝试从记忆中搜索相关内容（如果 embedding 服务可用）
        try:
            relevant = await self.memory.search_relevant(user_input, top_k=3)
            if relevant:
                context = "\n".join([f"- {r['text']}" for r in relevant])
                context = f"\n\n相关历史对话：\n{context}"
        except Exception as e:
            logger.warning(f"记忆搜索跳过（embedding 未配置）: {e}")
            
        prompt = f"""你是一个专业的学习助手，请回答用户的问题。
{context}

用户问题：{user_input}

请用简洁清晰的语言回答，如果不确定请诚实说明。"""

        response = await self.ollama.generate_text(prompt, model_type="main")
        return response
        
    async def _process_study_log_intent(self, user_input: str) -> str:
        """处理学习记录意图"""
        # 分析是查询还是记录
        if any(kw in user_input for kw in ["学了", "完成", "做完", "看完"]):
            # TODO: 集成 StudyDatabase 后启用
            return "太棒了！我已经记录下你的学习进度了，继续加油！💪"
        else:
            return "学习记录功能正在开发中，敬请期待~"
            
    async def _process_chat_intent(self, user_input: str, intent: str) -> str:
        """处理普通聊天和情感陪伴"""
        system_prompt = """你是小助，一个温柔、专业、善于倾听的学习伙伴。

你的特点：
- 说话温柔亲切，像朋友一样
- 善于鼓励和支持
- 回答简洁有趣
- 适时给予学习建议

用户可能是学生，正在学习或需要情感支持。请用温暖的方式回应。"""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history[-4:])
        messages.append({"role": "user", "content": user_input})
        
        response = await self.ollama.generate_text(
            messages[-1]["content"],
            system_prompt=system_prompt,
            model_type="main"
        )
        return response
        
    async def _handle_audio_stream(self, message: dict):
        """处理音频流数据"""
        if not self.realtime_client or not self.realtime_client.is_connected:
            logger.warning("音频流数据但客户端未连接")
            return
            
        data = message.get("data", [])
        if isinstance(data, list) and len(data) > 0:
            # 转换为 bytes
            audio_bytes = struct.pack(f'<{len(data)}h', *data)
            await self.realtime_client.stream_audio(audio_bytes)
            
    async def _handle_start_audio(self, message: dict):
        """开始音频会话"""
        if self.realtime_client and self.realtime_client.is_connected:
            return
            
        self.current_mode = "audio"
        
        # 创建实时客户端
        qwen_config = self.config.get("ai_services", {}).get("qwen", {})
        self.realtime_client = QwenRealtimeClient(
            api_key=qwen_config.get("api_key", ""),
            model=qwen_config.get("realtime_model", "qwen-audio-chat")
        )
        
        # 设置回调
        self.realtime_client.on_transcript = self._on_transcript
        self.realtime_client.on_audio = self._on_audio_response
        self.realtime_client.on_text = self._on_text_response
        
        # 连接
        await self.realtime_client.connect()
        
        await self.send_message({
            "type": "system",
            "action": "audio_started",
            "message": "语音模式已开启"
        })
        
    async def _handle_stop_audio(self, message: dict):
        """停止音频会话"""
        if self.realtime_client:
            await self.realtime_client.close()
            self.realtime_client = None
            
        self.current_mode = "text"
        
        await self.send_message({
            "type": "system",
            "action": "audio_stopped",
            "message": "语音模式已关闭"
        })
        
    async def _handle_commit(self, message: dict):
        """提交音频缓冲区"""
        if self.realtime_client and self.realtime_client.is_connected:
            await self.realtime_client.commit_audio()
            
    async def _handle_get_schedule(self, message: dict):
        """获取日程"""
        schedules = await self.schedule_manager.get_today_schedules()
        await self.send_message({
            "type": "schedule",
            "data": schedules
        })
        
    async def _handle_tool_call(self, message: dict):
        """处理工具调用"""
        tool_name = message.get("tool")
        params = message.get("params", {})
        
        result = await self.schedule_tools.execute(tool_name, params)
        await self.send_message({
            "type": "tool_result",
            "tool": tool_name,
            "result": result
        })
        
    # 音频回调
    async def _on_transcript(self, text: str, is_final: bool):
        """收到语音转文字"""
        await self.send_message({
            "type": "transcript",
            "text": text,
            "is_final": is_final
        })
        
        if is_final and text.strip():
            # 保存对话
            await self.db.add_conversation("user", text)
            
    async def _on_audio_response(self, audio_data: bytes):
        """收到音频响应"""
        import base64
        audio_b64 = base64.b64encode(audio_data).decode()
        await self.send_message({
            "type": "audio",
            "data": audio_b64
        })
        
    async def _on_text_response(self, text: str, is_final: bool):
        """收到文字响应"""
        await self.send_message({
            "type": "assistant",
            "content": text,
            "is_final": is_final
        })
        
        if is_final and text.strip():
            await self.db.add_conversation("assistant", text)
            
    async def cleanup(self):
        """清理会话资源"""
        self.is_active = False
        if self.realtime_client:
            await self.realtime_client.close()
        logger.info(f"会话清理完成: {self.session_id}")


class WebSocketServer:
    """WebSocket 服务器 - 管理所有连接"""
    
    def __init__(
        self,
        config: dict,
        db_manager: DatabaseManager,
        ollama_client: OllamaClient,
        vector_memory: ConversationMemory,
        schedule_manager: ScheduleManager
    ):
        self.config = config
        self.db = db_manager
        self.ollama = ollama_client
        self.memory = vector_memory
        self.schedule_manager = schedule_manager
        
        # 活跃会话
        self.sessions: Dict[str, SessionManager] = {}
        
    async def handle_connection(self, websocket: WebSocket, session_id: str):
        """处理新连接"""
        await websocket.accept()
        logger.info(f"新连接: {session_id}")
        
        # 创建会话
        session = SessionManager(
            session_id=session_id,
            websocket=websocket,
            config=self.config,
            db_manager=self.db,
            ollama_client=self.ollama,
            vector_memory=self.memory,
            schedule_manager=self.schedule_manager
        )
        
        self.sessions[session_id] = session
        
        try:
            await session.initialize()
            
            # 消息循环
            while True:
                data = await websocket.receive_text()
                message = json.loads(data)
                await session.handle_message(message)
                
        except WebSocketDisconnect:
            logger.info(f"连接断开: {session_id}")
        except Exception as e:
            logger.error(f"WebSocket 错误: {e}")
        finally:
            await session.cleanup()
            if session_id in self.sessions:
                del self.sessions[session_id]
                
    def get_active_sessions(self) -> int:
        """获取活跃会话数"""
        return len(self.sessions)

