"""
M1.2 FastAPI SSE 服务

POST /api/debate { user_input } → text/event-stream
事件类型：
  - stage              进度文字
  - router_done        Router 卡片就绪
  - opinions_done      3 人首发就绪
  - r1_rebuttals_done  第一轮反驳就绪
  - r1_replies_done    第一轮回应就绪
  - r2_rebuttals_done  第二轮反驳就绪
  - r2_replies_done    第二轮回应就绪
  - done               主持人综合 + 完整结果
  - error              异常

每事件格式：data: {type, ...payload}\\n\\n
"""

from __future__ import annotations

import asyncio
import json
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from router import route
from moderator import Moderator, ROUND_1_PAIRS, ROUND_2_PAIRS

app = FastAPI(title="职场三人智囊团 API", version="0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse(event_type: str, data: dict) -> str:
    payload = {"type": event_type, **data}
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def serialize_pairs_dict(d: dict) -> dict:
    """tuple key → 'speaker->target' 字符串。"""
    out = {}
    for k, v in d.items():
        key = f"{k[0]}->{k[1]}" if isinstance(k, tuple) else str(k)
        out[key] = v
    return out


async def debate_stream(user_input: str):
    try:
        m = Moderator()

        yield sse("stage", {"name": "router", "msg": "困境提炼中（约 5-30s）..."})
        card = await asyncio.to_thread(route, user_input)
        yield sse("router_done", {"card": card})

        if card.get("crisis"):
            yield sse("stage", {"name": "crisis", "msg": "识别到关键信号，主持人接管..."})
            r = await asyncio.to_thread(m._crisis_response, card)
            yield sse("done", {
                "output_type": "crisis_response",
                "text": r["text"],
                "card": card,
            })
            return

        if card.get("needs_followup"):
            yield sse("stage", {"name": "followup", "msg": "主持人追问中..."})
            r = await asyncio.to_thread(m._followup_question, card)
            yield sse("done", {
                "output_type": "followup_question",
                "text": r["text"],
                "card": card,
            })
            return

        intent = (card.get("core") or {}).get("intent", "decision")

        if intent == "listen":
            yield sse("stage", {"name": "opinions", "msg": "苏轼牵头抚慰，曾/王 补位（约 60-90s）..."})
            opinions = await asyncio.to_thread(m._parallel_first_opinions, card)
            yield sse("opinions_done", {"opinions": opinions})

            yield sse("stage", {"name": "synthesis", "msg": "主持人收尾（约 30-60s）..."})
            text = await asyncio.to_thread(m._synthesize_listen, card, opinions)
            yield sse("done", {
                "output_type": "full_response",
                "intent": "listen",
                "text": text,
                "card": card,
                "opinions": opinions,
            })
            return

        # 2 轮辩论
        yield sse("stage", {"name": "opinions", "msg": "三人首发中（约 25-90s）..."})
        opinions = await asyncio.to_thread(m._parallel_first_opinions, card)
        yield sse("opinions_done", {"opinions": opinions})

        yield sse("stage", {"name": "r1_rebuttal", "msg": "第一轮反驳中（顺时针·约 25-90s）..."})
        rb_r1 = await asyncio.to_thread(
            m._parallel_rebuttals, card, ROUND_1_PAIRS, opinions, 1
        )
        yield sse("r1_rebuttals_done", {"rebuttals": serialize_pairs_dict(rb_r1)})

        yield sse("stage", {"name": "r1_reply", "msg": "第一轮回应中（约 25-90s）..."})
        rp_r1 = await asyncio.to_thread(
            m._parallel_replies, card, ROUND_1_PAIRS, opinions, rb_r1, 1
        )
        yield sse("r1_replies_done", {"replies": rp_r1})

        yield sse("stage", {"name": "r2_rebuttal", "msg": "第二轮反驳中（逆时针·约 25-90s）..."})
        rb_r2 = await asyncio.to_thread(
            m._parallel_rebuttals, card, ROUND_2_PAIRS, opinions, 2, rp_r1
        )
        yield sse("r2_rebuttals_done", {"rebuttals": serialize_pairs_dict(rb_r2)})

        yield sse("stage", {"name": "r2_reply", "msg": "第二轮回应中（约 25-90s）..."})
        rp_r2 = await asyncio.to_thread(
            m._parallel_replies, card, ROUND_2_PAIRS, opinions, rb_r2, 2
        )
        yield sse("r2_replies_done", {"replies": rp_r2})

        flagged = m._verify_references(opinions)

        yield sse("stage", {"name": "synthesis", "msg": "主持人综合中（约 30-60s）..."})
        text = await asyncio.to_thread(
            m._synthesize_decision,
            card, opinions, rb_r1, rp_r1, rb_r2, rp_r2, flagged
        )

        yield sse("done", {
            "output_type": "full_response",
            "intent": intent,
            "text": text,
            "card": card,
            "opinions": opinions,
            "round_1": {
                "rebuttals": serialize_pairs_dict(rb_r1),
                "replies": rp_r1,
            },
            "round_2": {
                "rebuttals": serialize_pairs_dict(rb_r2),
                "replies": rp_r2,
            },
            "flagged": flagged,
        })

    except Exception as e:
        import traceback
        yield sse("error", {
            "msg": str(e),
            "traceback": traceback.format_exc()[-500:],
        })


class DebateRequest(BaseModel):
    user_input: str


@app.post("/api/debate")
async def debate(req: DebateRequest):
    if not req.user_input.strip():
        return {"error": "user_input required"}
    return StreamingResponse(
        debate_stream(req.user_input),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "三人智囊团 API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001, log_level="info", loop="asyncio")
