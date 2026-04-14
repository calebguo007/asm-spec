# ASM v0.3 Manifest 生成器 (asm-gen)

从 OpenAPI spec 自动生成符合 [ASM v0.3 schema](../../schema/asm-v0.3.schema.json) 的 manifest 文件。

## 安装依赖

```bash
pip install jsonschema pyyaml
```

> 仅使用 `jsonschema`、`pyyaml` 和标准库 `argparse`，无需 click/typer。

## Usage

### 从 OpenAPI spec 生成 manifest

```bash
# 输出到文件
python asm_gen.py --input openapi.yaml --output my-service.asm.json

# 输出到 stdout
python asm_gen.py --input openapi.json

# 支持 JSON 和 YAML 格式的 OpenAPI spec
python asm_gen.py -i spec.yaml -o output.asm.json
```

### 手动指定 taxonomy 和 service_id

```bash
python asm_gen.py \
  --input openapi.yaml \
  --taxonomy ai.llm.chat \
  --service-id mycompany/my-llm@2.0 \
  --output my-llm.asm.json
```

### 仅校验已有 manifest

```bash
python asm_gen.py --validate-only --input existing.asm.json
```

## 参数说明

| 参数 | 简写 | 必填 | 说明 |
|------|------|------|------|
| `--input` | `-i` | ✅ | OpenAPI spec 文件路径（JSON/YAML），或校验模式下的 .asm.json 路径 |
| `--output` | `-o` | ❌ | 输出 .asm.json 路径，不指定则输出到 stdout |
| `--taxonomy` | `-t` | ❌ | 手动指定 taxonomy（如 `ai.llm.chat`），不指定则自动推断 |
| `--service-id` | `-s` | ❌ | 手动指定 service_id（如 `openai/gpt-4o@2024-11-20`） |
| `--validate-only` | `-v` | ❌ | 仅校验模式，不生成 manifest |

## 映射规则

| OpenAPI 字段 | ASM manifest 字段 | 说明 |
|---|---|---|
| `info.title` | `display_name` | Service显示名称 |
| `info.description` | `capabilities.description` | 同时用于推断 taxonomy |
| `info.version` | `service_id` 的版本部分 | 格式: `provider/service@version` |
| `servers[0].url` | `provider.url` / `service_id` 的 provider 部分 | 从域名提取 provider 名称 |
| `info.contact` | `provider.name` / `provider.url` | 优先使用 contact 信息 |
| `paths` | 推断 `taxonomy` | 通过 endpoint 路径模式匹配（如 `/chat/completions` → `ai.llm.chat`） |
| `x-pricing` | `pricing` | 支持根级、info 级和 path 级的 x-pricing 扩展 |
| `components.securitySchemes` | `payment.auth_type` | 推断认证方式 |

### x-pricing 扩展字段格式

在 OpenAPI spec 中添加 `x-pricing` 扩展字段：

```yaml
x-pricing:
  per_1m_input_tokens: 3.0
  per_1m_output_tokens: 15.0
  currency: USD
  batch_discount: 0.5
```

支持的 pricing 键：

- `per_token`, `per_1k_tokens`, `per_1m_tokens`
- `per_input_token`, `per_1k_input_tokens`, `per_1m_input_tokens`
- `per_output_token`, `per_1k_output_tokens`, `per_1m_output_tokens`
- `per_image`, `per_request`, `per_character`, `per_1m_characters`
- `per_second`, `per_minute`

### 自动推断的 taxonomy 列表

| taxonomy | 触发条件 |
|---|---|
| `ai.llm.chat` | endpoint 含 `/chat/completions`，或描述含 chat/llm/gpt 等关键词 |
| `ai.llm.embedding` | endpoint 含 `/embeddings`，或描述含 embedding/vector 等 |
| `ai.vision.image_generation` | endpoint 含 `/images/generations`，或描述含 text-to-image 等 |
| `ai.audio.tts` | endpoint 含 `/audio/speech`，或描述含 text-to-speech/tts 等 |
| `ai.audio.stt` | endpoint 含 `/audio/transcriptions`，或描述含 speech-to-text 等 |
| `ai.video.generation` | endpoint 含 `/videos/generations`，或描述含 video generation 等 |
| `ai.code.generation` | 描述含 code generation/copilot 等 |
| `ai.compute.gpu` | 描述含 gpu/compute 等 |

## 默认值

| 字段 | 默认值 |
|---|---|
| `asm_version` | `"0.3"` |
| `updated_at` | 当前 UTC 时间 |
| `ttl` | `3600` (1 小时) |

## 运行Test

```bash
python test_asm_gen.py -v
```

Test覆盖：
- taxonomy 推断（endpoint 匹配 + 文本推断）
- service_id 生成
- pricing 提取（根级/info 级/无 pricing）
- capabilities 推断
- 完整 manifest 生成 + schema 校验（LLM chat / 图像生成 / embedding / TTS）
- 对 `manifests/` 目录下所有现有 `.asm.json` 文件的校验
- `--validate-only` 模式
- 文件读写往返Test
