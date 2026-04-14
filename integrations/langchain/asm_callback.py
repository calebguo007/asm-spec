"""ASM Receipt Callback — 自动记录Service选择并生成 receipt payload。

当 LangChain Agent 通过 ASMRegistryTool 选择了某个Service后，
ASMReceiptCallback 自动捕获选择结果，生成符合 IETF ACTA 格式的
receipt payload，并写入指定目录。
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler


class ASMReceiptCallback(BaseCallbackHandler):
    """LangChain Callback Handler — 捕获 ASM Service选择并生成 receipt。

    当 agent 调用 asm_registry Tool并获得结果后，自动:
    1. 从Tool输出中提取被选中的 #1 Service信息
    2. 生成 asm:service_selection receipt payload
    3. 将 receipt 写入 output_dir 目录

    参数:
        output_dir: receipt 文件输出目录（默认 ./receipts）
        agent_id:   agent 标识符（写入 receipt 的 issuer 字段）
        verbose:    是否打印日志
    """

    def __init__(
        self,
        output_dir: str = "./receipts",
        agent_id: str = "langchain-agent",
        verbose: bool = True,
    ):
        super().__init__()
        self.output_dir = output_dir
        self.agent_id = agent_id
        self.verbose = verbose
        self._last_query: Optional[str] = None

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Tool开始执行时，记录Query内容。"""
        tool_name = serialized.get("name", "")
        if tool_name == "asm_registry":
            self._last_query = input_str

    def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        """Tool执行完成后，解析结果并生成 receipt。"""
        # 只处理 ASM registry Tool的输出
        if not output or "ASM Registry Query结果" not in output:
            return

        # 解析 top 1 Service信息
        selection = self._parse_selection(output)
        if not selection:
            return

        # 生成 receipt payload
        receipt = self._build_receipt(selection, output)

        # 写入文件
        self._save_receipt(receipt)

    def _parse_selection(self, output: str) -> Optional[dict[str, Any]]:
        """从 ASMRegistryTool 的输出中解析 #1 Service信息。"""
        lines = output.strip().split("\n")
        selection: dict[str, Any] = {}

        in_first = False
        roster: list[str] = []

        for line in lines:
            stripped = line.strip()

            # 检测 #1 开始
            if stripped.startswith("#1 "):
                in_first = True
                selection["display_name"] = stripped[3:].strip()
                continue

            # 检测 #2 开始（#1 结束）
            if stripped.startswith("#2 ") or stripped.startswith("#3 "):
                in_first = False
                # 收集 roster（所有排名的 service_id）
                sid_match = re.search(r"Service ID\s*:\s*(.+)", stripped)

            if in_first:
                if stripped.startswith("Service ID"):
                    selection["service_id"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("Taxonomy"):
                    selection["taxonomy"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("Score"):
                    try:
                        selection["score"] = float(stripped.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif stripped.startswith("Breakdown"):
                    selection["breakdown"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("Reasoning"):
                    selection["reasoning"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("Latency p50"):
                    selection["latency_p50"] = stripped.split(":", 1)[1].strip()
                elif stripped.startswith("Uptime"):
                    try:
                        selection["uptime"] = float(stripped.split(":", 1)[1].strip())
                    except ValueError:
                        pass

            # 收集所有 service_id 用于 roster_snapshot
            sid_match = re.search(r"Service ID\s*:\s*(.+)", stripped)
            if sid_match:
                roster.append(sid_match.group(1).strip())

        selection["roster_snapshot"] = roster

        if "service_id" not in selection:
            return None

        return selection

    def _build_receipt(
        self,
        selection: dict[str, Any],
        raw_output: str,
    ) -> dict[str, Any]:
        """构建 asm:service_selection receipt payload (IETF ACTA 格式)。"""
        now = datetime.now(timezone.utc)

        receipt = {
            "@context": [
                "https://www.w3.org/2018/credentials/v1",
                "https://asm-protocol.org/receipts/v1",
            ],
            "type": [
                "VerifiableCredential",
                "ASMServiceSelectionReceipt",
            ],
            "id": f"urn:uuid:{uuid4()}",
            "issuer": self.agent_id,
            "issuanceDate": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "credentialSubject": {
                "type": "asm:service_selection",
                "service_id": selection.get("service_id", ""),
                "taxonomy": selection.get("taxonomy", ""),
                "display_name": selection.get("display_name", ""),
                "selection_score": selection.get("score", 0),
                "selection_reasoning": selection.get("reasoning", ""),
                "score_breakdown": selection.get("breakdown", ""),
                "declared_sla": {
                    "latency_p50": selection.get("latency_p50", ""),
                    "uptime": selection.get("uptime", 0),
                },
                "roster_snapshot": selection.get("roster_snapshot", []),
                "query": self._last_query or "",
                "method": "TOPSIS",
                "agent_id": self.agent_id,
                "selected_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }

        return receipt

    def _save_receipt(self, receipt: dict[str, Any]) -> None:
        """将 receipt 写入 JSON 文件。"""
        os.makedirs(self.output_dir, exist_ok=True)

        service_id = receipt["credentialSubject"]["service_id"]
        # 文件名安全处理
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", service_id)
        timestamp = int(time.time())
        filename = f"receipt_{safe_name}_{timestamp}.json"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2, ensure_ascii=False)

        if self.verbose:
            print(f"📝 ASM Receipt 已保存: {filepath}")
            print(f"   Service: {receipt['credentialSubject']['display_name']} "
                  f"({receipt['credentialSubject']['service_id']})")
            print(f"   Scoring: {receipt['credentialSubject']['selection_score']}")
