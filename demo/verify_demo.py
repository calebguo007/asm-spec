#!/usr/bin/env python3
"""
ASM Signed Receipts — 真实验签 Demo
====================================

本 demo 使用 @veritasacta/verify CLI 对一个真实签名的 ACTA receipt
进行 Ed25519 验签，并将提取的 payload 字段与 ASM manifest 声明值
做 trust delta 计算。

前置要求：
  - Node.js 环境（npx 可用）
  - npx @veritasacta/verify@0.2.4 --self-test 通过

运行方式：
  python3 demo/verify_demo.py

不需要 npm install，纯 Python + subprocess 调用 npx。
"""

import sys
import os
import json
import subprocess
import tempfile

# 将 scorer 加入 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scorer"))

from scorer import compute_trust_delta

# ── ANSI 颜色 ──────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"


def header(text: str):
    print(f"\n{BOLD}{CYAN}{'═' * 70}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 70}{RESET}")


def step(num: int, text: str):
    print(f"\n{BOLD}{YELLOW}  Step {num}: {text}{RESET}")


def ok(text: str, indent: int = 4):
    print(f"{' ' * indent}{GREEN}✓{RESET} {text}")


def fail(text: str, indent: int = 4):
    print(f"{' ' * indent}{RED}✗{RESET} {text}")


def info(text: str, indent: int = 4):
    print(f"{' ' * indent}{CYAN}→{RESET} {text}")


def dim(text: str, indent: int = 4):
    print(f"{' ' * indent}{DIM}{text}{RESET}")


# ── 内嵌的真实签名 Receipt ──────────────────────────────
# 来源：@veritasacta/verify@0.2.4 的 samples/sample-receipt.json
# 格式：ACTA v2 envelope，Ed25519 签名
# 此 receipt 可通过 npx @veritasacta/verify --self-test 验证

SAMPLE_RECEIPT = {
    "v": 2,
    "type": "decision_receipt",
    "algorithm": "ed25519",
    "kid": "kPrK_qmxVWaYVA9wwBF6Iuo3vVzz7TxHCTwXBygrS4k",
    "issuer": "sb:test",
    "issued_at": "2026-01-01T00:00:00Z",
    "payload": {
        "decision": "allow",
        "policy_digest": "sha256:abcdef0123456789",
        "scope": "my-service",
        "tool": "read_database",
        "tier": "signed-known",
        "mode": "shadow",
        "reason_code": "policy_match",
        "request_id": "req_test_001"
    },
    "signature": "324a966f8d4e6652e2270311c9682157d5adc01f1f019d84b24a1125220869a5c5a0fc0096ed3afffaa66ac36cfbbd97e60d9c5f7ad632a2cf11c45c2c50fd0d"
}

# 对应的 Ed25519 公钥（hex），来自 RFC 8032 Test Vector #1
# 也是 @veritasacta/verify self-test 使用的公钥
SIGNING_PUBLIC_KEY = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"

# ── 模拟的 ASM Manifest 声明值 ──────────────────────────
# 用于演示 trust delta 计算：将 receipt 的实际执行数据与 manifest 声明做对比
# 这里假设 receipt 对应的服务在 ASM manifest 中声明了以下 SLA

ASM_DECLARED = {
    "service_id": "example/my-service@1.0",
    "display_name": "My Service",
    "declared_latency_seconds": 0.800,   # manifest 声明 p50 延迟 800ms
    "declared_quality_score": 0.92,      # manifest 声明质量分 0.92
    "declared_uptime": 0.999,            # manifest 声明可用性 99.9%
    "declared_cost_per_unit": 0.003,     # manifest 声明每次请求 $0.003
}

# 模拟的实际执行指标（在真实场景中，这些数据来自 receipt 的度量字段或监控系统）
ACTUAL_METRICS = {
    "actual_latency_seconds": 0.950,     # 实际延迟 950ms（比声明慢 18.75%）
    "actual_quality_score": 0.91,        # 实际质量 0.91（接近声明）
    "actual_uptime": 0.997,              # 实际可用性 99.7%（略低于声明）
    "actual_cost_per_unit": 0.003,       # 实际成本（与声明一致）
}


# ── 核心函数 ────────────────────────────────────────────

def verify_receipt_with_cli(receipt: dict, public_key: str) -> dict:
    """
    通过 subprocess 调用 npx @veritasacta/verify 验证签名 receipt。

    将 receipt JSON 写入临时文件，然后调用 CLI 工具验证。
    返回 CLI 的 JSON 输出（解析后的 dict）。
    """
    # 写入临时文件
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(receipt, f, indent=2)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [
                "npx", "@veritasacta/verify@0.2.4",
                tmp_path,
                "--key", public_key,
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # 解析 JSON 输出
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError:
            output = {
                "valid": False,
                "error": "json_parse_error",
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        output["exit_code"] = result.returncode
        return output

    except FileNotFoundError:
        return {
            "valid": False,
            "error": "npx_not_found",
            "hint": "请确保 Node.js 已安装且 npx 在 PATH 中",
        }
    except subprocess.TimeoutExpired:
        return {
            "valid": False,
            "error": "timeout",
            "hint": "验证超时（30s），请检查网络或 npx 缓存",
        }
    finally:
        os.unlink(tmp_path)


def extract_payload_fields(receipt: dict) -> dict:
    """从 receipt 中提取关键 payload 字段。"""
    payload = receipt.get("payload", {})
    return {
        "type": receipt.get("type", "unknown"),
        "tool": payload.get("tool", "unknown"),
        "decision": payload.get("decision", "unknown"),
        "tier": payload.get("tier", "unknown"),
        "mode": payload.get("mode", "unknown"),
        "reason_code": payload.get("reason_code", "unknown"),
        "scope": payload.get("scope", "unknown"),
        "request_id": payload.get("request_id", "unknown"),
    }


def compute_trust_deltas(declared: dict, actual: dict) -> dict:
    """
    计算每个维度的 trust delta。
    复用 scorer.py 的 compute_trust_delta 函数。
    """
    dimensions = {
        "latency": ("declared_latency_seconds", "actual_latency_seconds"),
        "quality": ("declared_quality_score", "actual_quality_score"),
        "uptime": ("declared_uptime", "actual_uptime"),
        "cost": ("declared_cost_per_unit", "actual_cost_per_unit"),
    }

    deltas = {}
    for dim_name, (decl_key, actual_key) in dimensions.items():
        d = declared[decl_key]
        a = actual[actual_key]
        delta = compute_trust_delta(d, a)
        deltas[dim_name] = {
            "declared": d,
            "actual": a,
            "delta": round(delta, 4),
        }
    return deltas


# ── 主流程 ──────────────────────────────────────────────

def main():
    print(f"\n{BOLD}{'=' * 70}{RESET}")
    print(f"{BOLD}  ASM Signed Receipts — 真实验签 Demo{RESET}")
    print(f"{BOLD}  使用 @veritasacta/verify CLI 验证 ACTA 格式的 Ed25519 签名{RESET}")
    print(f"{BOLD}{'=' * 70}{RESET}")

    # ── Part 1: 展示内嵌的 Receipt ──
    header("Part 1: 内嵌的真实签名 Receipt")

    step(1, "ACTA v2 Envelope 结构")
    info(f"版本: v{SAMPLE_RECEIPT['v']}")
    info(f"类型: {SAMPLE_RECEIPT['type']}")
    info(f"算法: {SAMPLE_RECEIPT['algorithm']}")
    info(f"签发者: {SAMPLE_RECEIPT['issuer']}")
    info(f"签发时间: {SAMPLE_RECEIPT['issued_at']}")
    info(f"Key ID: {SAMPLE_RECEIPT['kid']}")
    info(f"签名: {SAMPLE_RECEIPT['signature'][:32]}...（共 128 hex chars）")
    print()
    dim("完整 receipt JSON:")
    for line in json.dumps(SAMPLE_RECEIPT, indent=2).split("\n"):
        dim(line, indent=6)

    # ── Part 2: 调用 CLI 验签 ──
    header("Part 2: 调用 @veritasacta/verify 验签")

    step(2, "执行验签")
    info(f"公钥 (Ed25519 hex): {SIGNING_PUBLIC_KEY[:32]}...")
    info("命令: npx @veritasacta/verify@0.2.4 <receipt.json> --key <hex> --json")
    print()

    verify_result = verify_receipt_with_cli(SAMPLE_RECEIPT, SIGNING_PUBLIC_KEY)

    if verify_result.get("valid"):
        ok(f"{GREEN}VALID{RESET} — 签名验证通过！")
        ok(f"Receipt hash: {verify_result.get('hash', 'N/A')}")
        ok(f"格式: {verify_result.get('format', 'N/A')}")
        ok(f"类型: {verify_result.get('type', 'N/A')}")
        ok(f"签发者: {verify_result.get('issuer', 'N/A')}")
        ok(f"Key ID: {verify_result.get('kid', 'N/A')}")
    else:
        fail(f"{RED}INVALID{RESET} — 签名验证失败！")
        fail(f"错误: {verify_result.get('error', 'unknown')}")
        if "hint" in verify_result:
            fail(f"提示: {verify_result['hint']}")
        print(f"\n{DIM}验证输出:{RESET}")
        dim(json.dumps(verify_result, indent=2))
        print(f"\n{RED}验签失败，后续步骤无法继续。{RESET}")
        sys.exit(1)

    print()
    dim("CLI 完整输出:")
    for line in json.dumps(verify_result, indent=2).split("\n"):
        dim(line, indent=6)

    # ── Part 3: 提取 Payload 字段 ──
    header("Part 3: 提取 Receipt Payload 字段")

    step(3, "从已验证的 receipt 中提取关键字段")
    fields = extract_payload_fields(SAMPLE_RECEIPT)

    for key, value in fields.items():
        info(f"{key}: {BOLD}{value}{RESET}")

    # ── Part 4: Trust Delta 计算 ──
    header("Part 4: Trust Delta 计算 — ASM 声明 vs 实际执行")

    step(4, "ASM Manifest 声明值")
    info(f"服务: {ASM_DECLARED['display_name']} ({ASM_DECLARED['service_id']})")
    info(f"声明延迟 p50: {ASM_DECLARED['declared_latency_seconds']}s")
    info(f"声明质量分: {ASM_DECLARED['declared_quality_score']}")
    info(f"声明可用性: {ASM_DECLARED['declared_uptime']}")
    info(f"声明单价: ${ASM_DECLARED['declared_cost_per_unit']}")

    step(5, "实际执行指标（模拟）")
    info(f"实际延迟: {ACTUAL_METRICS['actual_latency_seconds']}s")
    info(f"实际质量: {ACTUAL_METRICS['actual_quality_score']}")
    info(f"实际可用性: {ACTUAL_METRICS['actual_uptime']}")
    info(f"实际单价: ${ACTUAL_METRICS['actual_cost_per_unit']}")

    step(6, "Trust Delta = |declared - actual| / declared")
    deltas = compute_trust_deltas(ASM_DECLARED, ACTUAL_METRICS)

    print()
    # 表头
    print(f"    {'维度':<12s} {'声明值':>10s} {'实际值':>10s} {'Delta':>10s}  {'评估'}")
    print(f"    {'─' * 12} {'─' * 10} {'─' * 10} {'─' * 10}  {'─' * 15}")

    overall_delta = 0.0
    for dim_name, d in deltas.items():
        delta = d["delta"]
        overall_delta += delta

        # 颜色编码
        if delta < 0.05:
            color = GREEN
            label = "优秀 ✓"
        elif delta < 0.15:
            color = YELLOW
            label = "可接受"
        elif delta < 0.30:
            color = YELLOW
            label = "偏差较大 ⚠"
        else:
            color = RED
            label = "严重偏差 ✗"

        declared_str = f"{d['declared']:.4f}"
        actual_str = f"{d['actual']:.4f}"
        delta_str = f"{color}{delta:.4f}{RESET}"

        print(f"    {dim_name:<12s} {declared_str:>10s} {actual_str:>10s} {delta_str:>20s}  {label}")

    # 总体信任分
    mean_delta = overall_delta / len(deltas)
    trust_score = max(0.0, min(1.0, 1.0 - mean_delta))

    print()
    trust_color = GREEN if trust_score >= 0.85 else (YELLOW if trust_score >= 0.7 else RED)
    info(f"平均 Delta: {mean_delta:.4f}")
    info(f"Trust Score: {trust_color}{BOLD}{trust_score:.4f}{RESET}  (1.0 - mean_delta)")

    # ── Part 5: 总结 ──
    header("完整信任链总结")

    print(f"""
  {BOLD}本 demo 演示的完整信任链:{RESET}

  {CYAN}1. ASM Manifest 声明{RESET}
     服务在 manifest 中声明 SLA（延迟、质量、可用性、成本）

  {CYAN}2. 服务执行{RESET}
     Agent 调用服务，获得实际执行结果

  {CYAN}3. Signed Receipt（本 demo 的核心）{RESET}
     服务签发 ACTA 格式的签名 receipt
     使用 Ed25519 签名，不可伪造

  {CYAN}4. 验签（@veritasacta/verify）{RESET}
     Agent 离线验证 receipt 签名的真实性
     {GREEN}✓ VALID{RESET} = receipt 未被篡改，确实由声明的签发者签署

  {CYAN}5. Trust Delta 计算{RESET}
     |declared - actual| / declared
     量化服务的"言行一致"程度

  {CYAN}6. 未来选择{RESET}
     Trust score 作为额外维度参与 ASM scorer 排名
     诚实的服务获得信任加分，夸大的服务被降权

  {DIM}─────────────────────────────────────────────────────────────{RESET}
  {DIM}Receipt 签名算法: Ed25519 (ACTA v2 envelope){RESET}
  {DIM}验签工具: npx @veritasacta/verify@0.2.4{RESET}
  {DIM}Trust delta 函数: scorer.py → compute_trust_delta(){RESET}
""")


if __name__ == "__main__":
    main()
