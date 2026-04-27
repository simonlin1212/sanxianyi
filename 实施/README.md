# 实施目录 · 操作指南

这个目录用于阶段 0（核心算法验证）的实际代码 + 测试输出。

## 你（Simon）现在需要做的事（一次性）

### 1. 申请 API key（5 分钟）

**默认用 MiniMax**（成本约 Anthropic Opus 的 1/100，Router 这种提炼员任务完全够用）：

- 访问：https://platform.minimaxi.com/
- 注册/登录 → 左侧「API Key 管理」 → 创建新 Key
- 复制 key
- 默认模型：`MiniMax-M2.7`（最新主力）

**预估阶段 0 跑 10 个用例总成本 < ¥0.5**（MiniMax 极便宜）。

**备选：Anthropic**（M0.1 跑通后做最终对比时切换）：
- https://console.anthropic.com/ → API keys → Create Key
- 在 `.env` 里把 `LLM_PROVIDER=minimax` 改为 `LLM_PROVIDER=anthropic`

### 2. 把 key 写到 .env 文件（本地操作，不要发给我）

在 Mac 终端跑：

```bash
cd "/Users/TiktokShop/Documents/simon-files/1-Projects/6、自媒体-独立开发者转型/职场三人智囊团/实施"
cp .env.example .env
# 然后编辑 .env，把 sk-ant-api03-xxx 替换成你的真实 key
```

或者用 VSCode 打开 `.env` 文件直接改。

### 3. 让我跑测试

key 配好后，告诉我"key 就绪"，我会执行：

```bash
python3 router_test.py
```

跑完输出到 `outputs/router_test_report.md`，我会给你审。

---

## 目录结构

```
实施/
├── README.md                 # 本文档
├── .env.example              # API key 模板（已生成）
├── .env                      # 你填真实 key 后产生（gitignore）
├── .gitignore                # 防止 .env 被提交
├── prompts/
│   └── router_v0.2.txt       # Router 的 system prompt
├── test_cases.yaml           # 15 个测试用例
├── router_test.py            # 测试脚本
└── outputs/                  # 测试报告会生成在这里
```

## 阶段 0 进度对应

| 模块 | 文件 | 状态 |
|---|---|---|
| M0.1 Router 设计 | `../设计文档/M0.1-Router设计.md` | ✅ v0.2 已审 |
| M0.1 Router 实施 | `prompts/router_v0.2.txt` + `router_test.py` | 🔄 待跑 |
| M0.1 Router 测试报告 | `outputs/router_test_report.md` | ⏳ 跑完后 |
| M0.2 三 agent 设计 | `../设计文档/M0.2-*.md` | ⏳ M0.1 通过后 |
| M0.3 主持人设计 | `../设计文档/M0.3-*.md` | ⏳ |
| M0.4 编排脚本 | `orchestrator.py` | ⏳ |
| M0.5 5 困境实测 | `outputs/full_debate_*.md` | ⏳ |

## 安全说明

- `.env` 永远不会被提交（已加 .gitignore）
- 你的 API key 只存在你本地
- 跑脚本时通过 `os.getenv()` 读取，不会在输出里打印
