# AI Interview Workflow

基于 Vue 3、FastAPI、LangGraph、DeepSeek 和 SQLite 的五轮技术面试工作流。
上传简历与岗位描述，生成题目和本题评价规则，对回答作分维度评价，由后端计算分数，再追问或切换话题，最后生成报告。

## 流程与评分

简历/JD分析 → 生成题目和规则 → 暂停等待回答 → 分维度评价 → 保存历史 → 更新轮次 → 追问/换题/报告。

- `requirements`：只包含题目明确要求或完成任务必需的考察点。
- `reference_approaches`：可行方案示例，不是唯一答案。
- `error_criteria`：明确技术错误的判据，不把未说明当作错误。
- 正确性50%、要求覆盖30%、方案解释20%；等级 none/limited/partial/good/excellent 对应0/25/50/80/100。
- 模型给等级、理由和原文摘录；后端按固定权重计算总分，四舍五入。
- 摘录必须真实存在于回答中，每个考察点恰好评价一次；校验失败最多纠正一次。
- 空白回答由代码判断；非空占位回答应标记 non_substantive，不等于没有提交。
- 综合分由代码计算历史各轮平均值，模型只生成文字总结；优点不足时不凑数。
- 每轮保存规则、评价依据、评分版本、权重和等级映射。

固定权重只是可解释的初始设计，不是经过统计标定的客观评分标准。语义正确性和题目规则仍由模型判断，可能误判。

## 文件

- `app/api.py`：接口与会话初始化。
- `app/main.py`：工作流节点、模型调用、检查点。
- `app/scoring.py`：Pydantic契约、语义结构校验、确定性算分。
- `frontend-web/index.html`：Vue界面，与既有 score/reason/weakness 和 JSON字符串报告兼容。
- `tests/test_scoring.py`：离线测试和临时 SQLite 五轮执行/重开验证。
- `tests/run_model_eval.py`：显式运行的合成回答模型对比，会消耗模型额度。

## 本地运行

Python 3.13开发环境，先安装 `requirements.txt`，复制 `.env.example` 为 `.env`，填写 `Deepseek_API_KEY`。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m uvicorn app.api:app --reload --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
python -m http.server 4000 --bind 127.0.0.1 --directory frontend-web
```

打开 http://127.0.0.1:4000 。模型名称仍为项目原有 `deepseek-v4-flash`，运行需要账户支持该模型。

## API兼容性

- `GET /`：健康检查。
- `POST /interview/start`：PDF和岗位描述表单，返回 `session_id`、`curr_question`；评分规则仅保存于后端。
- `POST /interview/answer`：`session_id`和`curr_answer`，返回本题 `curr_evaluation` 和下一题；第五轮返回 JSON字符串 `final_report`。
- `curr_evaluation` 保留 `score/reason/weakness`，另有维度等级、考察点状态、摘录、明确错误、追问建议和评分版本。

旧检查点缺少规则时，为原题补规则，不读取答案倒推规则。不会主动改写旧历史分数；新旧版本混合的报告不代表统一量表。

## 验证

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -v
```

2026-10-08：20项离线测试通过。真实模型小样本验证包含常见方案、替代方案、部分回答、明确错误、数字占位，并验证结构化出题和报告。初次占位评分漏考察点，被校验拒绝；加入一次有限纠正后复测通过。报告初次五案例输出格式失败，精简上下文和总结后复测通过。这不是效果基准或稳定性证明。

可选模型测试（收费API，不会自动随单元测试运行）：

```powershell
.\.venv\Scripts\python.exe -B tests/run_model_eval.py --output work/model-evaluation.json
```

## 当前边界

五轮和80分路由仍保留；未增加流式输出、恢复页面入口、防重复提交、自动工具调用。检查点持久化不等于模型外部调用恰好一次。开始面试接口仍有同步调用，应在后续独立改动中处理。2026-10-08已用合成简历在隔离端口完成Vue浏览器五轮端到端验证，分数100/0/71/0/0，综合34分；覆盖换话题、追问和结束状态，无浏览器脚本错误。实际部署及完整异常场景仍未验证，修改后的代码需重启后端。
