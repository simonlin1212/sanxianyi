# Backend 实施目录

三贤议的后端 Python 代码 + Router/Agent prompt + M0.5 实测产物。

详细架构见 [`../设计文档/M0.3-主持人设计.md`](../设计文档/M0.3-主持人设计.md)。

---

## 快速启动

### 1. 装依赖

```bash
pip install fastapi uvicorn openai anthropic pyyaml python-dotenv
```

### 2. 配 API Key

```bash
cp .env.example .env
# 然后编辑 .env，填一个 LLM provider 的 key（二选一）
```

支持的 provider：

| Provider | 申请 | 单次完整辩论成本 | 速度 |
|---|---|---|---|
| **MiniMax-M2.7**（默认） | https://platform.minimaxi.com/ | ¥0.06-0.10 | 3-6 分钟（推理模型） |
| Anthropic Claude | https://console.anthropic.com/ | ~¥3-5 | 1-2 分钟 |
| GLM 智谱 | https://bigmodel.cn/ | ¥0.05-0.08 | 1-2 分钟 |

切 GLM：`.env` 设 `LLM_PROVIDER=anthropic` + `ANTHROPIC_BASE_URL=https://open.bigmodel.cn/api/anthropic` + `ANTHROPIC_MODEL=glm-4.7`。

### 3. 启 backend 服务（FastAPI + SSE）

```bash
python3 server.py     # 监听 http://localhost:5001
```

### 4. 启 frontend（另开一个终端）

```bash
# 在 sanxianyi 根目录
npx http-server ui -p 5500 --cors -s
# 或：cd ../ui && python3 -m http.server 5500
```

打开 `http://localhost:5500` 即可。

---

## 跑测试

### M0.1 Router 单元测试（10/10 通过）

```bash
python3 router_test.py
```

产出 `outputs/router_test_report.md`。

### M0.5 5 困境集成测试

```bash
python3 orchestrator_test.py
```

跑 5 个有代表性的困境用例（覆盖 crisis / followup / listen / decision），产出每个用例的完整 markdown + 汇总报告 `outputs/m05_test_report.md`。

> 注意：5 困境完整跑完约 10-15 分钟（其中 2 个 decision 类各约 6 分钟，是 MiniMax 推理模型的特性）。

### 单次 CLI 调试

```bash
python3 orchestrator.py "我 30 岁，互联网产品经理，月薪 25k..."
```

直接传困境文本作为参数，跑完输出到 `outputs/run_<timestamp>_cli.md`。

---

## 文件结构

```
实施/
├── server.py                   # FastAPI + SSE 入口（端口 5001）
├── orchestrator.py             # 主流程编排 / CLI 入口
├── moderator.py                # 主持人逻辑 + 4 内置 prompt（crisis/followup/synthesize/fallback）
├── router.py                   # Router 入口（薄包装）
├── agents.py                   # BaseAgent + 3 persona 子类（ZengGuoFan/SuShi/WangYangMing）
├── corpus_loader.py            # 加载 ../设计文档/M0.2-*-语料.yaml + 引文打假
├── orchestrator_test.py        # M0.5 5 困境实测
├── router_test.py              # M0.1 Router 单元测试
├── test_cases.yaml             # 15 个 Router 测试用例
├── prompts/
│   ├── router_v0.2.txt         # Router system prompt
│   ├── zengguofan_v0.1.txt     # 曾国藩 system prompt
│   ├── sushi_v0.1.txt          # 苏轼 system prompt
│   └── wangyangming_v0.1.txt   # 王阳明 system prompt
├── outputs/                    # 实测产物（M0.5 真实跑通的 4 个困境 markdown）
├── .env.example                # 环境变量模板
└── README.md                   # 本文档
```

---

## API Endpoints

`server.py` 暴露：

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查 |
| POST | `/api/debate` | 主入口，接收 `{user_input}`，返回 SSE 流 |

SSE 事件类型（9 种）：
- `stage` — 当前 stage 名称 + 进度
- `router_done` — Router 卡片
- `opinions_done` — 3 人首发输出
- `r1_rebuttals_done` / `r1_replies_done` — 第 1 轮辩论
- `r2_rebuttals_done` / `r2_replies_done` — 第 2 轮辩论
- `done` — 主持人最终 markdown
- `error` — 错误信息

---

## 安全

- `.env` 已加入 `.gitignore`，不会被提交
- 代码全部用 `os.getenv()` 读取 API key，不会硬编码
- backend 重启时 prompt 会重新加载（修改 `prompts/*.txt` 后必须 pkill + 重启 server.py）

---

## 改 LLM Provider

`agents.py` 的 `_call_llm()` 函数封装了 minimax / anthropic 双 SDK 适配。要加新 provider（如 DeepSeek 直接 OpenAI SDK 兼容）：

1. `.env` 加新 provider 的 key
2. `agents.py` 顶部 if/elif 加分支
3. 重启 server

详见 `agents.py:24-55` 的 provider 初始化逻辑。

---

## 性能 / 成本参考

单次完整 2 轮辩论（intent=decision）：
- LLM 调用 = **16 次**（3 首发 + 3+3+3+3 R1/R2 反驳回应 + 1 主持人综合）
- 总 LLM token ≈ 80-150K（含全部 stage YAML 上下文）
- MiniMax-M2.7 实测耗时 = **3-6 分钟**（推理模型每次 25-90s）
- 成本 ≈ ¥0.06-0.10 / 次

性能瓶颈是 MiniMax 推理模型的 `<think>` 链。如要加速，切非推理模型（DeepSeek-V3 / Qwen-Plus）单次 ~1 分钟，但 prompt 兼容性需要再调试。
