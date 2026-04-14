# ASM LangChain Integration

将 ASM (Agent Service Manifest) 的Service发现与Scoring能力集成到 LangChain Agent 中。

## 组件

### ASMRegistryTool

LangChain `BaseTool`，支持自然语言Query ASM Registry。

- 解析自然语言Query，自动推断 taxonomy 和偏好方向
- 使用 `scorer.py` 的 `filter_services` + `score_topsis` 进行Scoring排序
- 返回 Top 3 推荐Service及Scoring详情

```python
from asm_tools import ASMRegistryTool

tool = ASMRegistryTool(manifests_dir="path/to/manifests")
result = tool._run("cheapest LLM for chat")
```

**支持的Query模式：**

| QueryExample | 推断的 taxonomy | 偏好方向 |
|---|---|---|
| `"best LLM for chat"` | `ai.llm.chat` | quality |
| `"cheapest image generation"` | `ai.vision.image_generation` | cost |
| `"fast text-to-speech"` | `ai.audio.tts` | speed |
| `"reliable embedding model"` | `ai.llm.embedding` | reliability |
| `"GPU compute"` | `ai.compute.gpu` | balanced |

### ASMComparisonTool

对比两个或多个Service的 manifest 差异。

```python
from asm_tools import ASMComparisonTool

tool = ASMComparisonTool(manifests_dir="path/to/manifests")
result = tool._run("openai/gpt-4o@2024-11-20, anthropic/claude-sonnet-4@4.0")
```

### ASMReceiptCallback

LangChain `BaseCallbackHandler`，自动捕获Service选择并生成 IETF ACTA 格式的 receipt。

```python
from asm_callback import ASMReceiptCallback

callback = ASMReceiptCallback(
    output_dir="./receipts",
    agent_id="my-agent",
)
```

**Receipt 格式（asm:service_selection）：**

```json
{
  "@context": ["https://www.w3.org/2018/credentials/v1", "https://asm-protocol.org/receipts/v1"],
  "type": ["VerifiableCredential", "ASMServiceSelectionReceipt"],
  "issuer": "my-agent",
  "credentialSubject": {
    "type": "asm:service_selection",
    "service_id": "openai/gpt-4o@2024-11-20",
    "taxonomy": "ai.llm.chat",
    "selection_score": 0.8234,
    "selection_reasoning": "...",
    "roster_snapshot": ["openai/gpt-4o@2024-11-20", "anthropic/claude-sonnet-4@4.0"],
    "method": "TOPSIS"
  }
}
```

## 安装

```bash
pip install -r requirements.txt
```

依赖：
- `langchain-core >= 0.2` — LangChain 核心库（BaseTool, BaseCallbackHandler）
- `pydantic >= 2.0` — 数据验证
- ASM `scorer.py` — Scoring逻辑（通过 sys.path 自动引入，无需额外安装）

## 运行演示

```bash
python demo_notebook.py
```

演示无需 API key，使用本地 manifest 文件和 mock 数据。

## 集成到 LangChain Agent

```python
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

from asm_tools import ASMRegistryTool, ASMComparisonTool
from asm_callback import ASMReceiptCallback

# Tool
tools = [
    ASMRegistryTool(manifests_dir="../../manifests"),
    ASMComparisonTool(manifests_dir="../../manifests"),
]

# Callback
receipt_callback = ASMReceiptCallback(output_dir="./receipts", agent_id="my-agent")

# Agent
llm = ChatOpenAI(model="gpt-4o", temperature=0)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an AI service broker. Use ASM tools to find and compare services."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, callbacks=[receipt_callback], verbose=True)

result = executor.invoke({"input": "Find me the best LLM under $10/M tokens"})
```

## 架构

```
User Query → LangChain Agent
                ↓
          ASMRegistryTool._run(query)
                ↓
          _parse_natural_query() → Constraints + Preferences
                ↓
          scorer.select_service() → filter + TOPSIS
                ↓
          Top 3 Results → Agent 选择 #1
                ↓
          ASMReceiptCallback.on_tool_end()
                ↓
          Receipt JSON → ./receipts/
```
