#!/usr/bin/env python3
"""ASM v0.3 Manifest 生成器 — 单元Test

使用 mock OpenAPI spec Test manifest 生成与校验功能。
"""

import json
import os
import sys
import tempfile
import unittest

# 确保可以导入 asm_gen
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from asm_gen import (
    generate_manifest,
    generate_service_id,
    infer_taxonomy,
    validate_manifest,
    load_schema,
    extract_pricing,
    infer_capabilities,
    load_file,
    cmd_validate,
)

# ============================================================
# Mock OpenAPI Specs
# ============================================================

# Mock 1: LLM Chat Service (类似 OpenAI)
MOCK_LLM_CHAT_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "AcmeAI Chat API",
        "description": "A powerful large language model API for chat completions and text generation",
        "version": "2.0",
        "contact": {
            "name": "AcmeAI",
            "url": "https://acmeai.example.com"
        }
    },
    "servers": [
        {"url": "https://api.acmeai.example.com/v2"}
    ],
    "paths": {
        "/chat/completions": {
            "post": {
                "summary": "Create chat completion",
                "description": "Generates a chat completion response given a conversation history",
                "operationId": "createChatCompletion",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "model": {"type": "string"},
                                    "messages": {"type": "array"},
                                    "temperature": {"type": "number"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "成功"}
                }
            }
        }
    },
    "components": {
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer"
            }
        }
    },
    "x-pricing": {
        "per_1m_input_tokens": 3.0,
        "per_1m_output_tokens": 15.0,
        "currency": "USD",
        "batch_discount": 0.5
    }
}

# Mock 2: 图像生成Service
MOCK_IMAGE_GEN_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "PixelForge Image Generator",
        "description": "State-of-the-art text-to-image generation API with photorealistic quality",
        "version": "1.5",
        "contact": {
            "name": "PixelForge Labs",
            "url": "https://pixelforge.example.com"
        }
    },
    "servers": [
        {"url": "https://api.pixelforge.example.com/v1"}
    ],
    "paths": {
        "/images/generations": {
            "post": {
                "summary": "Generate image from text prompt",
                "description": "Creates an image from a text-to-image prompt",
                "operationId": "generateImage",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "prompt": {"type": "string"},
                                    "size": {"type": "string"},
                                    "quality": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "成功"}
                }
            }
        }
    },
    "components": {
        "securitySchemes": {
            "apiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key"
            }
        }
    },
    "x-pricing": {
        "per_image": 0.04,
        "currency": "USD"
    }
}

# Mock 3: 无 endpoint 信息，仅通过描述推断（TTS Service）
MOCK_TTS_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "VoiceCraft TTS",
        "description": "Premium text-to-speech synthesis API with voice cloning capabilities",
        "version": "3.0"
    },
    "servers": [
        {"url": "https://api.voicecraft.example.com"}
    ],
    "paths": {
        "/v1/synthesize": {
            "post": {
                "summary": "Synthesize speech from text",
                "description": "Convert text to speech audio using advanced TTS models"
            }
        }
    }
}

# Mock 4: 带有 info 级别 x-pricing 的 embedding Service
MOCK_EMBEDDING_SPEC = {
    "openapi": "3.1.0",
    "info": {
        "title": "VectorDB Embedding API",
        "description": "High-dimensional text embedding model for semantic search and RAG",
        "version": "2.0",
        "x-pricing": {
            "per_1m_tokens": 0.10,
            "currency": "USD"
        }
    },
    "servers": [
        {"url": "https://api.vectordb.example.com/v2"}
    ],
    "paths": {
        "/embeddings": {
            "post": {
                "summary": "Create embeddings",
                "description": "Generate vector embeddings for input text"
            }
        }
    }
}


# ============================================================
# Test类
# ============================================================


class TestTaxonomyInference(unittest.TestCase):
    """Test taxonomy 推断逻辑。"""

    def test_infer_from_chat_endpoint(self):
        """通过 /chat/completions endpoint 推断为 ai.llm.chat"""
        result = infer_taxonomy(MOCK_LLM_CHAT_SPEC)
        self.assertEqual(result, "ai.llm.chat")

    def test_infer_from_image_endpoint(self):
        """通过 /images/generations endpoint 推断为 ai.vision.image_generation"""
        result = infer_taxonomy(MOCK_IMAGE_GEN_SPEC)
        self.assertEqual(result, "ai.vision.image_generation")

    def test_infer_from_description(self):
        """通过描述文本推断为 ai.audio.tts"""
        result = infer_taxonomy(MOCK_TTS_SPEC)
        self.assertEqual(result, "ai.audio.tts")

    def test_infer_from_embedding_endpoint(self):
        """通过 /embeddings endpoint 推断为 ai.llm.embedding"""
        result = infer_taxonomy(MOCK_EMBEDDING_SPEC)
        self.assertEqual(result, "ai.llm.embedding")


class TestServiceIdGeneration(unittest.TestCase):
    """Test service_id 生成逻辑。"""

    def test_service_id_from_llm_spec(self):
        """从 LLM spec 生成 service_id"""
        result = generate_service_id(MOCK_LLM_CHAT_SPEC)
        self.assertIn("acmeai", result.lower())
        self.assertIn("@2.0", result)

    def test_service_id_from_image_spec(self):
        """从 image gen spec 生成 service_id"""
        result = generate_service_id(MOCK_IMAGE_GEN_SPEC)
        self.assertIn("pixelforge", result.lower())
        self.assertIn("@1.5", result)


class TestPricingExtraction(unittest.TestCase):
    """Test pricing 提取逻辑。"""

    def test_extract_pricing_from_root(self):
        """从根级 x-pricing 提取 pricing"""
        pricing = extract_pricing(MOCK_LLM_CHAT_SPEC)
        self.assertIsNotNone(pricing)
        self.assertIn("billing_dimensions", pricing)
        self.assertEqual(len(pricing["billing_dimensions"]), 2)
        # 检查 input_token
        dims = {d["dimension"]: d for d in pricing["billing_dimensions"]}
        self.assertIn("input_token", dims)
        self.assertEqual(dims["input_token"]["cost_per_unit"], 3.0)
        self.assertEqual(dims["input_token"]["unit"], "per_1M")
        # 检查 batch_discount
        self.assertEqual(pricing["batch_discount"], 0.5)

    def test_extract_pricing_from_info(self):
        """从 info 级别 x-pricing 提取 pricing"""
        pricing = extract_pricing(MOCK_EMBEDDING_SPEC)
        self.assertIsNotNone(pricing)
        dims = pricing["billing_dimensions"]
        self.assertEqual(len(dims), 1)
        self.assertEqual(dims[0]["dimension"], "token")
        self.assertEqual(dims[0]["cost_per_unit"], 0.10)

    def test_no_pricing(self):
        """无 x-pricing 时返回 None"""
        pricing = extract_pricing(MOCK_TTS_SPEC)
        self.assertIsNone(pricing)

    def test_image_pricing(self):
        """图片按张计费"""
        pricing = extract_pricing(MOCK_IMAGE_GEN_SPEC)
        self.assertIsNotNone(pricing)
        dims = pricing["billing_dimensions"]
        self.assertEqual(dims[0]["dimension"], "image")
        self.assertEqual(dims[0]["unit"], "per_1")
        self.assertEqual(dims[0]["cost_per_unit"], 0.04)


class TestCapabilitiesInference(unittest.TestCase):
    """Test capabilities 推断逻辑。"""

    def test_llm_capabilities(self):
        """LLM chat 的 capabilities"""
        caps = infer_capabilities(MOCK_LLM_CHAT_SPEC, "ai.llm.chat")
        self.assertEqual(caps["input_modalities"], ["text"])
        self.assertEqual(caps["output_modalities"], ["text"])
        self.assertIn("description", caps)

    def test_image_gen_capabilities(self):
        """图像生成的 capabilities"""
        caps = infer_capabilities(MOCK_IMAGE_GEN_SPEC, "ai.vision.image_generation")
        self.assertEqual(caps["input_modalities"], ["text"])
        self.assertEqual(caps["output_modalities"], ["image"])


class TestManifestGeneration(unittest.TestCase):
    """Test完整的 manifest 生成流程。"""

    def test_generate_llm_manifest(self):
        """生成 LLM chat manifest 并校验"""
        manifest = generate_manifest(MOCK_LLM_CHAT_SPEC)

        # 基础字段
        self.assertEqual(manifest["asm_version"], "0.3")
        self.assertEqual(manifest["taxonomy"], "ai.llm.chat")
        self.assertEqual(manifest["display_name"], "AcmeAI Chat API")
        self.assertEqual(manifest["ttl"], 3600)
        self.assertIn("updated_at", manifest)
        self.assertIn("service_id", manifest)

        # provider
        self.assertIn("provider", manifest)
        self.assertEqual(manifest["provider"]["name"], "AcmeAI")

        # pricing
        self.assertIn("pricing", manifest)
        self.assertIn("billing_dimensions", manifest["pricing"])

        # payment
        self.assertIn("payment", manifest)
        self.assertEqual(manifest["payment"]["auth_type"], "api_key")

        # schema 校验
        schema = load_schema()
        if schema:
            errors = validate_manifest(manifest, schema)
            self.assertEqual(errors, [], f"Schema 校验失败:\n" + "\n".join(errors))

    def test_generate_image_manifest(self):
        """生成图像生成 manifest 并校验"""
        manifest = generate_manifest(MOCK_IMAGE_GEN_SPEC)

        self.assertEqual(manifest["asm_version"], "0.3")
        self.assertEqual(manifest["taxonomy"], "ai.vision.image_generation")
        self.assertEqual(manifest["display_name"], "PixelForge Image Generator")

        # capabilities
        self.assertIn("capabilities", manifest)
        self.assertEqual(manifest["capabilities"]["input_modalities"], ["text"])
        self.assertEqual(manifest["capabilities"]["output_modalities"], ["image"])

        # pricing
        self.assertIn("pricing", manifest)
        dims = manifest["pricing"]["billing_dimensions"]
        self.assertEqual(dims[0]["dimension"], "image")

        # schema 校验
        schema = load_schema()
        if schema:
            errors = validate_manifest(manifest, schema)
            self.assertEqual(errors, [], f"Schema 校验失败:\n" + "\n".join(errors))

    def test_generate_with_taxonomy_override(self):
        """手动指定 taxonomy"""
        manifest = generate_manifest(MOCK_TTS_SPEC, taxonomy_override="ai.audio.tts")
        self.assertEqual(manifest["taxonomy"], "ai.audio.tts")

        schema = load_schema()
        if schema:
            errors = validate_manifest(manifest, schema)
            self.assertEqual(errors, [], f"Schema 校验失败:\n" + "\n".join(errors))

    def test_generate_with_service_id_override(self):
        """手动指定 service_id"""
        manifest = generate_manifest(
            MOCK_LLM_CHAT_SPEC,
            service_id_override="acmeai/chat-pro@2.0"
        )
        self.assertEqual(manifest["service_id"], "acmeai/chat-pro@2.0")

    def test_generate_embedding_manifest(self):
        """生成 embedding manifest 并校验"""
        manifest = generate_manifest(MOCK_EMBEDDING_SPEC)

        self.assertEqual(manifest["taxonomy"], "ai.llm.embedding")
        self.assertIn("pricing", manifest)

        schema = load_schema()
        if schema:
            errors = validate_manifest(manifest, schema)
            self.assertEqual(errors, [], f"Schema 校验失败:\n" + "\n".join(errors))


class TestValidation(unittest.TestCase):
    """Test校验功能。"""

    def test_validate_existing_manifests(self):
        """校验 manifests/ 目录下的所有现有 .asm.json 文件"""
        manifests_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", "manifests"
        )
        if not os.path.isdir(manifests_dir):
            self.skipTest("manifests 目录不存在")

        schema = load_schema()
        if schema is None:
            self.skipTest("schema 文件不存在")

        for fname in os.listdir(manifests_dir):
            if fname.endswith(".asm.json"):
                fpath = os.path.join(manifests_dir, fname)
                manifest = load_file(fpath)
                errors = validate_manifest(manifest, schema)
                self.assertEqual(
                    errors, [],
                    f"{fname} 校验失败:\n" + "\n".join(errors)
                )

    def test_validate_invalid_manifest(self):
        """校验一个缺少必填字段的无效 manifest"""
        invalid = {"asm_version": "0.3"}  # 缺少 service_id 和 taxonomy
        schema = load_schema()
        if schema is None:
            self.skipTest("schema 文件不存在")

        errors = validate_manifest(invalid, schema)
        self.assertTrue(len(errors) > 0, "应该检测到校验错误")

    def test_validate_only_mode(self):
        """Test --validate-only 模式（通过临时文件）"""
        schema = load_schema()
        if schema is None:
            self.skipTest("schema 文件不存在")

        # 生成一个合法 manifest 并Write to temp file
        manifest = generate_manifest(MOCK_LLM_CHAT_SPEC)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".asm.json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(manifest, f)
            tmp_path = f.name

        try:
            result = cmd_validate(tmp_path)
            self.assertEqual(result, 0, "合法 manifest 校验应返回 0")
        finally:
            os.unlink(tmp_path)


class TestFileIO(unittest.TestCase):
    """Test文件读写功能。"""

    def test_generate_and_write_json(self):
        """生成 manifest 并写入 JSON 文件，再读回校验"""
        manifest = generate_manifest(MOCK_IMAGE_GEN_SPEC)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".asm.json", delete=False, encoding="utf-8"
        ) as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)
            tmp_path = f.name

        try:
            loaded = load_file(tmp_path)
            self.assertEqual(loaded["asm_version"], "0.3")
            self.assertEqual(loaded["taxonomy"], "ai.vision.image_generation")
            self.assertEqual(loaded["display_name"], "PixelForge Image Generator")
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
