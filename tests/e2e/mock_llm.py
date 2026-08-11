#!/usr/bin/env python3
"""writer-assistant E2E mock LLM server — OpenAI 兼容 /v1/chat/completions。

设计：
- 秒级返回预设剧本响应，驱动真实 CLI 链路（chapter_pipeline / ReAct 循环全部真实执行）
- 剧本按请求内容路由（system prompt 关键词优先，其次全量消息），路由名对应 scripts/<route>.txt 文件
- 支持流式（SSE）与非流式两种响应
- 完整请求/路由/响应日志，供测试报告使用
- 故障注入：MOCK_FAULT=delay|empty|truncate|http500 环境变量
"""
from __future__ import annotations

import json
import re
import os
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get("MOCK_LLM_PORT", "9876"))
LOG_DIR = Path(os.environ.get("MOCK_LLM_LOG_DIR", "logs"))
SCRIPT_DIR = Path(os.environ.get("MOCK_LLM_SCRIPT_DIR", "scripts"))
FAULT = os.environ.get("MOCK_FAULT", "")  # delay | empty | truncate | http500 | none
DELAY_SECONDS = float(os.environ.get("MOCK_FAULT_DELAY", "75"))  # 超过 LLM 超时(60s)触发

LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_request(entry: dict) -> None:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = LOG_DIR / f"req-{stamp}-{uuid.uuid4().hex[:6]}.json"
    path.write_text(
        json.dumps(entry, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
    )


def message_text(messages: list[dict]) -> str:
    parts = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") for c in content if isinstance(c, dict)
            )
        parts.append(f"[{role}] {content}")
    return "\n".join(parts)


def route_for(messages: list[dict]) -> str:
    """路由规则：system prompt 身份优先（每个阶段的 system 是稳定任务描述），
    last_user 关键词兜底。"""
    texts = message_text(messages)
    last_user = str(messages[-1].get("content", "")) if messages else ""
    system = "\n".join(
        str(m.get("content", "")) for m in messages if m.get("role") == "system"
    )
    hay = system or texts
    # 结构化阶段（按 system 稳定特征，优先级高）
    if "提取关键信息" in hay or "提取关键事实" in hay:
        return "extract"
    if "严格 YAML" in hay or "只输出严格" in hay:
        return "state_update"
    if "合并到世界观状态" in hay or "真相文件" in hay or "细心的编辑" in hay:
        return "state_merge"
    # 写作类：小说作家身份（system 身份词，不用 user 内容避免误判）
    if "小说作家" in hay or "小说家" in hay:
        return "writing"
    # 审稿类：system 身份词（优先级高于 planning——审稿 system 常含"世界观/设定"）
    if any(k in hay for k in ("审稿", "审查", "评审", "检视", "reviewer", "审阅", "审核", "小说编辑")):
        return "review"
    # 规划/大纲/设定类
    if any(k in hay for k in ("大纲", "规划", "outline", "世界观", "设定", "分卷")):
        return "planning"
    return "unknown"


# 目标区间只在"控制/目标字数"语境中找，避免命中 system 风格表格里的 "1-8 字一句"
_TARGET_RANGE_RE = re.compile(
    r"(?:正文必须控制(?:在)?|目标字数[^\n]*?)(\d+)\s*[-~]\s*(\d+)\s*个?中文字符"
)


def _fit_target_length(content: str, texts: str) -> str:
    """写作响应按指令中的目标区间动态调整长度（按段落循环拼接/截断）。"""
    m = _TARGET_RANGE_RE.search(texts)
    if not m:
        return content
    lo, hi = int(m.group(1)), int(m.group(2))
    hanzi = sum(1 for ch in content if "一" <= ch <= "鿿")
    if lo <= hanzi <= hi:
        return content
    paragraphs = [p for p in content.split("\n\n") if p.strip()]
    if not paragraphs:
        return content
    # 不足：循环拼接段落；超出：截断到区间中值
    if hanzi < lo:
        parts, total = list(paragraphs), hanzi
        while total < lo:
            parts.append(paragraphs[len(parts) % len(paragraphs)])
            total += sum(1 for ch in parts[-1] if "一" <= ch <= "鿿")
        return "\n\n".join(parts)
    target = (lo + hi) // 2
    result, total = [], 0
    for p in paragraphs:
        if total >= target:
            break
        result.append(p)
        total += sum(1 for ch in p if "一" <= ch <= "鿿")
    return "\n\n".join(result)


def script_text(route: str, fallback: str = "（默认响应）") -> str:
    for name in (route, "default"):
        path = SCRIPT_DIR / f"{name}.txt"
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return fallback


def chat_response(content: str, *, tool_calls: list[dict] | None = None) -> dict:
    message: dict = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": f"chatcmpl-mock-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "mock-model",
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 500,
            "total_tokens": 1500,
        },
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 静音默认访问日志
        pass

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        for enc in ("utf-8", "gbk"):
            try:
                return json.loads(raw.decode(enc))
            except UnicodeDecodeError:
                continue
            except json.JSONDecodeError:
                break
        return {}

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/chat/completions"):
            self.send_response(404)
            self.end_headers()
            return
        body = self._read_body()
        messages = body.get("messages", [])
        route = route_for(messages)
        texts = message_text(messages)

        # ---- 故障注入 ----
        if FAULT == "delay":
            time.sleep(DELAY_SECONDS)
        if FAULT == "http500":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", "0")
            self.end_headers()
            log_request({"fault": "http500", "route": route})
            return
        if FAULT == "empty":
            content = ""
        elif FAULT == "truncate":
            content = script_text(route)[:100]  # 截断响应（下游应按截断处理）
        else:
            content = script_text(route)
            if route == "writing":
                content = _fit_target_length(content, texts)

        stream = bool(body.get("stream"))
        log_request(
            {
                "route": route,
                "fault": FAULT or "none",
                "stream": stream,
                "model": body.get("model"),
                "tools_requested": len(body.get("tools", []) or []),
                "message_count": len(messages),
                "system_prompt": messages[0].get("content", "")[:200]
                if messages
                else "",
                "last_user": messages[-1].get("content", "")[:300]
                if messages
                else "",
                "messages_debug": [
                    {"role": m.get("role"), "content": str(m.get("content", ""))[:3000]}
                    for m in messages
                ],
                "response_content": content[:200],
            }
        )

        payload = chat_response(content)
        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            # 按 8 字符切块，模拟真实流式
            for i in range(0, len(content), 8):
                chunk = {
                    "id": payload["id"],
                    "object": "chat.completion.chunk",
                    "created": payload["created"],
                    "model": payload["model"],
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": content[i : i + 8]},
                            "finish_reason": None,
                        }
                    ],
                }
                self.wfile.write(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8"))
                self.wfile.flush()
            final = {
                "id": payload["id"],
                "object": "chat.completion.chunk",
                "created": payload["created"],
                "model": payload["model"],
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": payload["usage"],
            }
            self.wfile.write(f"data: {json.dumps(final, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        else:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            self.wfile.flush()


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"mock LLM listening on http://127.0.0.1:{PORT}/v1 (fault={FAULT or 'none'})")
    print(f"scripts dir: {SCRIPT_DIR.resolve()}")
    print(f"logs dir: {LOG_DIR.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
