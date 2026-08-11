"""查看 mock 请求日志：路由/流式/工具数/prompt 特征。用法: python inspect_logs.py [N]"""
import json
import os
import sys
from pathlib import Path

LOG_DIR = Path(os.environ.get("MOCK_LLM_LOG_DIR", "logs"))
n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
files = sorted(LOG_DIR.glob("req-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
for path in files[:n]:
    d = json.loads(path.read_text(encoding="utf-8"))
    print(f"--- {path.name}")
    print(f"  route={d['route']} stream={d['stream']} tools={d['tools_requested']} msgs={d['message_count']}")
    print(f"  sys: {d['system_prompt'][:200].replace(chr(10), ' / ')}")
    print(f"  last_user: {d['last_user'][:200].replace(chr(10), ' / ')}")
