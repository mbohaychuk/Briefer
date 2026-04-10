from unittest.mock import MagicMock

from conftest import make_normalized_article, make_raw_article

from app.ingestion.pipeline import IngestionPipeline


def _build_pipeline(**overrides):
    """Build a pipeline with mocked components. Override any component via kwargs."""
    defaults = {
        "plugins": [MagicMock()],
        "extractor": MagicMock(),
        "normalizer_fn": MagicMock(),
        "dedup": MagicMock(),
        "repository": MagicMock(),
        "embedder": MagicMock(),
    }
    defaults.update(overrides)

    # Wire up sensible default behaviors
    if "plugins" not in overrides:
        defaults["plugins"][0].fetch.return_value = [make_raw_article()]
        defaults["plugins"][0].name = "MockPlugin"
    if "extractor" not in overrides:
        defaults["extractor"].extract.return_value = "Full article text " * 10
    if "normalizer_fn" not in overrides:
        defaults["normalizer_fn"].return_value = make_normalized_article()
    if "dedup" not in overrides:
        defaults["dedup"].filter_duplicates.side_effect = lambda x: x
    if "embedder" not in overrides:
        defaults["embedder"].embed_and_store.return_value = [
            make_normalized_article().id
        ]

    return IngestionPipeline(**defaults)


def test_pipeline_end_to_end():
    pipeline = _build_pipeline()
    result = pipeline.run()
    assert result.fetched == 1
    assert result.extracted == 1
    assert result.new == 1
    assert result.embedded == 1


def test_pipeline_skips_extraction_failures():
    extractor = MagicMock()
    extractor.extract.return_value = None

    pipeline = _build_pipeline(extractor=extractor)
    result = pipeline.run()

    assert result.fetched == 1
    assert result.extracted == 0
    assert result.new == 0


def test_pipeline_dedup_filters_duplicates():
    dedup = MagicMock()
    dedup.filter_duplicates.return_value = []  # All filtered out

    pipeline = _build_pipeline(dedup=dedup)
    result = pipeline.run()

    assert result.new == 0
    assert result.embedded == 0


def test_pipeline_handles_plugin_error():
    failing_plugin = MagicMock()
    failing_plugin.fetch.side_effect = Exception("Feed unavailable")
    failing_plugin.name = "FailPlugin"

    working_plugin = MagicMock()
    working_plugin.fetch.return_value = [make_raw_article()]
    working_plugin.name = "WorkPlugin"

    pipeline = _build_pipeline(plugins=[failing_plugin, working_plugin])
    result = pipeline.run()

    assert result.fetched == 1  # Only working plugin's articles


def test_pipeline_commits_after_success():
    repo = MagicMock()
    pipeline = _build_pipeline(repository=repo)
    pipeline.run()
    repo.commit.assert_called_once()


def test_pipeline_multiple_articles():
    plugin = MagicMock()
    plugin.fetch.return_value = [make_raw_article(), make_raw_article(), make_raw_article()]
    plugin.name = "MultiPlugin"

    normalized = [make_normalized_article() for _ in range(3)]
    normalizer = MagicMock(side_effect=normalized)

    dedup = MagicMock()
    dedup.filter_duplicates.side_effect = lambda x: x

    embedder = MagicMock()
    embedder.embed_and_store.return_value = [a.id for a in normalized]

    pipeline = _build_pipeline(
        plugins=[plugin],
        normalizer_fn=normalizer,
        dedup=dedup,
        embedder=embedder,
    )
    result = pipeline.run()

    assert result.fetched == 3
    assert result.extracted == 3
    assert result.new == 3
    assert result.embedded == 3


def test_get_pipeline_raises_when_not_initialized():
    """get_pipeline() should raise RuntimeError before init."""
    import pytest

    import app.ingestion.pipeline as pipeline_mod

    saved = pipeline_mod._pipeline_instance
    pipeline_mod._pipeline_instance = None
    try:
        with pytest.raises(RuntimeError, match="not initialized"):
            pipeline_mod.get_pipeline()
    finally:
        pipeline_mod._pipeline_instance = saved
