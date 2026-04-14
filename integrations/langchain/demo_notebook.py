#!/usr/bin/env python3
"""ASM LangChain 集成 — 完整演示

本文件模拟 Jupyter Notebook 风格，用注释分隔 cell。
演示完整流程：创建 agent → 用 ASMRegistryTool Query → 选择Service → ASMReceiptCallback 记录。

无需真实 API key，使用 mock LLM 数据演示。
"""

# %% Cell 1: 环境准备与导入
# ============================================================

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

# 确保可以导入本地模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from asm_tools import ASMRegistryTool, ASMComparisonTool
from asm_callback import ASMReceiptCallback

print("✅ ASM LangChain 集成模块导入成功")
print(f"   ASMRegistryTool:   asm_registry")
print(f"   ASMComparisonTool: asm_comparison")
print(f"   ASMReceiptCallback: 已Load")


# %% Cell 2: 初始化Tool和Callback
# ============================================================

# manifests 目录（使用项目中的真实 manifest 文件）
MANIFESTS_DIR = str(Path(__file__).resolve().parent.parent.parent / "manifests")

# 创建临时目录存放 receipt
RECEIPT_DIR = tempfile.mkdtemp(prefix="asm_receipts_")

print(f"\n📂 Manifests 目录: {MANIFESTS_DIR}")
print(f"📂 Receipt 输出目录: {RECEIPT_DIR}")

# 初始化Tool
registry_tool = ASMRegistryTool(manifests_dir=MANIFESTS_DIR)
comparison_tool = ASMComparisonTool(manifests_dir=MANIFESTS_DIR)

# 初始化Callback
receipt_callback = ASMReceiptCallback(
    output_dir=RECEIPT_DIR,
    agent_id="demo-langchain-agent",
    verbose=True,
)

print("\n✅ Tool和Callback已初始化")


# %% Cell 3: 模拟 Agent Query — 寻找最佳 LLM Service
# ============================================================

print("\n" + "=" * 70)
print("  场景 1: Agent 需要一个高质量的 LLM chat Service")
print("=" * 70)

query_1 = "I need the best quality LLM for chat"

# 模拟 on_tool_start Callback
receipt_callback.on_tool_start(
    serialized={"name": "asm_registry"},
    input_str=query_1,
)

# 执行Query
result_1 = registry_tool._run(query=query_1)
print(f"\n{result_1}")

# 模拟 on_tool_end Callback — 自动生成 receipt
print("\n--- Receipt 生成 ---")
receipt_callback.on_tool_end(output=result_1)


# %% Cell 4: 模拟 Agent Query — 寻找便宜的图像生成Service
# ============================================================

print("\n" + "=" * 70)
print("  场景 2: Agent 需要一个便宜的图像生成Service")
print("=" * 70)

query_2 = "cheapest image generation service"

receipt_callback.on_tool_start(
    serialized={"name": "asm_registry"},
    input_str=query_2,
)

result_2 = registry_tool._run(query=query_2)
print(f"\n{result_2}")

print("\n--- Receipt 生成 ---")
receipt_callback.on_tool_end(output=result_2)


# %% Cell 5: 模拟 Agent Query — 快速的 TTS Service
# ============================================================

print("\n" + "=" * 70)
print("  场景 3: Agent 需要一个快速的 TTS Service")
print("=" * 70)

query_3 = "fast text-to-speech service"

receipt_callback.on_tool_start(
    serialized={"name": "asm_registry"},
    input_str=query_3,
)

result_3 = registry_tool._run(query=query_3)
print(f"\n{result_3}")

print("\n--- Receipt 生成 ---")
receipt_callback.on_tool_end(output=result_3)


# %% Cell 6: Service对比
# ============================================================

print("\n" + "=" * 70)
print("  场景 4: 对比两个 LLM Service")
print("=" * 70)

comparison_result = comparison_tool._run(
    service_ids="openai/gpt-4o@2024-11-20, anthropic/claude-sonnet-4@4.0"
)
print(f"\n{comparison_result}")


# %% Cell 7: 对比图像生成Service
# ============================================================

print("\n" + "=" * 70)
print("  场景 5: 对比三个图像生成Service")
print("=" * 70)

comparison_result_2 = comparison_tool._run(
    service_ids="black-forest-labs/flux-1.1-pro@1.1, openai/dall-e-3@3.0, google/imagen-3@3.0"
)
print(f"\n{comparison_result_2}")


# %% Cell 8: 查看生成的 Receipt 文件
# ============================================================

print("\n" + "=" * 70)
print("  生成的 Receipt 文件")
print("=" * 70)

receipt_files = sorted(Path(RECEIPT_DIR).glob("receipt_*.json"))
print(f"\ntotal生成 {len(receipt_files)} 个 receipt 文件:\n")

for rf in receipt_files:
    print(f"📄 {rf.name}")
    with open(rf) as f:
        data = json.load(f)
    print(f"   Type: {data['type']}")
    print(f"   Service: {data['credentialSubject']['display_name']} "
          f"({data['credentialSubject']['service_id']})")
    print(f"   Scoring: {data['credentialSubject']['selection_score']}")
    print(f"   Query: {data['credentialSubject']['query']}")
    print(f"   时间: {data['issuanceDate']}")
    print()

# 展示一个完整的 receipt JSON
if receipt_files:
    print("--- 完整 Receipt Example ---")
    with open(receipt_files[0]) as f:
        print(json.dumps(json.load(f), indent=2, ensure_ascii=False))


# %% Cell 9: 模拟完整 LangChain Agent 流程（伪代码）
# ============================================================

print("\n" + "=" * 70)
print("  完整 LangChain Agent 集成Example（伪代码）")
print("=" * 70)

print("""
# 以下是真实 LangChain Agent 的集成方式（需要 LLM API key）:

from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

from asm_tools import ASMRegistryTool, ASMComparisonTool
from asm_callback import ASMReceiptCallback

# 1. 初始化Tool
tools = [
    ASMRegistryTool(manifests_dir="path/to/manifests"),
    ASMComparisonTool(manifests_dir="path/to/manifests"),
]

# 2. 初始化Callback
receipt_callback = ASMReceiptCallback(
    output_dir="./receipts",
    agent_id="my-agent-v1",
)

# 3. 创建 LLM 和 Agent
llm = ChatOpenAI(model="gpt-4o", temperature=0)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an AI service broker. Use ASM tools to find "
               "and compare AI services for the user."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])
agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(
    agent=agent,
    tools=tools,
    callbacks=[receipt_callback],
    verbose=True,
)

# 4. 运行 Agent
result = executor.invoke({
    "input": "Find me the cheapest LLM with quality > 0.8"
})
print(result["output"])

# Receipt 会自动保存到 ./receipts/ 目录
""")


# %% Cell 10: 总结
# ============================================================

print("=" * 70)
print("  演示完成")
print("=" * 70)
print(f"""
  ✅ ASMRegistryTool  — 自然语言Query → TOPSIS Scoring → Top 3 推荐
  ✅ ASMComparisonTool — 多Service manifest 对比表
  ✅ ASMReceiptCallback — 自动记录选择理由 → IETF ACTA receipt

  生成了 {len(receipt_files)} 个 receipt 文件在: {RECEIPT_DIR}

  ASM 信任链:
  Query → Scoring选择 → Receipt 记录 → 信任积累 → 更好的未来选择
""")
