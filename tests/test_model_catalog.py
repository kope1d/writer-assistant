from __future__ import annotations

from tools.llm.model_catalog import (
    CURATED_MODEL_PRESETS,
    MAX_CONTEXT_TOKENS,
    MAX_OUTPUT_TOKENS,
    build_model_preset_catalog,
)


def test_curated_catalog_covers_common_model_families_with_unique_ids():
    catalog = build_model_preset_catalog({})

    assert len(catalog) >= 20
    assert len({preset["id"] for preset in catalog}) == len(catalog)
    assert {preset["family"] for preset in catalog} >= {
        "OpenAI · GPT-5.6",
        "Anthropic · Claude",
        "Google · Gemini",
        "DeepSeek · V4",
        "国内前沿",
        "国际前沿",
        "本地模型",
    }
    assert {preset["id"] for preset in catalog} >= {
        "openai-gpt-5.6-sol",
        "openai-gpt-5.6-terra",
        "openai-gpt-5.6-luna",
        "anthropic-claude-fable-5",
        "anthropic-claude-opus-5",
        "anthropic-claude-sonnet-5",
        "anthropic-claude-haiku-4.5",
        "google-gemini-3.1-pro-preview",
        "google-gemini-3.6-flash",
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "dashscope-qwen3.8-max",
        "moonshot-kimi-k3",
        "zhipu-glm-5.2",
        "volcengine-doubao-seed-2.1-pro",
        "minimax-m3",
        "xiaomi-mimo-v2.5",
        "xiaomi-mimo-v2.5-pro",
        "xiaomi-mimo-v2.5-pro-ultraspeed",
        "xai-grok-4.5",
        "local-ollama",
        "local-lmstudio",
    }
    assert all(preset["metadata_source"] == "official" for preset in catalog)


def test_local_presets_point_at_localhost_openai_compatible_servers():
    catalog = {preset["id"]: preset for preset in build_model_preset_catalog({})}

    ollama = catalog["local-ollama"]
    lmstudio = catalog["local-lmstudio"]

    assert ollama["base_url"] == "http://localhost:11434/v1"
    assert lmstudio["base_url"] == "http://localhost:1234/v1"
    assert ollama["provider"] == "openai"
    assert lmstudio["provider"] == "openai"
    assert ollama["api_format"] == "chat"
    assert lmstudio["api_format"] == "chat"
    assert ollama["family"] == "本地模型"
    assert lmstudio["family"] == "本地模型"
    assert ollama["model"] == "qwen2.5:7b"
    assert lmstudio["model"] == "local-model"
    assert ollama["output_limit_known"] is False
    assert lmstudio["output_limit_known"] is False


def test_catalog_reports_litellm_conflicts_without_overriding_official_limits():
    openai_spec = next(
        preset
        for preset in CURATED_MODEL_PRESETS
        if preset.preset_id == "openai-gpt-5.6-sol"
    )
    catalog = build_model_preset_catalog(
        {
            openai_spec.litellm_model: {
                "max_input_tokens": 987_654,
                "max_output_tokens": 999_999,
            }
        }
    )
    openai = next(
        preset for preset in catalog if preset["id"] == openai_spec.preset_id
    )
    anthropic = next(
        preset
        for preset in catalog
        if preset["id"] == "anthropic-claude-sonnet-5"
    )

    assert openai["context_tokens"] == 1_050_000
    assert openai["max_tokens"] == 128_000
    assert openai["metadata_source"] == "official+litellm"
    assert openai["metadata_status"] == "conflict"
    assert openai["litellm_context_tokens"] == 987_654
    assert openai["litellm_max_tokens"] == 999_999
    assert openai["metadata_model"] == openai_spec.litellm_model
    assert anthropic["metadata_source"] == "official"


def test_catalog_exposes_current_frontier_context_and_output_capacities():
    catalog = {preset["id"]: preset for preset in build_model_preset_catalog({})}

    assert MAX_CONTEXT_TOKENS == 10_000_000
    assert MAX_OUTPUT_TOKENS == 384_000
    assert catalog["deepseek-v4-flash"]["context_tokens"] == 1_000_000
    assert catalog["deepseek-v4-flash"]["max_tokens"] == 384_000
    assert catalog["volcengine-doubao-seed-2.1-pro"]["max_tokens"] == 262_144


def test_catalog_contains_no_credential_fields():
    catalog = build_model_preset_catalog({})

    assert not {
        key
        for preset in catalog
        for key in preset
        if "key" in key.lower() or "credential" in key.lower()
    }
