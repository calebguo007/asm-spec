#!/usr/bin/env python3
"""ASM v0.3 Manifest 生成器

从 OpenAPI spec 自动生成符合 ASM v0.3 schema 的 manifest 文件。
支持 JSON 和 YAML 格式的 OpenAPI spec 输入。

Usage:
    python asm_gen.py --input openapi.yaml --output service.asm.json
    python asm_gen.py --validate-only --input existing.asm.json
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None

try:
    import jsonschema
except ImportError:
    jsonschema = None

# ============================================================
# 常量与默认值
# ============================================================

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "schema", "asm-v0.3.schema.json"
)

DEFAULT_TTL = 3600
ASM_VERSION = "0.3"

# taxonomy 推断关键词映射表
TAXONOMY_KEYWORDS: Dict[str, List[str]] = {
    "ai.llm.chat": [
        "chat", "completion", "conversation", "language model", "llm",
        "gpt", "claude", "gemini", "text generation", "assistant",
    ],
    "ai.llm.embedding": [
        "embedding", "vector", "semantic search", "encode", "similarity",
    ],
    "ai.vision.image_generation": [
        "image generation", "text-to-image", "text to image", "image synthesis",
        "dall-e", "stable diffusion", "flux", "imagen", "midjourney",
    ],
    "ai.vision.image_editing": [
        "image editing", "inpainting", "outpainting", "image manipulation",
    ],
    "ai.vision.ocr": [
        "ocr", "text recognition", "optical character recognition",
    ],
    "ai.audio.tts": [
        "text-to-speech", "text to speech", "tts", "speech synthesis",
        "voice generation",
    ],
    "ai.audio.stt": [
        "speech-to-text", "speech to text", "stt", "transcription",
        "speech recognition", "whisper",
    ],
    "ai.audio.music": [
        "music generation", "music synthesis", "audio generation",
    ],
    "ai.video.generation": [
        "video generation", "text-to-video", "text to video",
        "video synthesis", "sora", "veo", "kling",
    ],
    "ai.code.generation": [
        "code generation", "code completion", "copilot", "codex",
    ],
    "ai.search.web": [
        "web search", "search engine", "internet search",
    ],
    "ai.compute.gpu": [
        "gpu", "compute", "serverless gpu", "inference", "training",
    ],
}

# endpoint 路径到 taxonomy 的映射
ENDPOINT_TAXONOMY_MAP: Dict[str, str] = {
    "/chat/completions": "ai.llm.chat",
    "/completions": "ai.llm.chat",
    "/embeddings": "ai.llm.embedding",
    "/images/generations": "ai.vision.image_generation",
    "/images/edits": "ai.vision.image_editing",
    "/audio/speech": "ai.audio.tts",
    "/audio/transcriptions": "ai.audio.stt",
    "/audio/translations": "ai.audio.stt",
    "/videos/generations": "ai.video.generation",
}


# ============================================================
# Tool函数
# ============================================================


def load_file(path: str) -> Dict[str, Any]:
    """Load JSON 或 YAML 文件。"""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 尝试 JSON
    if path.endswith(".json"):
        return json.loads(content)

    # 尝试 YAML
    if path.endswith((".yaml", ".yml")):
        if yaml is None:
            print("Error: 需要 pyyaml 库来解析 YAML 文件。请运行: pip install pyyaml", file=sys.stderr)
            sys.exit(1)
        return yaml.safe_load(content)

    # 未知扩展名 — 先尝试 JSON，再尝试 YAML
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        if yaml is not None:
            return yaml.safe_load(content)
        print("Error: 无法解析文件，请确保文件为 JSON 或 YAML 格式。", file=sys.stderr)
        sys.exit(1)


def load_schema() -> Optional[Dict[str, Any]]:
    """Load ASM v0.3 schema 文件。"""
    schema_path = os.path.normpath(SCHEMA_PATH)
    if not os.path.exists(schema_path):
        print(f"警告: 未找到 schema 文件 ({schema_path})，跳过校验。", file=sys.stderr)
        return None
    return load_file(schema_path)


def validate_manifest(manifest: Dict[str, Any], schema: Optional[Dict[str, Any]] = None) -> List[str]:
    """校验 manifest 是否符合 ASM v0.3 schema。返回错误列表（空列表表示通过）。"""
    if jsonschema is None:
        return ["jsonschema 库未安装，无法执行校验。请运行: pip install jsonschema"]

    if schema is None:
        schema = load_schema()
    if schema is None:
        return ["未找到 schema 文件，无法校验。"]

    errors = []
    validator = jsonschema.Draft202012Validator(schema)
    for error in sorted(validator.iter_errors(manifest), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"  [{path}] {error.message}")
    return errors


# ============================================================
# taxonomy 推断
# ============================================================


def infer_taxonomy_from_text(text: str) -> Optional[str]:
    """从文本描述中推断 taxonomy。"""
    text_lower = text.lower()
    best_match = None
    best_score = 0

    for taxonomy, keywords in TAXONOMY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > best_score:
            best_score = score
            best_match = taxonomy

    return best_match if best_score > 0 else None


def infer_taxonomy_from_endpoints(paths: Dict[str, Any]) -> Optional[str]:
    """从 OpenAPI paths 中推断 taxonomy。"""
    for endpoint_path in paths:
        # 精确匹配
        if endpoint_path in ENDPOINT_TAXONOMY_MAP:
            return ENDPOINT_TAXONOMY_MAP[endpoint_path]
        # 后缀匹配
        for pattern, taxonomy in ENDPOINT_TAXONOMY_MAP.items():
            if endpoint_path.endswith(pattern):
                return taxonomy
    return None


def infer_taxonomy(spec: Dict[str, Any]) -> str:
    """综合推断 taxonomy。优先级: endpoints > description > 默认值。"""
    # 1. 从 paths 推断
    paths = spec.get("paths", {})
    if paths:
        result = infer_taxonomy_from_endpoints(paths)
        if result:
            return result

    # 2. 从 info.description 推断
    description = spec.get("info", {}).get("description", "")
    title = spec.get("info", {}).get("title", "")
    combined_text = f"{title} {description}"

    # 也把 paths 的描述加进来
    for path_item in paths.values():
        if isinstance(path_item, dict):
            for method_info in path_item.values():
                if isinstance(method_info, dict):
                    combined_text += " " + method_info.get("summary", "")
                    combined_text += " " + method_info.get("description", "")

    result = infer_taxonomy_from_text(combined_text)
    if result:
        return result

    # 3. 默认值
    return "ai.llm.chat"


# ============================================================
# service_id 生成
# ============================================================


def slugify(text: str) -> str:
    """将文本转换为 URL 友好的 slug。"""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def generate_service_id(spec: Dict[str, Any]) -> str:
    """从 OpenAPI spec 生成 service_id。

    格式: <provider>/<service>@<version>
    """
    info = spec.get("info", {})
    title = info.get("title", "unknown-service")
    version = info.get("version", "1.0")

    # 尝试从 servers URL 提取 provider
    servers = spec.get("servers", [])
    provider = "unknown"
    if servers:
        url = servers[0].get("url", "")
        # 从 URL 中提取域名作为 provider
        match = re.search(r"https?://(?:api\.)?([^./]+)", url)
        if match:
            provider = match.group(1)

    # 也尝试从 info.contact 提取
    if provider == "unknown":
        contact = info.get("contact", {})
        if contact.get("name"):
            provider = slugify(contact["name"])

    service_slug = slugify(title)
    return f"{provider}/{service_slug}@{version}"


# ============================================================
# pricing 映射
# ============================================================


def extract_pricing(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 OpenAPI spec 的 x-pricing 扩展字段提取 pricing 信息。"""
    x_pricing = spec.get("x-pricing") or spec.get("info", {}).get("x-pricing")
    if not x_pricing:
        # 也在 paths 中查找
        for path_item in spec.get("paths", {}).values():
            if isinstance(path_item, dict):
                if "x-pricing" in path_item:
                    x_pricing = path_item["x-pricing"]
                    break
                for method_info in path_item.values():
                    if isinstance(method_info, dict) and "x-pricing" in method_info:
                        x_pricing = method_info["x-pricing"]
                        break
            if x_pricing:
                break

    if not x_pricing:
        return None

    # 如果已经是 ASM 格式
    if "billing_dimensions" in x_pricing:
        return x_pricing

    # 简单格式: {"per_1m_input_tokens": 3.0, "currency": "USD"}
    pricing: Dict[str, Any] = {}
    billing_dimensions = []
    currency = x_pricing.get("currency", "USD")

    dimension_map = {
        "per_token": ("token", "per_1"),
        "per_1k_tokens": ("token", "per_1K"),
        "per_1m_tokens": ("token", "per_1M"),
        "per_input_token": ("input_token", "per_1"),
        "per_1k_input_tokens": ("input_token", "per_1K"),
        "per_1m_input_tokens": ("input_token", "per_1M"),
        "per_output_token": ("output_token", "per_1"),
        "per_1k_output_tokens": ("output_token", "per_1K"),
        "per_1m_output_tokens": ("output_token", "per_1M"),
        "per_image": ("image", "per_1"),
        "per_request": ("request", "per_1"),
        "per_character": ("character", "per_1"),
        "per_1m_characters": ("character", "per_1M"),
        "per_second": ("second", "per_1"),
        "per_minute": ("minute", "per_1"),
    }

    for key, value in x_pricing.items():
        if key in dimension_map and isinstance(value, (int, float)):
            dim, unit = dimension_map[key]
            billing_dimensions.append({
                "dimension": dim,
                "unit": unit,
                "cost_per_unit": value,
                "currency": currency,
            })

    if billing_dimensions:
        pricing["billing_dimensions"] = billing_dimensions

    # 可选字段
    if "batch_discount" in x_pricing:
        pricing["batch_discount"] = x_pricing["batch_discount"]
    if "free_tier" in x_pricing:
        pricing["free_tier"] = x_pricing["free_tier"]
    if "estimated" in x_pricing:
        pricing["estimated"] = x_pricing["estimated"]

    return pricing if pricing else None


# ============================================================
# capabilities 推断
# ============================================================


def infer_capabilities(spec: Dict[str, Any], taxonomy: str) -> Dict[str, Any]:
    """从 OpenAPI spec 推断 capabilities。"""
    caps: Dict[str, Any] = {}

    # description
    description = spec.get("info", {}).get("description", "")
    if description:
        caps["description"] = description

    # 根据 taxonomy 推断 modalities
    taxonomy_modalities = {
        "ai.llm.chat": (["text"], ["text"]),
        "ai.llm.embedding": (["text"], ["structured_data"]),
        "ai.vision.image_generation": (["text"], ["image"]),
        "ai.vision.image_editing": (["image", "text"], ["image"]),
        "ai.vision.ocr": (["image"], ["text"]),
        "ai.audio.tts": (["text"], ["audio"]),
        "ai.audio.stt": (["audio"], ["text"]),
        "ai.audio.music": (["text"], ["audio"]),
        "ai.video.generation": (["text"], ["video"]),
        "ai.code.generation": (["text"], ["text"]),
    }

    if taxonomy in taxonomy_modalities:
        input_mod, output_mod = taxonomy_modalities[taxonomy]
        caps["input_modalities"] = input_mod
        caps["output_modalities"] = output_mod

    return caps


# ============================================================
# provider 提取
# ============================================================


def extract_provider(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 OpenAPI spec 提取 provider 信息。"""
    info = spec.get("info", {})
    contact = info.get("contact", {})
    servers = spec.get("servers", [])

    provider: Dict[str, Any] = {}

    # name: 优先用 contact.name，其次从 servers URL 推断
    if contact.get("name"):
        provider["name"] = contact["name"]
    elif servers:
        url = servers[0].get("url", "")
        match = re.search(r"https?://(?:api\.)?([^./]+)", url)
        if match:
            provider["name"] = match.group(1).capitalize()

    # url: 优先用 contact.url，其次用 servers[0].url 的域名
    if contact.get("url"):
        provider["url"] = contact["url"]
    elif servers:
        url = servers[0].get("url", "")
        match = re.search(r"(https?://[^/]+)", url)
        if match:
            provider["url"] = match.group(1)

    return provider if provider else None


# ============================================================
# 核心生成逻辑
# ============================================================


def generate_manifest(
    spec: Dict[str, Any],
    taxonomy_override: Optional[str] = None,
    service_id_override: Optional[str] = None,
) -> Dict[str, Any]:
    """从 OpenAPI spec 生成 ASM v0.3 manifest。"""
    info = spec.get("info", {})

    # taxonomy
    taxonomy = taxonomy_override or infer_taxonomy(spec)

    # service_id
    service_id = service_id_override or generate_service_id(spec)

    # 构建 manifest
    manifest: Dict[str, Any] = {
        "asm_version": ASM_VERSION,
        "service_id": service_id,
        "taxonomy": taxonomy,
    }

    # display_name
    title = info.get("title")
    if title:
        manifest["display_name"] = title

    # updated_at & ttl
    manifest["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["ttl"] = DEFAULT_TTL

    # provider
    provider = extract_provider(spec)
    if provider:
        manifest["provider"] = provider

    # capabilities
    capabilities = infer_capabilities(spec, taxonomy)
    if capabilities:
        manifest["capabilities"] = capabilities

    # pricing
    pricing = extract_pricing(spec)
    if pricing:
        manifest["pricing"] = pricing

    # payment — 从 OpenAPI securitySchemes 推断 auth_type
    security_schemes = spec.get("components", {}).get("securitySchemes", {})
    if security_schemes:
        payment: Dict[str, Any] = {}
        for _scheme_name, scheme_def in security_schemes.items():
            scheme_type = scheme_def.get("type", "")
            if scheme_type == "http" and scheme_def.get("scheme") == "bearer":
                payment["auth_type"] = "api_key"
            elif scheme_type == "apiKey":
                payment["auth_type"] = "api_key"
            elif scheme_type == "oauth2":
                payment["auth_type"] = "oauth2"
        if payment:
            payment.setdefault("methods", ["api_key_prepaid"])
            manifest["payment"] = payment

    return manifest


# ============================================================
# CLI
# ============================================================


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="asm-gen",
        description="ASM v0.3 Manifest 生成器 — 从 OpenAPI spec 自动生成 ASM manifest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  # 从 OpenAPI spec 生成 manifest
  python asm_gen.py --input openapi.yaml --output my-service.asm.json

  # 手动指定 taxonomy 和 service_id
  python asm_gen.py --input openapi.yaml --taxonomy ai.llm.chat --service-id myco/gpt@1.0

  # 仅校验已有 manifest
  python asm_gen.py --validate-only --input existing.asm.json

  # 生成并输出到 stdout
  python asm_gen.py --input openapi.yaml
""",
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="OpenAPI spec 文件路径（JSON 或 YAML），或 --validate-only 模式下的 .asm.json 文件路径",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出 .asm.json 文件路径（默认输出到 stdout）",
    )
    parser.add_argument(
        "--taxonomy", "-t",
        default=None,
        help="手动指定 taxonomy（如 ai.llm.chat, ai.vision.image_generation），不指定则自动推断",
    )
    parser.add_argument(
        "--service-id", "-s",
        default=None,
        help="手动指定 service_id（如 openai/gpt-4o@2024-11-20）",
    )
    parser.add_argument(
        "--validate-only", "-v",
        action="store_true",
        help="仅校验模式：校验已有 manifest 是否符合 ASM v0.3 schema",
    )

    return parser


def main() -> int:
    """CLI 入口。"""
    parser = build_parser()
    args = parser.parse_args()

    # --validate-only 模式
    if args.validate_only:
        return cmd_validate(args.input)

    # 生成模式
    return cmd_generate(args.input, args.output, args.taxonomy, args.service_id)


def cmd_validate(input_path: str) -> int:
    """校验已有 manifest 文件。"""
    try:
        manifest = load_file(input_path)
    except Exception as e:
        print(f"Error: 无法读取文件 {input_path}: {e}", file=sys.stderr)
        return 1

    schema = load_schema()
    errors = validate_manifest(manifest, schema)

    if errors:
        print(f"❌ 校验失败 — {input_path} 存在以下问题:")
        for err in errors:
            print(err)
        return 1
    else:
        print(f"✅ 校验通过 — {input_path} 符合 ASM v0.3 schema")
        return 0


def cmd_generate(
    input_path: str,
    output_path: Optional[str],
    taxonomy: Optional[str],
    service_id: Optional[str],
) -> int:
    """从 OpenAPI spec 生成 manifest。"""
    # Load OpenAPI spec
    try:
        spec = load_file(input_path)
    except Exception as e:
        print(f"Error: 无法读取 OpenAPI spec {input_path}: {e}", file=sys.stderr)
        return 1

    # 生成 manifest
    manifest = generate_manifest(spec, taxonomy, service_id)

    # 校验
    schema = load_schema()
    errors = validate_manifest(manifest, schema)
    if errors:
        print("⚠️  生成的 manifest 存在校验问题:", file=sys.stderr)
        for err in errors:
            print(err, file=sys.stderr)
        print("仍将输出生成结果，请手动修正以上问题。\n", file=sys.stderr)

    # 输出
    output_json = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"

    if output_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"✅ manifest 已生成: {output_path}")
        if not errors:
            print("✅ 已通过 ASM v0.3 schema 校验")
    else:
        sys.stdout.write(output_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
