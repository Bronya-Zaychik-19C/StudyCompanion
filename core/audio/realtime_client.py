# -*- coding: utf-8 -*-
"""
StudyCompanion - Qwen Realtime 客户端
精简自 N.E.K.O 项目，专注于核心语音交互功能
"""

import asyncio
import websockets
import json
import base64
import time
import logging
from typing import Optional, Callable, Dict, Any, Awaitable
from enum import Enum

logger = logging.getLogger(__name__)


class TurnDetectionMode(Enum):
    """说话检测模式"""
    SERVER_VAD = "server_vad"  # 服务器端语音活动检测
    MANUAL = "manual"           # 手动控制


class QwenRealtimeClient:
    """
    Qwen Realtime API 客户端
    支持实时语音对话，低延迟交互
    """
    
    def __init__(
        self,
        api_key: str,
        base_url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/inference/",
        model: str = "qwen-audio-chat",
        voice: str = "longduoer",
        turn_detection_mode: TurnDetectionMode = TurnDetectionMode.SERVER_VAD,
        on_text_delta: Optional[Callable[[str, bool], Awaitable[None]]] = None,
        on_audio_delta: Optional[Callable[[bytes], Awaitable[None]]] = None,
        on_input_transcript: Optional[Callable[[str], Awaitable[None]]] = None,
        on_output_transcript: Optional[Callable[[str, bool], Awaitable[None]]] = None,
        on_connection_error: Optional[Callable[[str], Awaitable[None]]] = None,
        on_response_done: Optional[Callable[[], Awaitable[None]]] = None,
    ):
        """
        初始化 Qwen Realtime 客户端
        
        Args:
            api_key: Qwen API Key
            base_url: WebSocket URL
            model: 模型名称
            voice: 语音名称（longduoer, longshaonv, etc.）
            turn_detection_mode: 说话检测模式
            on_text_delta: 文本增量回调
            on_audio_delta: 音频增量回调
            on_input_transcript: 用户输入转录回调
            on_output_transcript: AI输出转录回调
            on_connection_error: 连接错误回调
            on_response_done: 响应完成回调
        """
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.ws = None
        self.turn_detection_mode = turn_detection_mode
        
        # 回调函数
        self.on_text_delta = on_text_delta
        self.on_audio_delta = on_audio_delta
        self.on_input_transcript = on_input_transcript
        self.on_output_transcript = on_output_transcript
        self.on_connection_error = on_connection_error
        self.on_response_done = on_response_done
        
        # 状态追踪
        self._current_response_id = None
        self._current_item_id = None
        self._is_responding = False
        self._is_first_text_chunk = False
        self._is_first_transcript_chunk = False
        self._print_input_transcript = False
        self._output_transcript_buffer = ""
        self._modalities = ["text", "audio"]
        self._audio_in_buffer = False
        
        logger.info(f"🎤 Qwen Realtime 客户端初始化完成")
        logger.info(f"   模型: {model}, 音色: {voice}")
    
    async def connect(self, instructions: str, native_audio: bool = True) -> None:
        """
        建立 WebSocket 连接
        
        Args:
            instructions: 系统指令（角色设定）
            native_audio: 是否使用原生音频输出
        """
        url = f"{self.base_url}?model={self.model}"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            self.ws = await websockets.connect(url, additional_headers=headers)
            logger.info(f"✅ WebSocket 连接成功")
            
            # 配置会话
            self._modalities = ["text", "audio"] if native_audio else ["text"]
            
            await self.update_session({
                "instructions": instructions,
                "modalities": self._modalities,
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "gummy-realtime-v1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500
                },
                "temperature": 0.6
            })
            
            logger.info(f"✅ 会话配置完成")
            
        except Exception as e:
            logger.error(f"💥 连接失败: {e}")
            if self.on_connection_error:
                await self.on_connection_error(str(e))
            raise
    
    async def send_event(self, event: Dict[str, Any]) -> None:
        """发送事件到服务器"""
        event['event_id'] = f"event_{int(time.time() * 1000)}"
        if self.ws:
            try:
                await self.ws.send(json.dumps(event))
            except Exception as e:
                logger.warning(f"⚠️ 发送事件失败: {e}")
                raise
    
    async def update_session(self, config: Dict[str, Any]) -> None:
        """更新会话配置"""
        event = {
            "type": "session.update",
            "session": config
        }
        await self.send_event(event)
    
    async def stream_audio(self, audio_chunk: bytes) -> None:
        """
        发送音频流到服务器
        
        Args:
            audio_chunk: PCM16 格式音频数据
        """
        audio_b64 = base64.b64encode(audio_chunk).decode()
        
        append_event = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64
        }
        await self.send_event(append_event)
    
    async def create_response(self, instructions: str = None) -> None:
        """请求生成响应"""
        event = {
            "type": "response.create",
            "response": {
                "modalities": self._modalities
            }
        }
        
        if instructions:
            event["response"]["instructions"] = instructions
        
        await self.send_event(event)
    
    async def cancel_response(self) -> None:
        """取消当前响应"""
        event = {
            "type": "response.cancel"
        }
        await self.send_event(event)
    
    async def handle_interruption(self):
        """处理用户打断"""
        if not self._is_responding:
            return
        
        logger.info("🛑 处理用户打断")
        
        if self._current_response_id:
            await self.cancel_response()
        
        self._is_responding = False
        self._current_response_id = None
        self._current_item_id = None
        self._output_transcript_buffer = ""
        self._is_first_transcript_chunk = True
    
    async def handle_messages(self) -> None:
        """处理服务器消息（主循环）"""
        try:
            if not self.ws:
                logger.error("💥 WebSocket 未连接")
                return
            
            async for message in self.ws:
                event = json.loads(message)
                event_type = event.get("type")
                
                # 错误处理
                if event_type == "error":
                    logger.error(f"💥 API 错误: {event['error']}")
                    if self.on_connection_error:
                        await self.on_connection_error(event['error'])
                    continue
                
                # 响应状态
                elif event_type == "response.done":
                    self._is_responding = False
                    self._current_response_id = None
                    self._current_item_id = None
                    self._output_transcript_buffer = ""
                    if self.on_response_done:
                        await self.on_response_done()
                
                elif event_type == "response.created":
                    self._current_response_id = event.get("response", {}).get("id")
                    self._is_responding = True
                    self._is_first_text_chunk = True
                    self._is_first_transcript_chunk = True
                    self._output_transcript_buffer = ""
                
                elif event_type == "response.output_item.added":
                    self._current_item_id = event.get("item", {}).get("id")
                
                # 用户语音检测
                elif event_type == "input_audio_buffer.speech_started":
                    logger.debug("🎤 检测到用户开始说话")
                    self._audio_in_buffer = True
                    if self._is_responding:
                        logger.info("🛑 用户打断，取消当前响应")
                        await self.handle_interruption()
                
                elif event_type == "input_audio_buffer.speech_stopped":
                    logger.debug("🎤 用户停止说话")
                    self._audio_in_buffer = False
                
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    self._print_input_transcript = True
                
                elif event_type in ["response.audio_transcript.done", "response.output_audio_transcript.done"]:
                    self._print_input_transcript = False
                    self._output_transcript_buffer = ""
                
                # 文本增量
                if event_type in ["response.text.delta", "response.output_text.delta"]:
                    if self.on_text_delta:
                        await self.on_text_delta(event["delta"], self._is_first_text_chunk)
                        self._is_first_text_chunk = False
                
                # 音频增量
                elif event_type in ["response.audio.delta", "response.output_audio.delta"]:
                    if self.on_audio_delta:
                        audio_bytes = base64.b64decode(event["delta"])
                        await self.on_audio_delta(audio_bytes)
                
                # 用户输入转录
                elif event_type == "conversation.item.input_audio_transcription.completed":
                    transcript = event.get("transcript", "")
                    if self.on_input_transcript:
                        await self.on_input_transcript(transcript)
                
                # AI 输出转录
                elif event_type in ["response.audio_transcript.done", "response.output_audio_transcript.done"]:
                    if self.on_output_transcript and self._is_first_transcript_chunk:
                        transcript = event.get("transcript", "")
                        if transcript:
                            await self.on_output_transcript(transcript, True)
                            self._is_first_transcript_chunk = False
                
                elif event_type in ["response.audio_transcript.delta", "response.output_audio_transcript.delta"]:
                    if self.on_output_transcript:
                        delta = event.get("delta", "")
                        if not self._print_input_transcript:
                            self._output_transcript_buffer += delta
                        else:
                            if self._output_transcript_buffer:
                                await self.on_output_transcript(
                                    self._output_transcript_buffer,
                                    self._is_first_transcript_chunk
                                )
                                self._is_first_transcript_chunk = False
                                self._output_transcript_buffer = ""
                            await self.on_output_transcript(delta, self._is_first_transcript_chunk)
                            self._is_first_transcript_chunk = False
        
        except websockets.exceptions.ConnectionClosedOK:
            logger.info("✅ 连接正常关闭")
        except websockets.exceptions.ConnectionClosedError as e:
            error_msg = str(e)
            logger.error(f"💥 连接异常关闭: {error_msg}")
            if self.on_connection_error:
                await self.on_connection_error(error_msg)
        except Exception as e:
            logger.error(f"💥 消息处理错误: {e}")
            raise
    
    async def close(self) -> None:
        """关闭 WebSocket 连接"""
        if self.ws:
            try:
                await self.ws.close()
                logger.info("✅ WebSocket 已关闭")
            except Exception as e:
                logger.error(f"💥 关闭连接失败: {e}")
            finally:
                self.ws = None


