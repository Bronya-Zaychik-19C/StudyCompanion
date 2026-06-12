# -*- coding: utf-8 -*-
"""
StudyCompanion - 考研 AI 学习私教 v3.5
多会话持久化 | 数学一 | 英语一 | 408
"""

import asyncio, json, logging, uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from uvicorn import Config, Server

from core.memory.database import DatabaseManager
from core.ai.qwen_client import QwenChatClient
from core.knowledge.engine import KnowledgeBase
from features.feynman.engine import FeynmanEngine
from features.diagnosis.engine import DiagnosisEngine
from features.exam.engine import ExamEngine
from features.exam.question_bank import QuestionBank
from features.roadmap.engine import RoadmapEngine
from config.personas import get_system_prompt, get_feynman_hook, get_persona_list

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class StudyCompanionApp:
    def __init__(self, config_path="config/default_config.json"):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        self.app = FastAPI(title="StudyCompanion")
        self.db = None; self.ai = None; self.kb = None
        self.feynman = None; self.diagnosis = None; self.exam = None; self.roadmap = None; self.qbank = None
        self.ws_sessions = {}  # ws_id -> {ws, session_id, feynman_sid, mode, persona, history}
        logger.info("🎓 StudyCompanion v3.6 初始化中...")

    async def initialize(self):
        db_path = self.config.get('database', {}).get('path', 'data/sqlite/study_companion.db')
        self.db = DatabaseManager(db_path)
        await self.db.init_database()

        ai_cfg = self.config.get('ai', {})
        provider = ai_cfg.get('provider', 'deepseek')
        prov = ai_cfg.get(provider, {})
        api_key = prov.get('api_key', '')
        if api_key and not api_key.startswith('sk-你的'):
            self.ai = QwenChatClient(api_key=api_key, model=prov.get('model', 'deepseek-chat'),
                                      base_url=prov.get('base_url', 'https://api.deepseek.com/v1/chat/completions'))
            logger.info(f"✅ AI: {provider}/{prov.get('model')}")
        else:
            logger.warning("⚠️ 未配置 API Key")

        self.kb = KnowledgeBase()
        self.kb.load_subject('math_one.json')
        self.feynman = FeynmanEngine(ai_client=self.ai, knowledge_base=self.kb, question_bank=self.qbank)
        self.diagnosis = DiagnosisEngine(ai_client=self.ai, knowledge_base=self.kb)
        self.exam = ExamEngine(ai_client=self.ai, knowledge_base=self.kb)
        self.roadmap = RoadmapEngine(ai_client=self.ai, knowledge_base=self.kb)
        self.qbank = QuestionBank(knowledge_base=self.kb)
        logger.info("✅ 全部引擎就绪")

    # ==================== HTTP API ====================

    def setup_routes(self):
        @self.app.get("/")
        async def index():
            return HTMLResponse(content=HTML)

        @self.app.get("/api/health")
        async def health():
            return {"status": "ok", "version": "3.5.0", "ai": self.ai is not None}

        @self.app.get("/api/sessions")
        async def list_sessions():
            sessions = await self.db.list_sessions()
            return JSONResponse(sessions)

        @self.app.post("/api/sessions")
        async def create_session():
            sid = str(uuid.uuid4())[:8]
            await self.db.create_session(sid)
            return JSONResponse({"id": sid, "title": "新对话"})

        @self.app.get("/api/sessions/{sid}")
        async def get_session(sid: str):
            s = await self.db.get_session(sid)
            if not s:
                return JSONResponse({"error": "not found"}, status_code=404)
            msgs = await self.db.load_messages(sid)
            return JSONResponse({"session": s, "messages": msgs})

        @self.app.delete("/api/sessions/{sid}")
        async def delete_session(sid: str):
            await self.db.delete_session(sid)
            return JSONResponse({"ok": True})

        @self.app.websocket("/ws")
        async def ws(websocket: WebSocket):
            await self._handle_ws(websocket)

    # ==================== WebSocket ====================

    async def _handle_ws(self, ws: WebSocket):
        await ws.accept()
        wsid = str(id(ws))
        self.ws_sessions[wsid] = {
            'ws': ws, 'session_id': None, 'feynman_sid': None,
            'mode': 'chat', 'persona': 'mentor', 'history': []
        }
        logger.info(f"🔌 {wsid}")
        try:
            while True:
                data = await ws.receive_json()
                await self._route(wsid, data)
        except WebSocketDisconnect:
            pass
        finally:
            self.ws_sessions.pop(wsid, None)

    async def _route(self, wsid, data):
        s = self.ws_sessions.get(wsid)
        ws = s['ws']
        mtype = data.get('type', 'text')

        if mtype == 'session_load':
            sid = data.get('session_id')
            if sid:
                s['session_id'] = sid
                msgs = await self.db.load_messages(sid)
                s['history'] = [{"role": m['role'], "content": m['content']} for m in msgs]
                s['mode'] = 'chat'
                await ws.send_json({'type': 'history_loaded', 'messages': msgs, 'session_id': sid})
            return

        if mtype == 'session_new':
            sid = str(uuid.uuid4())[:8]
            s['session_id'] = sid
            s['history'] = []; s['mode'] = 'chat'
            await self.db.create_session(sid)
            await ws.send_json({'type': 'session_created', 'session_id': sid, 'title': '新对话'})
            return

        if mtype == 'session_delete':
            sid = data.get('session_id') or s.get('session_id')
            if sid:
                await self.db.delete_session(sid)
                if s['session_id'] == sid:
                    s['session_id'] = None; s['history'] = []
                await ws.send_json({'type': 'session_deleted', 'session_id': sid})
            return

        if mtype == 'persona_set':
            s['persona'] = data.get('persona', 'mentor')
            await ws.send_json({'type': 'system_msg', 'content': '人设已切换'})
            return

        # 以下消息需要 session
        if not s.get('session_id'):
            sid = str(uuid.uuid4())[:8]
            s['session_id'] = sid
            await self.db.create_session(sid)
            await ws.send_json({'type': 'session_created', 'session_id': sid, 'title': '新对话'})

        content = data.get('content', '')
        subject = data.get('subject', 'math_one')

        if mtype == 'text':
            await self._handle_text(wsid, content, subject, data.get('chapter'))
        elif mtype == 'feynman_start':
            await self._start_feynman(wsid, data.get('concept', content), subject)
        elif mtype == 'feynman_end':
            await self._end_feynman(wsid)
        elif mtype == 'diagnosis_start':
            await self._start_diagnosis(wsid, subject, data.get('chapter'))
        elif mtype == 'diagnosis_answer':
            await self._handle_diagnosis_answer(wsid, data.get('answer'))
        elif mtype == 'exam_generate':
            await self._gen_exam(wsid, subject, data.get('count', 5), data.get('chapter'))
        elif mtype == 'exam_hotspots':
            await self._predict_hotspots(wsid, subject, data.get('chapter'))
        elif mtype == 'roadmap_recommend':
            await self._get_recommendations(wsid, subject)
        elif mtype == 'roadmap_plan':
            await self._get_study_plan(wsid, subject, data.get('days', 30))
        elif mtype == 'qbank_topic':
            await self._qbank_by_topic(wsid, data.get('topic_id', ''))
        elif mtype == 'qbank_years':
            await self._qbank_years(wsid)
        elif mtype == 'qbank_hot':
            await self._qbank_hot(wsid)
        elif mtype == 'qbank_paper':
            await self._qbank_paper(wsid, data.get('year'))
        elif mtype == 'qbank_question':
            await self._qbank_question(wsid, data.get('year'), data.get('q_num'))

    # ==================== Text Handler ====================

    async def _handle_text(self, wsid, content, subject, chapter=None):
        s = self.ws_sessions[wsid]; ws = s['ws']

        if s.get('mode') == 'feynman' and s.get('feynman_sid'):
            await ws.send_json({'type': 'stream_start', 'role': 'assistant'})
            full = ""
            async for token in self.feynman.process_response_stream(s['feynman_sid'], content):
                full += token; await ws.send_json({'type': 'stream_delta', 'content': token})
            await ws.send_json({'type': 'stream_end'})
            await self._save_msg(s, 'user', content)
            await self._save_msg(s, 'assistant', full)
            return

        if not self.ai:
            await ws.send_json({'type': 'error', 'content': '请配置 API Key'})
            return

        await self._save_msg(s, 'user', content)
        # 自动标题
        if len(s.get('history', [])) == 0 and s.get('session_id'):
            await self.db.auto_title(s['session_id'], content)

        try:
            intent = await self.ai.classify_intent(content)
            itype = intent.get('intent', 'chat')
            if itype == 'feynman':
                concept = intent.get('concept', content)
                if chapter:
                    ch_data = self.kb.get_chapter(subject, chapter - 1) if self.kb else None
                    if ch_data: concept = f"{ch_data['name']}中的{concept}"
                await self._start_feynman(wsid, concept, subject)
            else:
                sp = get_system_prompt(s.get('persona', 'mentor'))
                history = s.get('history', [])
                history.append({"role": "user", "content": content})
                if len(history) > 20: history = history[-20:]
                msgs = [{"role": "system", "content": sp}] + history[-12:]
                full = ""
                await ws.send_json({'type': 'stream_start', 'role': 'assistant'})
                async for token in self.ai.chat_stream(msgs, max_tokens=4096):
                    full += token; await ws.send_json({'type': 'stream_delta', 'content': token})
                await ws.send_json({'type': 'stream_end'})
                history.append({"role": "assistant", "content": full})
                if len(history) > 20: history = history[-20:]
                s['history'] = history
                await self._save_msg(s, 'assistant', full)
        except Exception as e:
            logger.error(f"处理失败: {e}")
            await ws.send_json({'type': 'stream_delta', 'content': '出错了，请重试'})
            await ws.send_json({'type': 'stream_end'})

    async def _save_msg(self, s, role, content):
        if s.get('session_id') and content:
            await self.db.save_message(s['session_id'], role, content)

    # ==================== Feynman ====================

    async def _start_feynman(self, wsid, concept, subject):
        s = self.ws_sessions[wsid]; ws = s['ws']
        if s.get('feynman_sid'):
            self.feynman.end_session(s['feynman_sid'])
        topic_id = None
        if self.kb:
            matches = self.kb.search_topics(subject, concept)
            if matches: topic_id = matches[0]['topic'].get('id')
        fsid = f"{wsid}_{concept}"
        s['feynman_sid'] = fsid; s['mode'] = 'feynman'
        prior = s.get('history', [])
        await ws.send_json({'type': 'stream_start', 'role': 'assistant'})
        full = ""
        async for token in self.feynman.start_session_stream(fsid, concept, subject, topic_id, s.get('persona', 'mentor'), prior):
            full += token; await ws.send_json({'type': 'stream_delta', 'content': token})
        await ws.send_json({'type': 'stream_end'})
        await self._save_msg(s, 'user', f"学习：{concept}")
        await self._save_msg(s, 'assistant', full)

    async def _end_feynman(self, wsid):
        s = self.ws_sessions[wsid]
        if s.get('feynman_sid'):
            feynman_session = self.feynman.sessions.get(s['feynman_sid'])
            if feynman_session:
                h = s.get('history', [])
                h.append({"role": "system", "content": f"[费曼: {feynman_session.get('concept','')}]"})
                h.extend(feynman_session['history'][-6:])
                if len(h) > 20: h = h[-20:]
                s['history'] = h
            self.feynman.end_session(s['feynman_sid'])
            s['feynman_sid'] = None
        s['mode'] = 'chat'
        await s['ws'].send_json({'type': 'system_msg', 'content': '已退出费曼学习模式'})

    # ==================== Diagnosis / Exam / Roadmap ====================

    async def _start_diagnosis(self, wsid, subject, chapter=None):
        s = self.ws_sessions[wsid]; ws = s['ws']
        diag_sid = f"{wsid}_diag"
        s['diag_sid'] = diag_sid
        q = await self.diagnosis.start_diagnosis(diag_sid, subject, chapter_index=chapter - 1 if chapter else None)
        if q.get('done'): await self._send_report(s, q.get('summary'))
        else: await ws.send_json({**q, 'type': 'question'})

    async def _handle_diagnosis_answer(self, wsid, answer):
        s = self.ws_sessions[wsid]; ws = s['ws']
        if not s.get('diag_sid'): return
        fb = await self.diagnosis.submit_answer(s['diag_sid'], answer)
        await ws.send_json({'type': 'system_msg', 'content': fb.get('feedback', '') + '\n' + fb.get('progress', '')})
        q = await self.diagnosis.next_question(s['diag_sid'])
        if q.get('done'):
            summary = q.get('summary')
            if summary:
                await ws.send_json({**summary, 'type': 'report'})
                if summary.get('weak_points'):
                    for w in summary['weak_points']:
                        self.roadmap.add_weak(wsid, w.get('id', ''))
        else:
            await ws.send_json({**q, 'type': 'question'})

    async def _send_report(self, s, summary):
        if summary: await s['ws'].send_json({**summary, 'type': 'report'})

    async def _gen_exam(self, wsid, subject, count, chapter=None):
        s = self.ws_sessions[wsid]
        exam = await self.exam.generate_mock_exam(subject, count, chapter_index=chapter - 1 if chapter else None)
        await s['ws'].send_json({**exam, 'type': 'exam'})

    async def _predict_hotspots(self, wsid, subject, chapter=None):
        s = self.ws_sessions[wsid]
        hotspots = await self.exam.predict_hotspots(subject, chapter_index=chapter - 1 if chapter else None)
        await s['ws'].send_json({**hotspots, 'type': 'hotspots'})

    async def _get_recommendations(self, wsid, subject):
        s = self.ws_sessions[wsid]
        recs = self.roadmap.get_recommendations(wsid, subject, 10)
        lines = ['推荐学习路径：\n']
        for i, r in enumerate(recs):
            tags = ''; tags += ' [薄弱]' if r.get('is_weak') else ''; tags += ' [高频]' if r.get('weight') == '高频' else ''
            lines.append(f"{i+1}. {r['name']} [{r['chapter']}] 难度:{'*'*r.get('difficulty',3)}{tags}")
        await s['ws'].send_json({'role': 'assistant', 'content': '\n'.join(lines)})

    async def _get_study_plan(self, wsid, subject, days):
        s = self.ws_sessions[wsid]
        plan = await self.roadmap.generate_study_plan(wsid, subject, days)
        await s['ws'].send_json({**plan, 'type': 'plan'})

    async def _qbank_by_topic(self, wsid, topic_id):
        s = self.ws_sessions[wsid]
        ctx = self.qbank.build_exam_context(topic_id)
        await s['ws'].send_json({'role': 'assistant', 'content': f"📚 {ctx}"})

    async def _qbank_years(self, wsid):
        s = self.ws_sessions[wsid]
        years = self.qbank.get_years()
        await s['ws'].send_json({'role': 'assistant', 'content': f"📚 已索引真题年份: {', '.join(str(y) for y in years)}"})

    async def _qbank_hot(self, wsid):
        s = self.ws_sessions[wsid]
        hot = self.qbank.get_hot_topics()
        lines = ["📊 高频考点统计:\n"]
        for h in hot[:15]:
            lines.append(f"{h['name']} [{h['chapter']}] — 出现{h['frequency']}次")
        await s['ws'].send_json({'role': 'assistant', 'content': '\n'.join(lines)})

    async def _qbank_paper(self, wsid, year):
        s = self.ws_sessions[wsid]; ws = s['ws']
        if not year: year = 2024
        questions = self.qbank.get_exam(int(year))
        if not questions:
            await ws.send_json({'role': 'system', 'content': f'{year}年真题数据未索引'})
            return

        await ws.send_json({'type': 'system_msg', 'role': 'system', 'content': f'📋 正在提取 {year} 年真题（共{len(questions)}题）...'})

        # Try to extract actual text from answer PDF
        pdf_text = ""
        try:
            import fitz, os
            fname = f'02.1987-2025年数一真题答案解析/{year}数学一解析.pdf'
            if os.path.exists(fname):
                doc = fitz.open(fname)
                pdf_text = ''.join(page.get_text() for page in doc)
        except Exception as e:
            logger.warning(f"Cannot read answer PDF: {e}")

        # Build question list with real answer data from PDF
        qlist = []
        for q in questions:
            topic_name = q['topic_ids'][0] if q['topic_ids'] else ''
            if self.kb and q['topic_ids']:
                match = self.kb.get_topic('math_one', q['topic_ids'][0])
                if match: topic_name = match['topic'].get('name', topic_name)

            # Try to find real answer text from PDF
            answer_text = ""
            if pdf_text:
                import re
                pat = rf'(?:^|\n)\s*[\(（]?{q["q_num"]}[\)）]?\s*【答案】\s*([^\n]*?)\n'
                m = re.search(pat, pdf_text)
                if m: answer_text = m.group(1).strip()[:50]

            qlist.append({
                'num': q['q_num'], 'type': q['type'], 'topic': topic_name,
                'keywords': q['keywords'], 'answer': answer_text
            })

        # Build a structured reference
        lines = [f"## {year}年数学一真题\n"]
        lines.append(f"共{len(questions)}题 | 数据来源：39年真题索引\n")
        lines.append("---\n")

        sel = [q for q in qlist if q['type'] == '选择题']
        fill = [q for q in qlist if q['type'] == '填空题']
        solve = [q for q in qlist if q['type'] == '解答题']

        if sel:
            lines.append(f"### 选择题（{len(sel)}题）\n")
            for q in sel:
                ans = f" → {q['answer']}" if q['answer'] else ""
                lines.append(f"**第{q['num']}题** [{q['topic']}]{ans}  ")
            lines.append("")

        if fill:
            lines.append(f"### 填空题（{len(fill)}题）\n")
            for q in fill:
                ans = f" → {q['answer']}" if q['answer'] else ""
                lines.append(f"**第{q['num']}题** [{q['topic']}]{ans}  ")
            lines.append("")

        if solve:
            lines.append(f"### 解答题（{len(solve)}题）\n")
            for q in solve:
                ans = f" → {q['answer']}" if q['answer'] else ""
                lines.append(f"**第{q['num']}题** [{q['topic']}]{ans}  ")
            lines.append("")

        lines.append("---")
        lines.append(f"\n> 以上为{year}年数学一真题的**题目结构**和**官方答案**。")
        lines.append(f"> 如需查看具体题目内容，请告诉我题号（如\"显示第5题\"），我将从解析中提取。")
        lines.append(f"> 如需做完整真题卷，请打开 `01.1987-2025年数一真题合集/{year}年考研数学（一）真题.pdf`")

        await ws.send_json({'role': 'assistant', 'content': '\n'.join(lines)})

    async def _qbank_question(self, wsid, year, q_num):
        s = self.ws_sessions[wsid]; ws = s['ws']
        if not year or not q_num:
            await ws.send_json({'role': 'system', 'content': '请指定年份和题号'})
            return

        # Extract from answer PDF
        try:
            import fitz, os, re
            fname = f'02.1987-2025年数一真题答案解析/{year}数学一解析.pdf'
            if not os.path.exists(fname):
                await ws.send_json({'role': 'system', 'content': f'{year}年解析PDF不存在'})
                return

            doc = fitz.open(fname)
            full = ''.join(page.get_text() for page in doc)

            # Find content around this question
            pat = rf'(?:^|\n)\s*[\(（]?{q_num}[\)）]?\s*【答案】([^\n]*)\n(.*?)(?=\n\s*[\(（]?\d{{1,2}}[\)）]?\s*【答案】|\Z)'
            m = re.search(pat, full, re.S)
            if not m:
                await ws.send_json({'role': 'system', 'content': f'未找到{year}年第{q_num}题'})
                return

            answer = m.group(1).strip()[:50]
            body = m.group(2).strip()

            # Find 【解】 marker to split problem from solution
            sol_start = body.find('【解】')
            problem_text = body[:sol_start].strip() if sol_start > 0 else ''
            solution_text = body[sol_start:].strip() if sol_start > 0 else body

            # Only clean up if solution text is available and not empty
            if len(solution_text) > 10:
                # Have AI clean up the garbled OCR text
                prompt = (
                    f"以下是{year}年数学一真题第{q_num}题的解析原文（从扫描版PDF OCR提取，"
                    f"存在乱码和数学符号错误）。请还原出：\n"
                    f"1. 这道题的完整原题内容\n"
                    f"2. 正确答案（已知答案为：{answer}）\n"
                    f"3. 简要解题思路\n\n"
                    f"OCR原文：\n{solution_text[:2000]}\n\n"
                    f"请用Markdown格式输出，数学公式用$$...$$。不要编造，根据OCR文本还原。"
                )
                await ws.send_json({'type': 'stream_start', 'role': 'assistant'})
                full_resp = ""
                async for token in self.ai.chat_stream([
                    {"role": "system", "content": "你是考研数学老师。根据OCR文本还原真题。不要编造。"},
                    {"role": "user", "content": prompt}
                ], max_tokens=4096):
                    full_resp += token; await ws.send_json({'type': 'stream_delta', 'content': token})
                await ws.send_json({'type': 'stream_end'})
            else:
                await ws.send_json({'role': 'system', 'content': f'{year}年第{q_num}题解析文本为空，请查看原始PDF'})

        except Exception as e:
            logger.error(f"提取真题失败: {e}")
            await ws.send_json({'role': 'system', 'content': f'提取失败: {e}'})

    async def run(self, host="0.0.0.0", port=48911):
        self.setup_routes(); await self.initialize()
        await Server(Config(app=self.app, host=host, port=port)).serve()


# ==================== HTML ====================

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><title>StudyCompanion - 考研AI私教</title>
<script>window.MathJax={tex:{inlineMath:[["$","$"]],displayMath:[["$$","$$"]]},svg:{fontCache:"global"}};</script>
<script src="https://unpkg.com/mathjax@3/es5/tex-svg.js"></script>
<script src="https://cdn.bootcdn.net/ajax/libs/mathjax/3.2.2/es5/tex-svg.js"></script>
<script>
function renderMath(el) {
    if (!el) return;
    var tries = 0;
    function tryTypeset() {
        tries++;
        if (window.MathJax && MathJax.typesetPromise) {
            MathJax.typesetPromise([el]).catch(function(){});
        } else if (tries < 15) {
            setTimeout(tryTypeset, 300);
        }
    }
    tryTypeset();
}
</script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Microsoft YaHei',sans-serif;background:#0f172a;color:#e2e8f0;height:100vh;overflow:hidden;display:flex}
.sidebar{width:280px;background:rgba(255,255,255,0.03);border-right:1px solid rgba(255,255,255,0.08);display:flex;flex-direction:column;height:100vh}
.sidebar-header{padding:16px;border-bottom:1px solid rgba(255,255,255,0.06);flex-shrink:0}
.sidebar-header h2{font-size:1.1em;background:linear-gradient(90deg,#4facfe,#00f2fe);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.sidebar-header .subtitle{font-size:.75em;color:rgba(255,255,255,0.4);margin-top:2px}
.sidebar-actions{padding:10px 16px;display:flex;gap:8px;flex-shrink:0}
.btn-new{flex:1;padding:8px;background:linear-gradient(135deg,#3b82f6,#2563eb);color:white;border:none;border-radius:8px;cursor:pointer;font-size:.85em}
.btn-new:hover{opacity:.9}
.conv-list{flex:1;overflow-y:auto;padding:8px}
.conv-item{padding:10px 12px;border-radius:8px;cursor:pointer;margin-bottom:4px;transition:all .15s;display:flex;justify-content:space-between;align-items:center;font-size:.85em}
.conv-item:hover{background:rgba(255,255,255,0.06)}
.conv-item.active{background:rgba(59,130,246,0.15);border:1px solid rgba(59,130,246,0.3)}
.conv-item .title{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:rgba(255,255,255,0.8)}
.conv-item .del-btn{opacity:0;color:#f87171;cursor:pointer;padding:2px 6px;font-size:.75em;border:none;background:none}
.conv-item:hover .del-btn{opacity:1}
.sidebar-footer{padding:12px 16px;border-top:1px solid rgba(255,255,255,0.06);font-size:.78em;flex-shrink:0}
.sidebar-footer select{padding:6px 8px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);border-radius:6px;color:white;width:100%;margin-top:6px}
.chapter-sidebar{width:200px;background:rgba(255,255,255,0.02);border-right:1px solid rgba(255,255,255,0.06);overflow-y:auto;padding:8px;flex-shrink:0;height:100vh}
.main{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh}
.header{padding:12px 20px;background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.header h1{font-size:1.1em}
.tabs{display:flex;gap:4px;padding:0 20px;background:rgba(255,255,255,0.02);border-bottom:1px solid rgba(255,255,255,0.06);flex-shrink:0}
.tab{padding:10px 16px;cursor:pointer;font-size:.85em;border-bottom:2px solid transparent;color:rgba(255,255,255,0.5);transition:all .2s}
.tab:hover{color:white}.tab.active{border-bottom-color:#3b82f6;color:white}
.chat-area{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:10px}
.msg{padding:10px 14px;border-radius:12px;max-width:85%;line-height:1.6;animation:fadeIn .25s;font-size:.92em}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.msg.user{background:linear-gradient(135deg,#3b82f6,#2563eb);align-self:flex-end}
.msg.assistant{background:rgba(255,255,255,0.08);align-self:flex-start}
.msg.system{background:rgba(251,191,36,0.1);color:#fbbf24;align-self:center;font-size:.78em;text-align:center}
.msg.question{background:rgba(79,172,254,0.12);border:1px solid rgba(79,172,254,0.25);align-self:flex-start}
.msg.question .q-title{font-weight:bold;margin-bottom:6px;color:#4facfe}
.msg.question .options{margin-top:6px;display:flex;flex-direction:column;gap:3px}
.msg.question .opt{padding:5px 8px;background:rgba(255,255,255,0.05);border-radius:4px;cursor:pointer;transition:all .15s;font-size:.88em}
.msg.question .opt:hover{background:rgba(59,130,246,0.2)}
.msg.question .opt.chosen{background:rgba(59,130,246,0.3);border:1px solid #3b82f6}
.mode-bar{padding:6px 20px;font-size:.78em;text-align:center;color:rgba(255,255,255,0.5);flex-shrink:0}
.mode-bar b{color:#4facfe}.mode-bar a{color:#fbbf24;text-decoration:none}
#actionButtons{padding:0 20px 6px;flex-shrink:0}
.input-area{padding:14px 20px;background:rgba(255,255,255,0.03);border-top:1px solid rgba(255,255,255,0.08);display:flex;gap:8px;flex-shrink:0}
#textInput{flex:1;padding:10px 16px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);border-radius:20px;color:white;font-size:.9em;outline:none}
#textInput:focus{border-color:#3b82f6}
button{padding:8px 16px;border:none;border-radius:16px;cursor:pointer;font-size:.85em;transition:all .2s;white-space:nowrap}
.btn-primary{background:linear-gradient(135deg,#3b82f6,#2563eb);color:white}.btn-primary:hover{opacity:.9}
.btn-secondary{background:rgba(255,255,255,0.08);color:white;border:1px solid rgba(255,255,255,0.15)}.btn-secondary:hover{background:rgba(255,255,255,0.12)}
.conn-dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:4px}.conn-dot.ok{background:#4ade80}.conn-dot.warn{background:#fbbf24}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-header"><h2>🎓 StudyCompanion</h2><div class="subtitle">考研AI私教 v3.5</div></div>
    <div class="sidebar-actions"><button class="btn-new" onclick="newSession()">+ 新对话</button></div>
    <div class="conv-list" id="convList"></div>
    <div class="sidebar-footer">
        <div style="display:flex;align-items:center;gap:6px"><span id="connDot" class="conn-dot warn"></span><span id="connText" style="font-size:.8em">未连接</span></div>
        <select id="personaSelect" onchange="setPersona(this.value)" style="margin-top:6px">
            <option value="professional">👨‍🏫 专业教师</option><option value="mentor" selected>🧑‍🏫 温和导师</option>
            <option value="comrade">🤝 研友</option><option value="concise">⚡ 极简模式</option>
        </select>
    </div>
</div>
<div class="chapter-sidebar" id="chapterSidebar"></div>
<div class="main">
    <div class="header"><h1 id="pageTitle">📐 数学一</h1></div>
    <div class="tabs">
        <div class="tab active" onclick="switchTab('feynman')">🧠 费曼</div>
        <div class="tab" onclick="switchTab('diagnosis')">🔍 诊断</div>
        <div class="tab" onclick="switchTab('paper')">📋 真题</div>
        <div class="tab" onclick="switchTab('exam')">📝 模拟</div>
        <div class="tab" onclick="switchTab('roadmap')">🗺️ 路径</div>
    </div>
    <div class="mode-bar" id="modeBar">选择左侧章节或输入知识点开始学习</div>
    <div class="chat-area" id="chatBox"></div>
    <div id="actionButtons" style="padding:0 20px 6px"></div>
    <div class="input-area">
        <input id="textInput" placeholder="输入知识点，如：数列极限夹逼定理..." autocomplete="off">
        <button class="btn-primary" onclick="sendMsg()">发送</button>
        <button class="btn-secondary" onclick="openMenu()">⚡</button>
    </div>
</div>
<script>
var ws,currentSession=null,currentChapter=null,currentTab='feynman',feynmanActive=false,streamDiv=null,streamContent='';
var chapters=[{idx:1,n:'函数与极限'},{idx:2,n:'导数与微分'},{idx:3,n:'中值定理与导数应用'},{idx:4,n:'不定积分'},{idx:5,n:'定积分'},{idx:6,n:'定积分的应用'},{idx:7,n:'微分方程'},{idx:8,n:'向量与空间解析几何'},{idx:9,n:'多元函数微分'},{idx:10,n:'重积分'},{idx:11,n:'曲线积分与曲面积分'},{idx:12,n:'无穷级数'},{idx:13,n:'行列式'},{idx:14,n:'矩阵'},{idx:15,n:'n维向量与线性方程组'},{idx:16,n:'特征值与特征向量'},{idx:17,n:'二次型'},{idx:18,n:'随机事件与概率'},{idx:19,n:'随机变量及其分布'},{idx:20,n:'多维随机变量'},{idx:21,n:'数字特征'},{idx:22,n:'大数定律与中心极限定理'},{idx:23,n:'数理统计'}];

function renderChapters(){var h='<div class="ch-label">数学一 章节</div>';chapters.forEach(function(c){h+='<div class="chapter-item'+(currentChapter===c.idx?' active':'')+'" onclick="selCh('+c.idx+')">Ch.'+c.idx+' '+c.n+'</div>'});document.getElementById('chapterSidebar').innerHTML=h}
function selCh(i){currentChapter=i;renderChapters()}
function switchTab(t){currentTab=t;feynmanActive=false;document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('active')});event.target.classList.add('active');document.getElementById('actionButtons').innerHTML='';var m={paper:getYearOptions(),diagnosis:'<button class="btn-secondary" onclick="startDiag()">🔍 诊断测试</button> <button class="btn-secondary" onclick="startDiagCh()">按章节诊断</button>',exam:'<button class="btn-secondary" onclick="genExam()">📝 模拟卷</button> <button class="btn-secondary" onclick="hotspots()">🎯 考点预测</button>',roadmap:'<button class="btn-secondary" onclick="getPlan(30)">🗓️ 30天</button> <button class="btn-secondary" onclick="getPlan(60)">🗓️ 60天</button> <button class="btn-secondary" onclick="getRecs()">📋 推荐路径</button>'};document.getElementById('actionButtons').innerHTML=m[t]||''}
function setPersona(p){ws.send(JSON.stringify({type:'persona_set',persona:p}))}
function openMenu(){document.getElementById('actionButtons').innerHTML='<button class="btn-secondary" onclick="startDiag()">诊断</button> <button class="btn-secondary" onclick="genExam()">模拟卷</button> <button class="btn-secondary" onclick="hotspots()">考点预测</button> <button class="btn-secondary" onclick="getRecs()">推荐路径</button> <button class="btn-secondary" onclick="exitFeynman()">退出费曼</button>'}

function connect(){
    ws=new WebSocket('ws://'+location.host+'/ws');
    ws.onopen=function(){document.getElementById('connDot').className='conn-dot ok';document.getElementById('connText').innerText='已连接';loadSessions()}
    ws.onclose=function(){document.getElementById('connDot').className='conn-dot warn';document.getElementById('connText').innerText='未连接';setTimeout(connect,3000)}
    ws.onmessage=function(e){
        var d=JSON.parse(e.data);
        if(d.type==='stream_start'){startStream(d.role)}
        else if(d.type==='stream_delta'){appendStream(d.content)}
        else if(d.type==='stream_end'){endStream()}
        else if(d.type==='session_created'){currentSession=d.session_id;loadSessions()}
        else if(d.type==='session_deleted'){currentSession=null;document.getElementById('chatBox').innerHTML='';loadSessions()}
        else if(d.type==='history_loaded'){loadHistory(d.messages);currentSession=d.session_id}
        else if(d.type==='question'){renderQ(d)}
        else if(d.type==='report'){renderReport(d)}
        else if(d.type==='exam'){renderExam(d)}
        else if(d.type==='hotspots'){renderHotspots(d)}
        else if(d.type==='plan'){renderPlan(d)}
        else if(d.type==='system_msg'){addMsg('system',d.content)}
        else{addMsg(d.role||'assistant',d.content)}
    }
}
function addMsg(role,content){var b=document.getElementById('chatBox');var d=document.createElement('div');d.className='msg '+role;d.innerHTML=content.replace(/\n/g,'<br>');b.appendChild(d);b.scrollTop=b.scrollHeight;renderMath(d)}
function startStream(role){var b=document.getElementById('chatBox');streamDiv=document.createElement('div');streamDiv.className='msg '+role;streamContent='';b.appendChild(streamDiv);b.scrollTop=b.scrollHeight}
function appendStream(c){if(!streamDiv)return;streamContent+=c;streamDiv.innerHTML=streamContent.replace(/\n/g,'<br>');document.getElementById('chatBox').scrollTop=document.getElementById('chatBox').scrollHeight}
function endStream(){if(!streamDiv)return;renderMath(streamDiv);streamDiv=null;streamContent=''}

async function loadSessions(){var r=await fetch('/api/sessions');var data=await r.json();var h='';data.forEach(function(s){h+='<div class="conv-item'+(s.id===currentSession?' active':'')+'" onclick="loadSession(\''+s.id+'\')"><span class="title">'+escHtml(s.title)+'</span><button class="del-btn" onclick="event.stopPropagation();delSession(\''+s.id+'\')">✕</button></div>'});document.getElementById('convList').innerHTML=h||'<div style="color:rgba(255,255,255,0.3);font-size:.8em;text-align:center;padding:20px">暂无对话</div>'}
function escHtml(s){var d=document.createElement('div');d.innerText=s;return d.innerHTML}
function newSession(){ws.send(JSON.stringify({type:'session_new'}));document.getElementById('chatBox').innerHTML='';feynmanActive=false;updateBar()}
function loadSession(sid){if(currentSession===sid)return;ws.send(JSON.stringify({type:'session_load',session_id:sid}));feynmanActive=false;updateBar()}
function delSession(sid){if(!confirm('删除此对话？'))return;ws.send(JSON.stringify({type:'session_delete',session_id:sid}))}
function loadHistory(msgs){var b=document.getElementById('chatBox');b.innerHTML='';msgs.forEach(function(m){addMsg(m.role,m.content)})}
function sendMsg(){var i=document.getElementById('textInput');var t=i.value.trim();if(!t||!ws)return;addMsg('user',t);i.value='';ws.send(JSON.stringify({type:'text',content:t,subject:'math_one',chapter:currentChapter}))}
function showQuestion(y,q){ws.send(JSON.stringify({type:'qbank_question',year:y,q_num:q}));addMsg('system','正在提取'+y+'年第'+q+'题...')}
function exitFeynman(){if(feynmanActive){ws.send(JSON.stringify({type:'feynman_end'}));feynmanActive=false;updateBar()}}
function updateBar(){document.getElementById('modeBar').innerHTML=feynmanActive?'🧠 <b>费曼模式</b> <a href="#" onclick="exitFeynman()">退出</a>':'选择左侧章节或输入知识点开始学习'}

function renderQ(d){var b=document.getElementById('chatBox');var div=document.createElement('div');div.className='msg question';div.id='q-'+d.topic_id;var h='<div class="q-title">📝 '+d.question+'</div>';if(d.options&&d.options.length){h+='<div class="options">';d.options.forEach(function(o,i){h+='<div class="opt" onclick="ansQ(\''+d.topic_id+'\',\''+String.fromCharCode(65+i)+'\',this)">'+o+'</div>'});h+='</div>'}h+='<div style="margin-top:6px"><input id="ans-'+d.topic_id+'" placeholder="输入答案" style="padding:6px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);border-radius:4px;color:white;width:60%;font-size:.85em"> <button class="btn-primary" style="font-size:.78em" onclick="submitAns(\''+d.topic_id+'\')">提交</button></div>';div.innerHTML=h;b.appendChild(div);b.scrollTop=b.scrollHeight;renderMath(div)}
function ansQ(tid,ans,el){document.querySelectorAll('#q-'+tid+' .opt').forEach(function(o){o.classList.remove('chosen')});el.classList.add('chosen');ws.send(JSON.stringify({type:'diagnosis_answer',answer:ans}))}
function submitAns(tid){var a=document.getElementById('ans-'+tid).value.trim();if(a)ws.send(JSON.stringify({type:'diagnosis_answer',answer:a}))}
function renderReport(d){var div=document.createElement('div');div.className='msg assistant';var h='<b>诊断报告</b><br>正确率：'+d.accuracy+'% ('+d.correct+'/'+d.total+')<br>';if(d.weak_points&&d.weak_points.length){h+='薄弱点：<br>';d.weak_points.forEach(function(w){h+='• '+w.name+'<br>'})}if(d.ai_summary)h+='<br>'+d.ai_summary;div.innerHTML=h;var bb=document.getElementById('chatBox');bb.appendChild(div);renderMath(div)}
function renderExam(d){d.questions.forEach(function(q,i){var div=document.createElement('div');div.className='msg question';div.id='eq-'+i;var h='<div class="q-title">第'+(i+1)+'题 ['+q.topic_name+']</div>'+q.question;if(q.options&&q.options.length){h+='<div class="options">';q.options.forEach(function(o,j){h+='<div class="opt" onclick="ansExam('+i+',\''+String.fromCharCode(65+j)+'\',this,\''+q.answer+'\')">'+o+'</div>'});h+='</div>'}div.innerHTML=h;var ex=document.getElementById('chatBox');ex.appendChild(div);renderMath(div)})}
function ansExam(i,ans,el,correct){document.querySelectorAll('#eq-'+i+' .opt').forEach(function(o){o.classList.remove('chosen')});el.classList.add('chosen');el.style.background=ans===correct?'rgba(74,222,128,0.3)':'rgba(248,113,113,0.3)';addMsg('system',ans===correct?'✅ 正确':'❌ 正确答案: '+correct)}
function renderHotspots(d){var div=document.createElement('div');div.className='msg assistant';var h='<b>考点预测</b><br><br>';d.hotspots.forEach(function(x,i){h+=(i+1)+'. '+x.name+' ['+x.chapter+'] '+x.weight+' '+'*'.repeat(x.difficulty||3)+'<br>'});if(d.ai_analysis)h+='<br>'+d.ai_analysis;div.innerHTML=h;var hs=document.getElementById('chatBox');hs.appendChild(div);renderMath(div)}
function renderPlan(d){var div=document.createElement('div');div.className='msg assistant';var h='<b>学习计划 ('+d.available_days+'天)</b><br><br>';if(d.recommendations){d.recommendations.forEach(function(r,i){h+=(i+1)+'. '+r.name+' ['+r.chapter+'] '+(r.is_weak?'[薄弱]':'')+'<br>'})}if(d.ai_study_plan)h+='<br>'+d.ai_study_plan;div.innerHTML=h;var pp=document.getElementById('chatBox');pp.appendChild(div);renderMath(div)}
function genPaper(y){if(!y){var e=document.getElementById('yearSelect');y=e?parseInt(e.value):2024}ws.send(JSON.stringify({type:'qbank_paper',year:y}));addMsg('system','正在生成'+y+'年真题卷...')}function getYearOptions(){var h='<select id="yearSelect" style="padding:6px 10px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);border-radius:6px;color:white;margin-right:8px">';for(var y=2025;y>=1987;y--){h+='<option value="'+y+'"'+(y===2024?' selected':'')+'>'+y+'年</option>'}h+='</select><button class="btn-secondary" onclick="genPaper()">📋 生成真题卷</button>';return h}function startDiag(){ws.send(JSON.stringify({type:'diagnosis_start',subject:'math_one'}))}
function startDiagCh(){if(currentChapter)ws.send(JSON.stringify({type:'diagnosis_start',subject:'math_one',chapter:currentChapter}))}
function genExam(){ws.send(JSON.stringify({type:'exam_generate',subject:'math_one',count:5,chapter:currentChapter}))}
function hotspots(){ws.send(JSON.stringify({type:'exam_hotspots',subject:'math_one',chapter:currentChapter}))}
function getRecs(){ws.send(JSON.stringify({type:'roadmap_recommend',subject:'math_one'}))}
function getPlan(d){ws.send(JSON.stringify({type:'roadmap_plan',subject:'math_one',days:d}))}

connect();renderChapters();updateBar();
document.getElementById('textInput').addEventListener('keypress',function(e){if(e.key==='Enter')sendMsg()});
</script></body></html>"""


def main():
    asyncio.run(StudyCompanionApp().run())

if __name__ == "__main__":
    main()
