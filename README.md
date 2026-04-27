# 三贤议 · sanxianyi

> 让 **曾国藩 · 苏轼 · 王阳明** 三位独立 agent，为你的职场困境真实辩论 2 轮
>
> *Three Chinese sages debate your career dilemma — twice, for real.*

![visual](https://img.shields.io/badge/三家共议-不予定论-c83232?style=flat-square)
![multi-agent](https://img.shields.io/badge/真%C2%B7多Agent-辩论架构-d4a85a?style=flat-square)
![status](https://img.shields.io/badge/status-阶段%E2%93%AA%2B%E2%91%A0_完成-2c3e50?style=flat-square)
![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square)

---

## 这是什么

一个**真·多 agent 辩论产品**——不是用一个 GPT 切换 prompt 假装多角色，而是 **3 个独立 agent**：

- 每位贤者 = 一个独立 LLM 实例 + 独立 system prompt + 独立精选语料库
- 你输入职场困境 → 三人各自给立场 → **互相质疑、辩论 2 轮**（每人发言 5 次）→ 主持人保留 3 人真实分歧 → 抛回给你自己选

**不给标准答案**——产品的核心是让你看 3 人真在为你吵架，自己挑。

---

## 三位贤者，三种维度

| 贤者 | 代表 | 核心 | 给你什么 |
|---|---|---|---|
| **曾国藩** | 勤奋派 | 拙诚 / 日课 / 慎独 | 笨功夫的尺子，问你下了多少 |
| **苏轼** | 乐观派 | 安住 / 旷达 / 重新框定 | 三贬黄惠儋的人，不会让你假装"想开了" |
| **王阳明** | 清醒派 | 致良知 / 知行合一 / 破心中贼 | 一面镜子，照出你藏在两难里、不敢承认的事 |

三人形成"行动 / 心态 / 认知"三角覆盖——任何困境都能让 3 人各占一边吵起来。

---

## 演示截图

> （首页 hero / 辩论现场 / 综合输出页 — 截图位）

---

## 架构（5 个 stage 串行 + 每 stage 内 3 次并行）

```
用户输入
   ↓
┌────────────── M0.1 Router ──────────────┐
│ 危机扫描 / 8 桶分类 / 100 分制信息打分      │
│ intent 判别（listen / decision / advice） │
└────────────────┬─────────────────────────┘
                 ↓
   ┌──── 主持人编排 ────┐
   │                      │
   │   crisis=true → 危机响应 (绕过 3 agent)
   │   needs_followup → 追问，再来一轮
   │   intent=listen → 苏轼主导 listen 模式
   │   else → 进入 ↓ 完整 2 轮辩论
   │                      │
   └──────────────────────┘
                 ↓
┌────── 2 轮深度辩论 (每 stage 3 次并行) ──────┐
│ 0  3 人首发                                    │
│ 1  R1 反驳（顺时针：曾→苏 / 苏→王 / 王→曾）   │
│ 2  R1 回应（被驳者 stage 3 调整）              │
│ 3  R2 再驳（逆时针，引用对方让步）            │
│ 4  R2 再应                                     │
└──────────────────────┬──────────────────────────┘
                       ↓
┌────── 主持人综合 ────────────────────────────┐
│ 共识 + 真实分歧（不和稀泥） + 今晚一件事       │
│ + closing question (王阳明 mirror_question)   │
└──────────────────────────────────────────────┘
                       ↓
                 给用户的 markdown
```

详见 [`设计文档/M0.3-主持人设计.md`](./设计文档/M0.3-主持人设计.md)。

---

## 项目结构

```
sanxianyi/
├── 设计文档/                         设计 + 实测产物
│   ├── 00-总开发大纲.md              阶段 0 路线图
│   ├── 01-阶段1-总开发大纲.md         阶段 1（UI + 视频）路线图
│   ├── 02-阶段1-UI完成总结.md         阶段 1 完成总结（最权威状态文档）
│   ├── M0.1-Router设计.md            Router agent 设计
│   ├── M0.2-{曾国藩,苏轼,王阳明}.md     3 persona agent 详细设计 ×3
│   ├── M0.2-{persona}-语料.yaml       3 persona 精选语料库（180 条 / HIGH 80%）
│   └── M0.3-主持人设计.md             主持人 / 编排器 v0.2（2 轮辩论版）
│
├── 实施/                              Backend Python
│   ├── server.py                     FastAPI + SSE 入口
│   ├── orchestrator.py               主流程编排
│   ├── moderator.py                  主持人逻辑 + 4 内置 prompt
│   ├── router.py                     Router 入口
│   ├── agents.py                     BaseAgent + 3 persona class
│   ├── corpus_loader.py              语料 yaml 加载 + 引文核验（防 LLM 编造）
│   ├── orchestrator_test.py          M0.5 5 困境实测脚本
│   ├── router_test.py                M0.1 Router 单元测试
│   ├── test_cases.yaml               15 个 Router 测试用例
│   ├── prompts/                      4 个 system prompt（Router + 3 persona）
│   ├── outputs/                      实测产物 markdown（M0.5 真实跑通的 4 困境）
│   └── .env.example                  环境变量模板
│
├── ui/                                Frontend 单页
│   ├── index.html                    主入口（Hero / Input / Live / Synthesis 4 view）
│   ├── css/custom.css                印章 / 进度条 / 对话气泡 / 流式打字
│   └── js/data.js                    4 个 demo case 真实数据
│
├── 三人语料/README.md                 语料调研索引（原始下载已剔除）
├── EP01-三贤议产品介绍.md             视频脚本 / 演讲稿
├── README.md                         本文档
├── LICENSE                           MIT
└── .gitignore
```

---

## 快速开始

### 1. 装依赖

```bash
pip install fastapi uvicorn openai anthropic pyyaml python-dotenv
```

### 2. 配 API Key

复制 `.env.example` 为 `.env`，填一个 LLM provider 的 key：

```bash
cd 实施
cp .env.example .env
# 编辑 .env，二选一：
# A. MiniMax（推荐，性价比高）：sk-cp-...
# B. Anthropic Claude：sk-ant-api03-...
```

支持的 provider：
- **MiniMax-M2.7**（默认，¥0.06-0.10/次完整辩论，6 分钟）
- **Anthropic Claude**（Opus 4.7 / Sonnet 4.6，~¥3-5/次，1-2 分钟）
- **GLM**（智谱，原生 Anthropic API 兼容，可直接换 base_url）

### 3. 启动 backend

```bash
cd 实施
python3 server.py    # 监听 http://localhost:5001
```

### 4. 启动 frontend

```bash
# 任选其一：
npx http-server ui -p 5500 --cors -s
# 或：
cd ui && python3 -m http.server 5500
```

打开浏览器：`http://localhost:5500`

### 5. 演示模式（不调 LLM）

UI 首页 4 个真实案例卡片直接点击 → 跳到 synthesis 页看预生成结果（来自 M0.5 实测产物）。无需启 backend。

---

## 阶段完成度

| 阶段 | 模块 | 状态 |
|---|---|---|
| **M0.1** | Router 设计 + 实施 + 10/10 测试 | ✅ |
| **M0.2** | 三 agent 设计骨架 | ✅ |
| **M0.2.5** | 三人语料萃取（180 条 / HIGH 80%） | ✅ |
| **M0.3** | 主持人设计 v0.2（2 轮深度辩论） | ✅ |
| **M0.4** | 编排脚本（含引文打假） | ✅ |
| **M0.5** | 5 困境实测 | ✅ |
| **M1.1** | UI 4 页面（Hero / Input / Live / Synthesis） | ✅ |
| **M1.2** | 后端 SSE + 真实 LLM 流式接通 | ✅ |

阶段 1 之后**作者不再继续维护**——本仓库为完整历史归档，欢迎任何 fork / 改造 / 商用。

---

## 技术栈

- **Backend**: FastAPI + uvicorn + asyncio + Python 3.9+
- **LLM Provider**: MiniMax-M2.7（默认）/ Anthropic Claude / GLM
- **Frontend**: 单 HTML + Tailwind CDN v4 + Alpine.js v3 + marked.js + LXGW WenKai webfont
- **流式**: Server-Sent Events（POST + ReadableStream + TextDecoder）
- **辩论**: 5 stage 串行（首发 / R1 反驳 / R1 回应 / R2 反驳 / R2 回应），每 stage 3 次并行
- **共 16 次 LLM 调用 / 单次完整辩论**

---

## 设计哲学（避坑指南）

本项目踩过的坑，都已固化在 `设计文档/` 和 prompt 里：

1. **真·多 agent ≠ Subagent + prompt 切换**——独立上下文 + 独立 prompt + 独立语料才有真冲突
2. **第二轮反驳必须能引用对方第一轮让步**——这才有"真辩论"感（连续追打 vs 换边对比的设计在 M0.3 § 6.2）
3. **主持人不调和分歧**——保留 3 人真实立场让用户自选，比给"折中方案"更有价值
4. **不给客户长期计划**——只给"今晚 / 明早 / 这一两日"近期可执行小事，禁"30/60/90 天"
5. **LLM 严禁编造用户未提及细节**——双层禁忌（agent prompt + synthesizer prompt），防"贴模板"幻觉
6. **agent 称客户用"汝/兄/君"**——古雅端庄，避免"用户"二字的工具感

---

## 致谢

- **历史人物素材**：参考公开版本的《曾国藩家书》《传习录》《苏轼诗词全集》《东坡志林》《林语堂苏东坡传》——本仓库 `三人语料/README.md` 列了调研用的开源 GitHub 仓库索引（原始 dump 因版权原因未一并上传）
- **配色 / 视觉系统**：印章 + 朱砂 + 暗金的"东方水墨 + 现代 SaaS"调性灵感来自抖音内容创作者社群
- **字体**：[LXGW WenKai 霞鹜文楷](https://github.com/lxgw/LxgwWenKai)（开源中文楷体）
- **架构对标**：调研过 GitHub 上 [superman](https://github.com/...)、[TopPerson](https://github.com/...)、[claude-marketplace](https://github.com/anthropics/...) 等多 agent 项目（详见 `设计文档/00-总开发大纲.md`）

---

## License

[MIT](./LICENSE) — 完全开源，可商用，可改造，无任何限制。

---

## 作者

- 抖音 / B 站 / 视频号 / 小红书：[@硅基世纪](#)（Claude Code 深度玩家 + AI 内容创作者）
- 项目状态：**已完成阶段 1，不再继续维护**。本仓库为完整历史归档。

---

# English Version

## What is this

A **real multi-agent debate product** — not a single GPT switching prompts to fake multiple roles, but **3 independent agents**:

- Each sage = independent LLM instance + independent system prompt + independent curated corpus
- You input a career dilemma → 3 sages give their initial stances → cross-question and **debate twice** (each speaks 5 times) → moderator preserves their **real disagreements** → throws back to you to choose

**No standard answers** — the core value is letting you watch 3 people really argue *for* you, then pick.

## Three sages, three dimensions

| Sage | Type | Core | Gives you |
|---|---|---|---|
| **Zeng Guofan** | The Diligent | Honesty / Daily practice / Self-discipline | A ruler measuring how much hard work you've actually put in |
| **Su Shi** | The Optimist | Settling / Detachment / Reframing | Someone exiled three times who won't let you fake "I'm over it" |
| **Wang Yangming** | The Awakener | Innate knowledge / Unity of action and intent | A mirror reflecting what you hide in your "dilemma" |

Three sages cover **action / mindset / cognition** — any dilemma will pull them into different corners.

## Architecture

5 sequential stages × 3 parallel calls per stage = **16 LLM calls per full debate**:

```
Stage 0  3 sages first opinions      (parallel)
Stage 1  R1 rebuttals (clockwise)    (parallel)
Stage 2  R1 replies (yielded/held)   (parallel)
Stage 3  R2 rebuttals (counterclockwise, citing R1 yielding) (parallel)
Stage 4  R2 replies                  (parallel)
Stage 5  Moderator synthesis (consensus + disagreement + tonight action)
```

See [`设计文档/M0.3-主持人设计.md`](./设计文档/M0.3-主持人设计.md) for full design.

## Quick start

```bash
# Install
pip install fastapi uvicorn openai anthropic pyyaml python-dotenv

# Config
cd 实施
cp .env.example .env  # Fill MiniMax or Anthropic API key

# Backend
python3 server.py     # http://localhost:5001

# Frontend
npx http-server ../ui -p 5500 --cors -s
open http://localhost:5500
```

## Status

Phases 0 + 1 complete. Author **no longer actively maintains**. This repo is a full historical archive — fork, modify, commercialize, no restrictions.

## License

[MIT](./LICENSE)
