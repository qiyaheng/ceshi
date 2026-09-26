# 金融研究员 Agent（FinResearcher）

一个面向 **A 股 + 美股** 的金融研究员 Agent 服务：输入股票代码，自动拉取行情/技术指标/市值数据，由大模型规划分析步骤并生成带来源溯源的研究报告。

核心设计原则：**数字和事实必须来自工具返回，模型只负责推理与表达**——避免 AI 编造数据。

## 架构

```
用户 / 第三方系统
   │  HTTP API（OpenAI 兼容 + 金融专属接口）
   ▼
FastAPI ── 鉴权（可选 Bearer Key）
   │
   ▼
Agent 编排（Function Calling 循环，多轮工具调用）
   ├─ 工具层：行情快照 / 技术指标(MA,RSI,MACD,波动率,回撤) / 市值概览 / 搜索
   ├─ 数据源：腾讯财经(主) → AkShare/yfinance(备)
   └─ 模型层：LiteLLM Router 多渠道自动降级
        方舟(主) → DeepSeek(备) → 自定义端点(兜底，如项目内置本地模型)
   ▼
报告生成（Markdown + 数据溯源轨迹 + 免责声明）
```

## 目录结构

```
├─ backend/
│  ├─ main.py               # FastAPI 入口
│  ├─ config.py             # 配置（读取 .env）
│  ├─ core/
│  │  ├─ llm.py             # LiteLLM Router：多渠道 + 自动降级 + NO_PROXY 直连本地
│  │  └─ agent.py           # Agent 循环（规划 → 调工具 → 总结）
│  ├─ tools/                # 金融工具（行情/指标/市值/缓存）
│  ├─ reports/generator.py  # 研报模板
│  └─ api/                  # 金融专属接口 + OpenAI 兼容接口
├─ models/                  # 本地 GGUF 模型存放目录（下载后生成）
├─ install_all.bat             # Windows 一键安装（装依赖+下模型+生成配置，双击即可）
├─ start_all.bat / stop_all.bat  # Windows 一键启动 / 停止（双击即可）
├─ scripts/
│  ├─ install_all.sh            # macOS/Linux 一键安装
│  ├─ start_all.sh / stop_all.sh # macOS/Linux 一键启动 / 停止
│  ├─ download_model.ps1/.sh     # 下载本地模型（Windows/macOS/Linux）
│  ├─ start_local_model.ps1/.sh  # 单独启动本地模型服务（端口 8081）
│  └─ smoke_test_agent.py        # 离线冒烟测试（无需模型）
├─ logs/                          # 一键启动后的运行日志（自动生成）
└─ .env.example             # 配置模板
```

## 模型说明

本项目默认（也是当前实测通过）的模型：

| 项 | 值 |
|---|---|
| 模型 | **Qwen3-4B-Instruct**（通义千问 3，阿里开源，Apache 2.0 可商用） |
| 文件格式 | GGUF，Q4_K_M 量化（约 2.5GB） |
| 存放位置 | 项目 `models/qwen3-4b-q4_k_m.gguf` |
| **API 调用模型名（id）** | `qwen3-4b`（由启动脚本的 `--model_alias` 指定，跨系统一致，避免路径斜杠在 JSON 转义中被破坏） |
| 下载源 | [ModelScope：Qwen/Qwen3-4B-GGUF](https://modelscope.cn/models/Qwen/Qwen3-4B-GGUF)（国内直连） |
| 推理引擎 | llama-cpp-python（自带 OpenAI 兼容服务，端口 8081） |
| 工具调用 | 支持 Function Calling（已实测 `<tool_call>` 正常解析） |
| 实测推理速度 | CPU 约 8 tokens/s；macOS 自动启用 Metal GPU 加速，更快 |

其他可用渠道（在 `.env` 中配置，LiteLLM 自动降级切换）：

- **火山方舟**（主渠道，需 Key）：豆包 Seed / DeepSeek V4 / GLM-5.3 等
- **DeepSeek 官方**（备渠道，需 Key）
- **任何 OpenAI 兼容端点**（兜底，免 Key）：本项目内置本地模型即属此类；也可填 Ollama（`http://localhost:11434/v1`）、LM Studio（`http://localhost:1234/v1`）等

如需换用其他本地模型（如更小的 Qwen3-1.7B 或更大的 8B），重新下载对应 GGUF 后修改 `scripts/start_local_model` 脚本中的文件名和 `.env` 的 `CUSTOM_MODEL` 即可。

## 环境要求

- Python 3.10+（建议 3.11/3.12）
- Windows 10/11、macOS、Linux 均可
- 本地模型路线：≥ 8GB 内存（CPU 即可运行，速度约 8 tokens/s）

## 快速开始（只做一次：安装；以后：启动）

整个使用流程只有三件事：**① 装好 Python → ② 一键安装 → ③ 一键启动**。

### 第 0 步：安装 Python（电脑上没有才需要）

到 https://www.python.org/downloads/ 下载 Python 3.10 或更高版本（建议 3.12）。
**Windows 安装时务必勾选最下方的 `Add Python to PATH`**，然后点 Install。

### 第 1 步：一键安装（装依赖 + 下模型 + 生成配置，全自动）

脚本会自动完成：创建独立运行环境 → 安装全部依赖 → 下载 2.5GB 本地模型 → 生成 `.env`。
**全程约 15~40 分钟**（主要是下载模型的时间），中途可以去做别的事。

**Windows**：在项目文件夹里**双击 `install_all.bat`**，按提示按任意键开始。

**macOS / Linux**：在项目根目录执行：

```bash
bash scripts/install_all.sh
```

> macOS 首次安装会弹窗要求装 Xcode 命令行工具，按提示装完后重新运行一次安装脚本即可；
> Linux 如提示缺编译工具，先执行 `sudo apt install build-essential cmake python3-venv`（Ubuntu/Debian）。
> 安装脚本可重复运行，已完成的步骤（如已下载的模型）会自动跳过，失败后修好网络重跑即可。

### （可选）手动安装——想自己控制每一步时看这里

一键脚本等价于下面这些命令，排错时也可以分步手动执行：

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
.\.venv\Scripts\python.exe -m pip install "transformers<5" sse-starlette starlette-context
powershell -ExecutionPolicy Bypass -File scripts\download_model.ps1
copy .env.example .env

# macOS / Linux (bash)
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip install llama-cpp-python   # macOS 自动启用 Metal GPU 加速
./.venv/bin/python -m pip install "transformers<5" sse-starlette starlette-context
bash scripts/download_model.sh
cp .env.example .env
```

下载的模型默认是 Qwen3-4B（Q4_K_M 量化，支持工具调用），存到 `models/` 目录，权重随项目走、断网也能跑。

### 关于 .env 配置（安装脚本已自动生成，无需手动操作）

安装脚本已经自动从模板生成了 `.env`，默认指向本地模型（`CUSTOM_MODEL=qwen3-4b`），**不用改任何东西**。
以后有云端 Key，再往里面填 `ARK_API_KEY`（火山方舟，主渠道）或 `DEEPSEEK_API_KEY`（备渠道），故障时自动降级。

### 第 2 步：启动服务（以后每天用，只需这一步）

本项目需要同时跑**两个**服务，一键脚本会帮你把两个都拉起来：

| 服务 | 端口 | 作用（大白话） |
|---|---|---|
| 本地模型服务 | 8081 | "大脑"，真正负责思考和说话的 AI 模型 |
| 后端 API 服务 | 8080 | "秘书"，接收你的请求、指挥大脑调用查行情等工具 |

**Windows**：到项目文件夹里**双击 `start_all.bat`** 即可。
（脚本会自动检查环境、缺 `.env` 时自动创建，然后弹出两个黑色命令行窗口分别运行两个服务。）

**macOS / Linux**：在项目根目录执行一条命令：

```bash
bash scripts/start_all.sh
```

两个服务会在后台运行，日志写在 `logs/model.log` 和 `logs/backend.log`。

**怎么算启动成功？**

- Windows：两个黑窗口里都出现 `Uvicorn running on http://127.0.0.1:xxxx`；
- 浏览器打开 http://localhost:8080/health ，看到 `{"status":"ok"...}` 就说明秘书已就位；
- 模型第一次启动要加载 2.5GB 权重，大约等 30~60 秒，期间窗口里的日志在滚动是正常的。

> 注意：Windows 那两个黑窗口**不能关**（最小化可以），关了对应服务就停了。停止见后面的「一键停止」。

### （可选）手动启动——想知道每条命令在干什么时看这里

一键脚本本质上就是帮你执行下面这些动作。需要手动操作时，打开**两个终端窗口**（Windows 可用 PowerShell，macOS/Linux 用终端），都先 `cd` 到项目根目录。

**终端窗口 A —— 启动大脑（模型服务）：**

```bash
# Windows
powershell -ExecutionPolicy Bypass -File scripts\start_local_model.ps1
# macOS / Linux
bash scripts/start_local_model.sh
```

逐段解释：`powershell -File 脚本.ps1` = 用 PowerShell 运行脚本；`-ExecutionPolicy Bypass` = 临时允许运行本地脚本（否则 Windows 默认可能拦截）。看到 `Uvicorn running on http://127.0.0.1:8081` 说明大脑已就绪。

**终端窗口 B —— 启动秘书（后端 API）：**

```bash
# Windows
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8080
# macOS / Linux
./.venv/bin/python -m uvicorn backend.main:app --port 8080
```

逐段解释：`.venv\Scripts\python.exe` = 用本项目自己的 Python（不是系统的）；`-m uvicorn backend.main:app` = 用 uvicorn 这个服务器程序加载 `backend/main.py` 里的应用；`--port 8080` = 监听 8080 端口。

### 第 3 步：生成研报

```bash
curl -X POST http://localhost:8080/v1/research/equity-report ^
  -H "Content-Type: application/json" -d "{\"symbol\":\"600519\"}"
```

> macOS/Linux 把行尾 `^` 换成 `\`。

> 本地 CPU 推理较慢，一份报告需要数分钟，属正常现象。

## 从 GitHub 下载后如何使用（给别人看的最短流程）

仓库**不包含**三样东西（体积大或含隐私，无法随 Git 传输）：Python 依赖环境 `.venv`、2.5GB 模型文件、`.env` 配置。
所以 clone 之后**不能直接运行**，但只需"装 Python + 双击一次安装脚本"即可补齐：

```bash
# 1. 下载代码（或在仓库页面点 Code → Download ZIP 解压）
git clone https://github.com/qiyaheng/ceshi.git
cd ceshi

# 2. 确认已装 Python 3.10+（没装就去 python.org，Windows 勾选 Add Python to PATH）

# 3. 一键安装（自动装依赖、下载 2.5GB 模型、生成 .env，约 15~40 分钟）
#    Windows：双击 install_all.bat
#    macOS/Linux：
bash scripts/install_all.sh

# 4. 启动
#    Windows：双击 start_all.bat
#    macOS/Linux：
bash scripts/start_all.sh

# 5. 停止
#    Windows：双击 stop_all.bat
#    macOS/Linux：
bash scripts/stop_all.sh
```

| 双击的文件（Windows） | 什么时候用 | 会做什么 |
|---|---|---|
| `install_all.bat` | **只有第一次** | 装依赖、下模型、生成配置（只做一次，约 15~40 分钟） |
| `start_all.bat` | **每次使用时** | 启动两个服务 |
| `stop_all.bat` | 用完后 | 停止两个服务、释放端口 |

> 最低配置：8GB 内存、约 6GB 磁盘空间（模型 2.5GB + 依赖约 1GB）。全程不需要任何 API Key，断网也能用。

## API 一览

| 接口 | 说明 |
|---|---|
| `POST /v1/research/equity-report` | 一键生成个股研报（symbol 如 `600519` / `AAPL`） |
| `POST /v1/agent/chat` | 自由对话，Agent 自动调用工具 |
| `POST /v1/chat/completions` | **OpenAI 兼容接口**，可直接接入 TraeCode、Dify 等第三方系统 |
| `GET /health` | 健康检查 |

在 `.env` 设置 `SERVICE_API_KEY` 后，所有接口需携带 `Authorization: Bearer <key>`。

### 接入 TraeCode（添加模型服务商）

| 字段 | 值 |
|---|---|
| 服务商名称 | `金融研究员 Agent`（任意名称，仅作显示） |
| Base URL | `http://localhost:8081/v1`（直连本地模型服务；若要走带 Agent 工具链的后端，填 `http://localhost:8080/v1`） |
| API Key | `none`（**不能空着**，否则密钥显示"未配置"；本地服务不校验，填任意非空字符串即可） |
| 模型 ID | `qwen3-4b`（**必须和服务端 `GET /v1/models` 返回的完全一致**；服务通过 `--model_alias` 固定为该值，三系统通用） |
| 超时时间（秒） | `300`（本地 CPU 推理约 8 tokens/s，超时太短会中断生成） |

## 代理注意事项

本机若开了系统代理/Clash 等，可能劫持 localhost 请求导致 502。本项目已做双保险：

1. 代码内内置 `NO_PROXY=localhost,127.0.0.1`，回环地址强制直连；
2. 所有文档与默认配置统一使用 `localhost`。

若仍遇 502/连接拒绝，请检查代理软件的"绕过本地地址"规则。

## 停止服务

### 方法一：一键停止（推荐）

**Windows**：到项目文件夹里**双击 `stop_all.bat`**。
它会自动找到占用 8080、8081 端口的进程并结束，看到「服务均已停止，端口已释放」即完成。

**macOS / Linux**：

```bash
bash scripts/stop_all.sh
```

它先按启动时记录的进程号停止服务，再用端口检查兜底。

### 方法二：手动停止（了解原理）

- **手动方式启动的**：在两个终端窗口里分别按 `Ctrl + C` 即可；
- **窗口已经关了 / 一键脚本启动的**，需要"按端口找进程再结束"：

```powershell
# Windows (PowerShell) 逐条执行
netstat -ano | findstr ":8081"     # 看最后一列的数字（PID）
taskkill /PID 那个数字 /F           # 把数字替换成上面看到的 PID
netstat -ano | findstr ":8080"
taskkill /PID 那个数字 /F
```

命令解释：`netstat -ano` = 列出本机所有网络连接和占用它们的进程号；`findstr ":8081"` = 只筛选 8081 端口的行；`taskkill /PID xxx /F` = 强制结束指定进程号的程序。

```bash
# macOS / Linux（一条命令直接按端口结束）
lsof -ti :8081 | xargs kill -9      # 模型服务
lsof -ti :8080 | xargs kill -9      # 后端 API
```

**确认已停掉**：再运行一次上面的查询命令，**没有任何输出**就代表端口空了、服务停了。

## 删除文件（卸载/清理）

必须**先停止服务再删文件**，否则模型文件被进程占用，Windows 下无法删除。

本项目所有文件都在项目目录内，无系统级安装，按需删除：

| 要清理的内容 | 位置 | 说明 |
|---|---|---|
| 本地模型（约 2.5GB） | `models/` | 删除后重新运行 download 脚本可再下载 |
| Python 依赖 | `.venv/` | 删除后按"快速开始"重新安装 |
| 分词器缓存（约几十 MB） | Windows：`C:\Users\<用户名>\.cache\huggingface`<br>macOS/Linux：`~/.cache/huggingface` | 本地模型服务的工具调用分词器 |
| 配置与生成物 | `.env`、`reports_output/` | 你的 Key 和生成的研报 |

完全卸载（停止服务后）：

```powershell
# Windows：在项目上级目录执行
rmdir /s /q 金融研究员trae
```

```bash
# macOS / Linux：在项目上级目录执行
rm -rf 金融研究员trae
```

## 离线验证（无需模型）

`scripts/smoke_test_agent.py` 使用**内置假 LLM（FakeLLM）**驱动真实工具链，不加载任何模型、不需要 Key，用于验证"工具调用 → 数据 → 研报模板"链路是否完好：

```bash
# Windows
.\.venv\Scripts\python.exe scripts\smoke_test_agent.py

# macOS / Linux
./.venv/bin/python scripts/smoke_test_agent.py
```

## 免责声明

本系统输出仅供研究参考，不构成投资建议。行情数据来自公开接口，商用前请确认数据源授权；面向公众提供服务需完成 ICP 及生成式人工智能算法备案。
