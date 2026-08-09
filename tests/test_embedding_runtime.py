from __future__ import annotations

import asyncio

import numpy as np

import tools.embedding_runtime as embedding_runtime
from tools.embedding_runtime import EmbeddingRuntime, EmbeddingSettings, run_embedding_probe


def test_local_embedding_probe_needs_no_url_or_api_key(monkeypatch):
    class FakeTextEmbedding:
        def __init__(self, **kwargs):
            assert kwargs["model_name"] == "test-local"

        def query_embed(self, texts):
            return (
                np.asarray([index, 1.0, 0.5], dtype=np.float32)
                for index, _ in enumerate(texts)
            )

    import fastembed

    monkeypatch.setattr(fastembed, "TextEmbedding", FakeTextEmbedding)
    embedding_runtime._LOCAL_MODELS.clear()
    result = run_embedding_probe(
        EmbeddingSettings(
            provider="local",
            model="test-local",
            dimension=3,
            max_tokens=512,
        )
    )

    assert result["ok"] is True
    assert result["provider"] == "local"
    assert result["dimension"] == 3
    assert result["vectors"] == 2


def test_local_embedding_routes_query_and_document_context(monkeypatch):
    calls = []

    class FakeTextEmbedding:
        def __init__(self, **kwargs):
            assert kwargs["model_name"] == "test-asymmetric"

        def query_embed(self, texts):
            calls.append(("query", list(texts)))
            return [np.asarray([1.0, 0.0], dtype=np.float32)]

        def passage_embed(self, texts):
            calls.append(("document", list(texts)))
            return [np.asarray([0.0, 1.0], dtype=np.float32)]

    import fastembed

    monkeypatch.setattr(fastembed, "TextEmbedding", FakeTextEmbedding)
    embedding_runtime._LOCAL_MODELS.clear()
    runtime = EmbeddingRuntime(
        EmbeddingSettings(
            provider="local",
            model="test-asymmetric",
            dimension=2,
            max_tokens=512,
        )
    )

    query = runtime._embed_local(["寻找旧线索"], "query")
    document = runtime._embed_local(["很久以前埋下的线索"], "document")

    assert query.tolist() == [[1.0, 0.0]]
    assert document.tolist() == [[0.0, 1.0]]
    assert calls == [
        ("query", ["寻找旧线索"]),
        ("document", ["很久以前埋下的线索"]),
    ]


def test_embedding_cache_reuses_identical_batches(monkeypatch):
    calls = {"n": 0}
    runtime = EmbeddingRuntime(
        EmbeddingSettings(
            provider="local",
            model="test-cache",
            dimension=2,
            max_tokens=512,
        )
    )

    def fake_local(texts, context):
        calls["n"] += 1
        return np.asarray(
            [[float(index), 1.0] for index in range(len(texts))],
            dtype=np.float32,
        )

    monkeypatch.setattr(runtime, "_embed_local", fake_local)

    async def run():
        first = await runtime.embed(["同一段文本"], context="query")
        second = await runtime.embed(["同一段文本"], context="query")
        third = await runtime.embed(["同一段文本"], context="document")
        return first, second, third

    first, second, third = asyncio.run(run())

    assert calls["n"] == 2
    assert np.array_equal(first, second)
    stats = runtime.cache_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 2
