<p align="center">
  <a href="#简体中文">简体中文</a> |
  <a href="#繁體中文">繁體中文</a> |
  <a href="#english">English</a>
</p>

---

<h1 align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/Tests-Passing-brightgreen.svg" alt="Tests">
  <img src="https://img.shields.io/badge/Version-1.0.0-orange.svg" alt="Version">
</h1>

<h3 align="center">AIChatRouter-CLI</h3>

<p align="center">
  <strong>轻量级终端 AI 多模型智能聊天路由引擎</strong><br>
  Lightweight Terminal AI Multi-Model Intelligent Chat Routing Engine
</p>

<p align="center">
  <a href="https://github.com/gitstq/AIChatRouter-CLI">GitHub</a> &bull;
  <a href="https://github.com/gitstq/AIChatRouter-CLI/issues">Issues</a> &bull;
  MIT License
</p>

---

<a id="简体中文"></a>

## 简体中文

### 项目简介

**AIChatRouter-CLI** 是一个零外部依赖的终端 AI 聊天工具，支持多模型智能路由、实时成本追踪和完整的会话管理。灵感来源于 Google Gemini CLI 的终端 AI 交互体验，但采用供应商无关的设计理念，让你自由选择最合适的 AI 模型。

只需一个 Python 解释器，即可在终端中享受智能路由带来的高效与便捷。

### 核心特性

#### 🤖 六大 AI 供应商支持

| 供应商 | 支持模型 |
|--------|---------|
| **OpenAI** | GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo |
| **Anthropic** | Claude Sonnet 4, Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus |
| **Google Gemini** | Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.0 Flash |
| **智谱 GLM** | GLM-4-Plus, GLM-4, GLM-4-Flash |
| **DeepSeek** | DeepSeek-Chat, DeepSeek-Reasoner |
| **Ollama** | Llama3, Qwen2.5, CodeLlama, Mistral 等本地模型 |

#### 🧠 智能任务路由

内置基于关键词 + 启发式规则的任务分类器，自动识别输入类型并路由到最优模型：

- **编程** (coding) -- 代码编写、调试、算法实现
- **创意写作** (creative) -- 故事、诗歌、文案创作
- **分析推理** (analysis) -- 数据分析、逻辑论证、对比评估
- **问答** (qa) -- 知识查询、概念解释
- **翻译** (translation) -- 多语言互译
- **数学** (math) -- 计算、方程求解、公式推导
- **摘要总结** (summarization) -- 内容提炼、要点归纳

#### 💰 实时成本追踪

- 按模型/供应商精确统计 Token 用量
- 日/周/月消费报告，一目了然
- 自定义月度预算，超额自动预警
- 支持 JSON/CSV 格式导出使用数据

#### 🖥️ 交互式终端 UI

- 彩色输出 -- 不同角色、不同信息类型一目了然
- 流式显示 -- 打字动画效果，实时呈现 AI 回复
- 多行输入 -- `Ctrl+Enter` 换行，`Enter` 发送
- 15+ 内置命令 -- `/help`、`/model`、`/cost`、`/export` 等
- 状态栏 -- 实时显示当前模型、供应商、Token 数和估算成本
- Markdown 格式化 -- 粗体、代码块、列表等终端渲染

#### 📦 零外部依赖

纯 Python 标准库实现，无需 `pip install` 任何第三方包。技术栈仅依赖：

`urllib` / `json` / `ssl` / `termios` / `tty` / `threading` / `csv` / `io`

兼容 Python 3.8+，可在任何安装了 Python 的环境中直接运行。

#### 🔄 会话管理

- 多会话支持，随时切换
- 对话持久化保存（JSON 格式）
- 上下文窗口自动裁剪，避免超出 Token 限制
- 内置系统提示模板，适配不同任务类型

#### ⛓️ 自动回退链

主模型不可用时，自动沿回退链选择替代模型，确保对话不中断。

#### ⚡ 一问一答模式

非交互式单次提问，适合脚本调用和管道集成：

```bash
aichatrouter ask "用简单的语言解释量子计算"
```

### 快速开始

#### 安装

```bash
# 克隆仓库
git clone https://github.com/gitstq/AIChatRouter-CLI.git
cd AIChatRouter-CLI

# 方式一：以开发模式安装（推荐）
pip install -e .

# 方式二：直接运行
python main.py config --init
```

#### 初始化配置

```bash
aichatrouter config --init
```

配置文件默认生成在 `~/.config/aichatrouter/config.yaml`，编辑该文件填入你的 API 密钥。

#### 开始聊天

```bash
# 启动交互式聊天
aichatrouter chat

# 指定供应商和模型
aichatrouter chat --provider anthropic --model claude-sonnet-4-20250514

# 一问一答模式
aichatrouter ask "用简单的语言解释量子计算"

# 测试路由结果
aichatrouter route-test "写一个 Python 快速排序"

# 查看可用模型
aichatrouter models

# 查看成本报告
aichatrouter cost
```

### 配置说明

配置文件采用 YAML 格式，支持多供应商、路由规则和成本追踪设置：

```yaml
# AIChatRouter 配置文件
# ==========================

providers:
  openai:
    api_key: "sk-xxx"
    base_url: "https://api.openai.com/v1"
    models:
      - name: "gpt-4o"
        cost_per_1k_input: 0.0025
        cost_per_1k_output: 0.01
      - name: "gpt-4o-mini"
        cost_per_1k_input: 0.00015
        cost_per_1k_output: 0.0006

  anthropic:
    api_key: "sk-ant-xxx"
    base_url: "https://api.anthropic.com"
    models:
      - name: "claude-sonnet-4-20250514"
        cost_per_1k_input: 0.003
        cost_per_1k_output: 0.015

  gemini:
    api_key: "your-gemini-key"
    models:
      - name: "gemini-2.5-pro"
        cost_per_1k_input: 0.00125
        cost_per_1k_output: 0.005

  zhipu:
    api_key: "your-zhipu-key"
    models:
      - name: "glm-4-plus"
        cost_per_1k_input: 0.005
        cost_per_1k_output: 0.005

  deepseek:
    api_key: "your-deepseek-key"
    models:
      - name: "deepseek-chat"
        cost_per_1k_input: 0.00014
        cost_per_1k_output: 0.00028

  ollama:
    base_url: "http://localhost:11434"
    models:
      - name: "llama3"
        cost_per_1k_input: 0.0
        cost_per_1k_output: 0.0

# 智能路由规则
routing:
  default_provider: "openai"
  default_model: "gpt-4o-mini"
  rules:
    coding:
      provider: "anthropic"
      model: "claude-sonnet-4-20250514"
      keywords: ["code", "function", "bug", "debug", "implement"]
    creative:
      provider: "anthropic"
      model: "claude-sonnet-4-20250514"
      keywords: ["write", "story", "creative", "poem"]
    analysis:
      provider: "openai"
      model: "gpt-4o"
      keywords: ["analyze", "compare", "explain"]
    simple:
      provider: "openai"
      model: "gpt-4o-mini"
      keywords: []

# 成本追踪设置
cost_tracking:
  enabled: true
  budget_monthly: 50.0
  data_dir: "~/.aichatrouter/usage"

# 通用参数
general:
  max_tokens: 4096
  temperature: 0.7
  timeout: 30
  retry_attempts: 3
```

### 聊天模式命令

在交互式聊天中，输入以下命令进行操作：

| 命令 | 说明 |
|------|------|
| `/help` | 显示所有可用命令 |
| `/model [name]` | 切换当前模型 |
| `/provider [name]` | 切换当前供应商 |
| `/clear` | 清空当前对话 |
| `/history` | 查看对话历史 |
| `/cost` | 显示成本报告 |
| `/export [format]` | 导出对话（json / markdown / text） |
| `/save [name]` | 保存当前会话 |
| `/load [name]` | 加载已保存的会话 |
| `/sessions` | 列出所有会话 |
| `/config` | 显示当前配置 |
| `/route-test [text]` | 测试文本的路由结果 |
| `/system [prompt]` | 设置系统提示 |
| `/compact` | 压缩对话上下文 |
| `/quit` | 退出聊天 |

### 设计理念

- **供应商无关** -- 灵感来自 Google Gemini CLI 的终端 AI 体验，但不绑定任何单一供应商
- **极致轻量** -- 零外部依赖，最大程度保证可移植性，一个文件拷贝即可使用
- **智能省钱** -- 简单任务自动路由到低成本模型，复杂任务才调用高端模型
- **隐私优先** -- 所有数据本地存储，不上传任何信息到第三方

### 开发与测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
python -m pytest tests/ -v

# 代码检查
make lint

# 清理构建产物
make clean
```

### 参与贡献

欢迎各种形式的贡献！无论是提交 Bug 报告、功能建议，还是直接发起 Pull Request。

1. Fork 本仓库
2. 创建功能分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m 'feat: add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 发起 Pull Request

### 许可证

本项目基于 [MIT License](https://opensource.org/licenses/MIT) 开源。

### 作者

**gitstq (琦琦)**

---

<a id="繁體中文"></a>

## 繁體中文

### 專案簡介

**AIChatRouter-CLI** 是一款零外部依賴的終端 AI 聊天工具，支援多模型智慧路由、即時成本追蹤與完整的會話管理。靈感源自 Google Gemini CLI 的終端 AI 互動體驗，但採用供應商無關的設計理念，讓你自由選擇最合適的 AI 模型。

只需一個 Python 直譯器，即可在終端中享受智慧路由帶來的高效與便捷。

### 核心特性

#### 🤖 六大 AI 供應商支援

| 供應商 | 支援模型 |
|--------|---------|
| **OpenAI** | GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo |
| **Anthropic** | Claude Sonnet 4, Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus |
| **Google Gemini** | Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.0 Flash |
| **智譜 GLM** | GLM-4-Plus, GLM-4, GLM-4-Flash |
| **DeepSeek** | DeepSeek-Chat, DeepSeek-Reasoner |
| **Ollama** | Llama3, Qwen2.5, CodeLlama, Mistral 等本地模型 |

#### 🧠 智慧任務路由

內建基於關鍵字 + 啟發式規則的任務分類器，自動識別輸入類型並路由至最佳模型：

- **程式設計** (coding) -- 程式碼撰寫、除錯、演算法實作
- **創意寫作** (creative) -- 故事、詩歌、文案創作
- **分析推理** (analysis) -- 資料分析、邏輯論證、對比評估
- **問答** (qa) -- 知識查詢、概念解釋
- **翻譯** (translation) -- 多語言互譯
- **數學** (math) -- 計算、方程求解、公式推導
- **摘要總結** (summarization) -- 內容提煉、要點歸納

#### 💰 即時成本追蹤

- 按模型/供應商精確統計 Token 用量
- 日/週/月消費報告，一目了然
- 自訂月度預算，超額自動預警
- 支援 JSON/CSV 格式匯出使用資料

#### 🖥️ 互動式終端 UI

- 彩色輸出 -- 不同角色、不同資訊類型一目了然
- 串流顯示 -- 打字動畫效果，即時呈現 AI 回覆
- 多行輸入 -- `Ctrl+Enter` 換行，`Enter` 發送
- 15+ 內建命令 -- `/help`、`/model`、`/cost`、`/export` 等
- 狀態列 -- 即時顯示當前模型、供應商、Token 數與估算成本
- Markdown 格式化 -- 粗體、程式碼區塊、列表等終端渲染

#### 📦 零外部依賴

純 Python 標準函式庫實作，無需 `pip install` 任何第三方套件。技術棧僅依賴：

`urllib` / `json` / `ssl` / `termios` / `tty` / `threading` / `csv` / `io`

相容 Python 3.8+，可在任何安裝了 Python 的環境中直接執行。

#### 🔄 會話管理

- 多會話支援，隨時切換
- 對話持久化儲存（JSON 格式）
- 上下文視窗自動裁剪，避免超出 Token 限制
- 內建系統提示範本，適配不同任務類型

#### ⛓️ 自動回退鏈

主模型不可用時，自動沿回退鏈選擇替代模型，確保對話不中斷。

#### ⚡ 一問一答模式

非互動式單次提問，適合腳本呼叫與管道整合：

```bash
aichatrouter ask "用簡單的語言解釋量子運算"
```

### 快速開始

#### 安裝

```bash
# 複製倉庫
git clone https://github.com/gitstq/AIChatRouter-CLI.git
cd AIChatRouter-CLI

# 方式一：以開發模式安裝（推薦）
pip install -e .

# 方式二：直接執行
python main.py config --init
```

#### 初始化設定

```bash
aichatrouter config --init
```

設定檔預設生成在 `~/.config/aichatrouter/config.yaml`，編輯該檔案填入你的 API 金鑰。

#### 開始聊天

```bash
# 啟動互動式聊天
aichatrouter chat

# 指定供應商和模型
aichatrouter chat --provider anthropic --model claude-sonnet-4-20250514

# 一問一答模式
aichatrouter ask "用簡單的語言解釋量子運算"

# 測試路由結果
aichatrouter route-test "寫一個 Python 快速排序"

# 查看可用模型
aichatrouter models

# 查看成本報告
aichatrouter cost
```

### 設定說明

設定檔採用 YAML 格式，支援多供應商、路由規則和成本追蹤設定：

```yaml
# AIChatRouter 設定檔
# ==========================

providers:
  openai:
    api_key: "sk-xxx"
    base_url: "https://api.openai.com/v1"
    models:
      - name: "gpt-4o"
        cost_per_1k_input: 0.0025
        cost_per_1k_output: 0.01
      - name: "gpt-4o-mini"
        cost_per_1k_input: 0.00015
        cost_per_1k_output: 0.0006

  anthropic:
    api_key: "sk-ant-xxx"
    base_url: "https://api.anthropic.com"
    models:
      - name: "claude-sonnet-4-20250514"
        cost_per_1k_input: 0.003
        cost_per_1k_output: 0.015

  gemini:
    api_key: "your-gemini-key"
    models:
      - name: "gemini-2.5-pro"
        cost_per_1k_input: 0.00125
        cost_per_1k_output: 0.005

  zhipu:
    api_key: "your-zhipu-key"
    models:
      - name: "glm-4-plus"
        cost_per_1k_input: 0.005
        cost_per_1k_output: 0.005

  deepseek:
    api_key: "your-deepseek-key"
    models:
      - name: "deepseek-chat"
        cost_per_1k_input: 0.00014
        cost_per_1k_output: 0.00028

  ollama:
    base_url: "http://localhost:11434"
    models:
      - name: "llama3"
        cost_per_1k_input: 0.0
        cost_per_1k_output: 0.0

# 智慧路由規則
routing:
  default_provider: "openai"
  default_model: "gpt-4o-mini"
  rules:
    coding:
      provider: "anthropic"
      model: "claude-sonnet-4-20250514"
      keywords: ["code", "function", "bug", "debug", "implement"]
    creative:
      provider: "anthropic"
      model: "claude-sonnet-4-20250514"
      keywords: ["write", "story", "creative", "poem"]
    analysis:
      provider: "openai"
      model: "gpt-4o"
      keywords: ["analyze", "compare", "explain"]
    simple:
      provider: "openai"
      model: "gpt-4o-mini"
      keywords: []

# 成本追蹤設定
cost_tracking:
  enabled: true
  budget_monthly: 50.0
  data_dir: "~/.aichatrouter/usage"

# 通用參數
general:
  max_tokens: 4096
  temperature: 0.7
  timeout: 30
  retry_attempts: 3
```

### 聊天模式命令

在互動式聊天中，輸入以下命令進行操作：

| 命令 | 說明 |
|------|------|
| `/help` | 顯示所有可用命令 |
| `/model [name]` | 切換當前模型 |
| `/provider [name]` | 切換當前供應商 |
| `/clear` | 清空當前對話 |
| `/history` | 檢視對話歷史 |
| `/cost` | 顯示成本報告 |
| `/export [format]` | 匯出對話（json / markdown / text） |
| `/save [name]` | 儲存當前會話 |
| `/load [name]` | 載入已儲存的會話 |
| `/sessions` | 列出所有會話 |
| `/config` | 顯示當前設定 |
| `/route-test [text]` | 測試文字的路由結果 |
| `/system [prompt]` | 設定系統提示 |
| `/compact` | 壓縮對話上下文 |
| `/quit` | 退出聊天 |

### 設計理念

- **供應商無關** -- 靈感來自 Google Gemini CLI 的終端 AI 體驗，但不綁定任何單一供應商
- **極致輕量** -- 零外部依賴，最大程度保證可移植性，一個檔案拷貝即可使用
- **智慧省錢** -- 簡單任務自動路由至低成本模型，複雜任務才呼叫高端模型
- **隱私優先** -- 所有資料本地儲存，不上傳任何資訊至第三方

### 開發與測試

```bash
# 安裝開發依賴
pip install -e ".[dev]"

# 執行測試
python -m pytest tests/ -v

# 程式碼檢查
make lint

# 清理建構產物
make clean
```

### 參與貢獻

歡迎各種形式的貢獻！無論是提交 Bug 回報、功能建議，還是直接發起 Pull Request。

1. Fork 本倉庫
2. 建立功能分支：`git checkout -b feature/your-feature`
3. 提交變更：`git commit -m 'feat: add your feature'`
4. 推送分支：`git push origin feature/your-feature`
5. 發起 Pull Request

### 授權條款

本專案基於 [MIT License](https://opensource.org/licenses/MIT) 開源。

### 作者

**gitstq (琦琦)**

---

<a id="english"></a>

## English

### Introduction

**AIChatRouter-CLI** is a zero-dependency terminal AI chat tool with intelligent multi-model routing, real-time cost tracking, and full session management. Inspired by the terminal AI experience of Google Gemini CLI, but built with a provider-agnostic philosophy that gives you the freedom to choose the best AI model for any task.

All you need is a Python interpreter to enjoy the efficiency and convenience of intelligent routing right from your terminal.

### Core Features

#### 🤖 Six AI Providers

| Provider | Supported Models |
|----------|-----------------|
| **OpenAI** | GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo |
| **Anthropic** | Claude Sonnet 4, Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus |
| **Google Gemini** | Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.0 Flash |
| **Zhipu/GLM** | GLM-4-Plus, GLM-4, GLM-4-Flash |
| **DeepSeek** | DeepSeek-Chat, DeepSeek-Reasoner |
| **Ollama** | Llama3, Qwen2.5, CodeLlama, Mistral and other local models |

#### 🧠 Smart Task Routing

A built-in task classifier powered by keyword matching and heuristic rules automatically identifies your input type and routes it to the optimal model:

- **Coding** -- Code writing, debugging, algorithm implementation
- **Creative Writing** -- Stories, poetry, copywriting
- **Analysis** -- Data analysis, logical reasoning, comparative evaluation
- **Q&A** -- Knowledge queries, concept explanations
- **Translation** -- Multi-language translation
- **Math** -- Calculations, equation solving, formula derivation
- **Summarization** -- Content distillation, key point extraction

#### 💰 Real-Time Cost Tracking

- Precise per-model/per-provider token usage statistics
- Daily, weekly, and monthly spending reports at a glance
- Customizable monthly budget with automatic overspend alerts
- Export usage data in JSON or CSV format

#### 🖥️ Interactive TUI

- Color-coded output -- Different roles and info types are visually distinct
- Streaming display -- Typing animation for real-time AI response rendering
- Multi-line input -- `Ctrl+Enter` for new lines, `Enter` to send
- 15+ built-in commands -- `/help`, `/model`, `/cost`, `/export`, and more
- Status bar -- Real-time display of current model, provider, token count, and estimated cost
- Markdown formatting -- Bold, code blocks, lists, and more rendered in the terminal

#### 📦 Zero Dependencies

Built entirely with the Python standard library -- no third-party packages required. The tech stack relies solely on:

`urllib` / `json` / `ssl` / `termios` / `tty` / `threading` / `csv` / `io`

Compatible with Python 3.8+, so you can run it in any environment with Python installed.

#### 🔄 Session Management

- Multi-session support with instant switching
- Conversation persistence (JSON format)
- Automatic context window trimming to avoid exceeding token limits
- Built-in system prompt templates tailored to different task types

#### ⛓️ Automatic Fallback Chain

When the primary model is unavailable, the system automatically selects an alternative along the fallback chain, ensuring uninterrupted conversations.

#### ⚡ One-Shot Mode

Non-interactive single-question mode, ideal for scripting and pipeline integration:

```bash
aichatrouter ask "Explain quantum computing in simple terms"
```

### Quick Start

#### Installation

```bash
# Clone the repository
git clone https://github.com/gitstq/AIChatRouter-CLI.git
cd AIChatRouter-CLI

# Option 1: Install in editable mode (recommended)
pip install -e .

# Option 2: Run directly
python main.py config --init
```

#### Initialize Configuration

```bash
aichatrouter config --init
```

The configuration file is generated by default at `~/.config/aichatrouter/config.yaml`. Edit this file to add your API keys.

#### Start Chatting

```bash
# Launch interactive chat
aichatrouter chat

# Specify provider and model
aichatrouter chat --provider anthropic --model claude-sonnet-4-20250514

# One-shot question
aichatrouter ask "Explain quantum computing in simple terms"

# Test routing
aichatrouter route-test "Write a Python sorting function"

# List available models
aichatrouter models

# View cost report
aichatrouter cost
```

### Configuration

The configuration file uses YAML format and supports multiple providers, routing rules, and cost tracking settings:

```yaml
# AIChatRouter Configuration
# ==========================

providers:
  openai:
    api_key: "sk-xxx"
    base_url: "https://api.openai.com/v1"
    models:
      - name: "gpt-4o"
        cost_per_1k_input: 0.0025
        cost_per_1k_output: 0.01
      - name: "gpt-4o-mini"
        cost_per_1k_input: 0.00015
        cost_per_1k_output: 0.0006

  anthropic:
    api_key: "sk-ant-xxx"
    base_url: "https://api.anthropic.com"
    models:
      - name: "claude-sonnet-4-20250514"
        cost_per_1k_input: 0.003
        cost_per_1k_output: 0.015

  gemini:
    api_key: "your-gemini-key"
    models:
      - name: "gemini-2.5-pro"
        cost_per_1k_input: 0.00125
        cost_per_1k_output: 0.005

  zhipu:
    api_key: "your-zhipu-key"
    models:
      - name: "glm-4-plus"
        cost_per_1k_input: 0.005
        cost_per_1k_output: 0.005

  deepseek:
    api_key: "your-deepseek-key"
    models:
      - name: "deepseek-chat"
        cost_per_1k_input: 0.00014
        cost_per_1k_output: 0.00028

  ollama:
    base_url: "http://localhost:11434"
    models:
      - name: "llama3"
        cost_per_1k_input: 0.0
        cost_per_1k_output: 0.0

# Smart routing rules
routing:
  default_provider: "openai"
  default_model: "gpt-4o-mini"
  rules:
    coding:
      provider: "anthropic"
      model: "claude-sonnet-4-20250514"
      keywords: ["code", "function", "bug", "debug", "implement"]
    creative:
      provider: "anthropic"
      model: "claude-sonnet-4-20250514"
      keywords: ["write", "story", "creative", "poem"]
    analysis:
      provider: "openai"
      model: "gpt-4o"
      keywords: ["analyze", "compare", "explain"]
    simple:
      provider: "openai"
      model: "gpt-4o-mini"
      keywords: []

# Cost tracking settings
cost_tracking:
  enabled: true
  budget_monthly: 50.0
  data_dir: "~/.aichatrouter/usage"

# General settings
general:
  max_tokens: 4096
  temperature: 0.7
  timeout: 30
  retry_attempts: 3
```

### Chat Mode Commands

While in interactive chat mode, use the following commands:

| Command | Description |
|---------|-------------|
| `/help` | Show all available commands |
| `/model [name]` | Switch the current model |
| `/provider [name]` | Switch the current provider |
| `/clear` | Clear the current conversation |
| `/history` | Show conversation history |
| `/cost` | Display cost report |
| `/export [format]` | Export conversation (json / markdown / text) |
| `/save [name]` | Save the current session |
| `/load [name]` | Load a saved session |
| `/sessions` | List all sessions |
| `/config` | Show current configuration |
| `/route-test [text]` | Test routing for given text |
| `/system [prompt]` | Set system prompt |
| `/compact` | Compact conversation context |
| `/quit` | Exit chat |

### Design Philosophy

- **Provider-Agnostic** -- Inspired by Google Gemini CLI's terminal AI experience, but not locked into any single provider
- **Ultra-Lightweight** -- Zero external dependencies for maximum portability; a single file copy is all you need
- **Smart Cost Savings** -- Simple tasks are automatically routed to cheaper models; premium models are only invoked when needed
- **Privacy-First** -- All data is stored locally; nothing is sent to third parties

### Development & Testing

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -v

# Lint check
make lint

# Clean build artifacts
make clean
```

### Contributing

Contributions of all kinds are welcome! Whether it's a bug report, a feature suggestion, or a pull request.

1. Fork this repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m 'feat: add your feature'`
4. Push the branch: `git push origin feature/your-feature`
5. Open a Pull Request

### License

This project is open-sourced under the [MIT License](https://opensource.org/licenses/MIT).

### Author

**gitstq (琦琦)**
