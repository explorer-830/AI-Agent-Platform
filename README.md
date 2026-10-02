# AI-Agent-Platform

一个基于 FastAPI、Streamlit、LangGraph 和 DeepSeek API 实现的智能面试系统。

用户上传 PDF 简历并填写岗位描述后，系统分析候选人的技术背景，生成面试问题，对回答进行评分与评价，并根据表现继续追问或切换话题。完成面试后，生成包含综合评分、优点、薄弱点和改进建议的个人报告。

## 项目功能

- PDF 简历上传与文字解析
- 结合简历和岗位要求分析候选人背景
- 五轮面试问答
- 每轮回答的评分、评价与薄弱点反馈
- 根据评分继续追问或切换技术话题
- 个人面试报告生成
- 聊天记录展示与新面试会话创建
- SQLite 面试状态持久化
- 日志记录与基础异常处理

## 技术栈

| 技术 | 用途 |
| --- | --- |
| Python | 项目主要开发语言 |
| FastAPI | 后端 API |
| Uvicorn | 后端服务运行 |
| Streamlit | 前端交互页面 |
| LangGraph | 面试流程编排与状态管理 |
| DeepSeek API | 简历分析、出题、评分和报告生成 |
| pypdf | PDF 文字提取 |
| SQLite | 面试状态持久化 |
| python-dotenv | 环境变量加载 |

## 系统架构

```text
用户
  │
  ▼
Streamlit 前端
  │ HTTP 请求
  ▼
FastAPI 后端
  │
  ▼
LangGraph 面试流程
  ├── DeepSeek API：分析、出题、评价、报告
  └── SQLite：保存面试状态
```

Streamlit 负责简历上传、岗位填写、回答提交和结果展示，FastAPI 提供面试接口，LangGraph 管理各阶段的执行顺序与会话状态。

## 面试流程

```text
上传简历与岗位描述
        ↓
分析候选人背景与岗位要求
        ↓
生成面试问题
        ↓
等待并接收回答
        ↓
评价回答、保存记录、更新轮次
        ↓
继续追问 / 切换技术话题
        ↓
完成五轮回答后生成报告
```

### 评分与分支判断

每轮评价包含三个字段：

```json
{
  "score": 80,
  "reason": "回答评价",
  "weakness": "薄弱点"
}
```

前四轮中：

- 评分低于 80 分：围绕回答中的薄弱点继续追问。
- 评分达到 80 分：选择新的技术方向并生成问题。

第五轮回答完成后生成个人报告。报告提示词要求参考各轮评分的平均值，输出综合评分、总体评价、优点、薄弱点和改进建议。

### 状态管理

面试状态包括简历路径、岗位描述、当前问题与回答、面试轮次、历史记录、当前评价和最终报告等信息。

每场面试使用独立的 `session_id`，作为 LangGraph 的线程标识。流程在评价节点前暂停，收到回答后更新状态，再恢复执行。

SQLite 保存流程检查点，Streamlit 的 `session_state` 保存当前页面的聊天记录、会话 ID 和报告。

## 项目结构

```text
AI-Agent-Platform/
├── app/
│   ├── api.py              # FastAPI 面试接口
│   └── main.py             # LangGraph 流程与模型调用
├── frontend/
│   └── main.py             # Streamlit 页面
├── .env.example            # 环境变量示例
├── .gitignore
├── requirements.txt
└── README.md
```

运行后会生成 `uploads/` 和 `interview_checkpoints.sqlite` 等本地数据文件，这些文件已通过 `.gitignore` 排除。

## API 接口

### POST `/interview/start`

接收 PDF 简历和岗位描述，创建面试会话。

使用表单参数：

| 参数 | 说明 |
| --- | --- |
| `file` | PDF 简历 |
| `job_description` | 岗位描述 |

处理流程：

```text
保存简历 → 提取文字 → 分析候选人与岗位 → 生成第一道题
```

返回示例：

```json
{
  "curr_question": "请结合你的项目说明……",
  "session_id": "生成的会话ID"
}
```

### POST `/interview/answer`

接收会话 ID 和当前回答，恢复面试流程。

请求示例：

```json
{
  "session_id": "会话ID",
  "curr_answer": "本轮回答"
}
```

正常轮次返回评价和下一题；最后一轮返回 `final_report` 和 `session_id`。其中 `final_report` 是包含报告内容的 JSON 字符串。

会话不存在时返回 404，前端提示重新开始面试。

## 本地运行

当前开发环境为 Python 3.13，以下命令使用 Windows PowerShell。

### 1. 下载项目

```powershell
git clone https://github.com/explorer-830/AI-Agent-Platform.git
cd AI-Agent-Platform
```

### 2. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 3. 配置环境变量

复制配置示例：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`，填写自己的 DeepSeek API 密钥：

```dotenv
Deepseek_API_KEY=your_api_key_here
```

变量名需要与代码保持一致。真实密钥只保存在本地 `.env` 中，不要提交到 GitHub。

模型名称在 `app/main.py` 中设置，运行前需确保账户支持配置的模型并有可用额度。

### 4. 启动 FastAPI

在项目根目录、已启用虚拟环境的终端中运行：

```powershell
python -m uvicorn app.api:app --reload
```

- 后端地址：http://127.0.0.1:8000
- 接口文档：http://127.0.0.1:8000/docs

### 5. 启动 Streamlit

另开一个终端，进入同一个项目根目录并运行：

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run frontend/main.py
```

前端默认地址：http://localhost:8501，以终端实际输出为准。

## 前端使用

1. 在侧边栏上传 PDF 简历。
2. 填写目标岗位描述，点击“开始面试”。
3. 在底部输入框回答问题并提交。
4. 查看评分、评价、薄弱点和下一道题。
5. 完成五轮回答后查看个人面试报告。
6. 再次点击“开始面试”，创建新会话并清空页面上的旧聊天和报告。

## 日志与异常处理

后端使用 Python `logging` 记录异常，保留报错堆栈；调试信息使用 DEBUG 级别记录。

当前包含以下处理：

- 模型请求超时
- 会话不存在
- 后端运行异常
- PDF 读取失败、加密或无可提取文字
- 评分与报告的 JSON 解析失败
- 前端请求超时和连接异常

前端两个面试请求的超时均为 120 秒。非成功响应优先展示后端返回的 `detail`。

## 项目状态与说明

目前已完成简历分析、面试问答、评分分支、状态保存和报告展示，并已进行一次完整面试及重新开始的手动测试。异常场景尚未全部实测。

- 当前 PDF 解析不包含 OCR，请上传未加密、包含可提取文字的 PDF。
- 简历和回答会发送给模型服务，请使用已获授权的材料。
- 前端超时不代表后端任务已取消，避免连续重复提交。
- 当前模型请求采用非流式返回。
- 评分和报告由模型生成，用于模拟面试与练习参考。

## 后续计划

后续将重点优化前端，将当前 Streamlit 页面逐步迁移到 Vue，继续使用 FastAPI 提供后端接口。

- 使用 Vue 构建面试页面，完善简历上传、岗位填写和回答提交等交互。
- 优化聊天布局，让题目、回答、评分和评价更清晰。
- 改进加载状态、错误提示和提交按钮状态，减少重复提交。
- 优化报告展示，突出综合评分、优点、薄弱点和改进建议。
