# E2E 全流程测试（Mock LLM）

用 OpenAI 兼容 mock 端点驱动**真实 CLI 链路**做端到端测试：agent ReAct 循环、长度校验、状态落定、快照事务、审稿、成书导出全部真实执行，只有 LLM 响应被替换为预设剧本（秒级返回，替代真实 LLM 的分钟级延迟）。

## 快速开始

```bash
# 1. 启动 mock（默认端口 9876，需在 bash/终端里挂后台）
python tests/e2e/mock_llm.py

# 2. 初始化一个测试项目（模板 demo_short）
writer init my-e2e --template demo_short

# 3. 用 mock 跑全流程（环境变量注入即可，产品代码零改动）
export LLM_BASE_URL="http://127.0.0.1:9876/v1" \
       LLM_API_KEY="mock-key" \
       LLM_MODEL="mock-model" \
       LLM_PROVIDER="openai"
writer write next        # 写作一章（Phase 1 创意写作 + Phase 2 状态落定）
writer multi-write next  # 多 Agent 编排写扩展章
writer review            # 审稿
writer assemble          # 成书
writer export --format md
```

## 结构

| 文件 | 说明 |
|------|------|
| `mock_llm.py` | OpenAI 兼容 mock 服务：按 system 身份词路由剧本、长度动态扩展、流式/非流式、故障注入 |
| `scripts/*.txt` | 各阶段剧本（writing/extract/state_update/state_merge/review/default） |
| `inspect_logs.py` | 请求日志查看工具（设置 `MOCK_LLM_LOG_DIR` + 传 N 参数） |
| `TEST-REPORT.md` | 2026-08-11 全流程测试报告（正向闭环 + 故障注入 4 场景 + 发现清单） |

## 故障注入

```bash
MOCK_FAULT=delay|empty|truncate|http500 python tests/e2e/mock_llm.py
# delay 可用 MOCK_FAULT_DELAY 指定秒数（默认 75s）
```

对应产品行为：HTTP 500 → 指数退避重试 3 次后报错；空响应 → MODEL_EMPTY_RESPONSE 明确报错；
截断响应 → 长度校验失败自动重写一次；长延迟 → 在 litellm 默认 600s 超时内正常完成。

## 注意事项

- 每次修改 mock_llm.py 后重启进程前**确保文件已落盘**（Windows 写盘延迟会导致 nohup 读到旧文件）
- 杀旧进程：`netstat -ano | grep 9876` 找到 PID 后 `taskkill //F //PID <pid>`
- 日志默认写到 `logs/req-*.json`（可通过 `MOCK_LLM_LOG_DIR` 覆盖），建议加入 .gitignore
