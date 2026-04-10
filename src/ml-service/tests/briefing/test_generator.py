from unittest.mock import MagicMock

from tests.briefing.conftest import _make_briefing_articles, _make_profile

from app.briefing.generator import BriefingGenerator


def test_generate_summary_calls_llm():
    mock_provider = MagicMock()
    mock_provider.generate.return_value = "Today's briefing highlights..."

    generator = BriefingGenerator(provider=mock_provider)
    articles = _make_briefing_articles(3)
    profile = _make_profile()

    result = generator.generate_summary(articles, profile)

    assert result == "Today's briefing highlights..."
    mock_provider.generate.assert_called_once()


def test_generate_summary_prompt_includes_profile():
    mock_provider = MagicMock()
    mock_provider.generate.return_value = "Summary"

    generator = BriefingGenerator(provider=mock_provider)
    articles = _make_briefing_articles(2)
    profile = _make_profile(name="Jane Analyst")

    generator.generate_summary(articles, profile)

    call_args = mock_provider.generate.call_args
    prompt = call_args.args[0]
    assert "Jane Analyst" in prompt
    assert "Environmental analyst" in prompt


def test_generate_summary_prompt_includes_articles():
    mock_provider = MagicMock()
    mock_provider.generate.return_value = "Summary"

    generator = BriefingGenerator(provider=mock_provider)
    articles = _make_briefing_articles(3)
    profile = _make_profile()

    generator.generate_summary(articles, profile)

    call_args = mock_provider.generate.call_args
    prompt = call_args.args[0]
    assert "Article 1" in prompt
    assert "Article 2" in prompt
    assert "Article 3" in prompt
    assert "3 total" in prompt


def test_generate_summary_empty_articles_returns_none():
    mock_provider = MagicMock()
    generator = BriefingGenerator(provider=mock_provider)
    profile = _make_profile()

    result = generator.generate_summary([], profile)

    assert result is None
    mock_provider.generate.assert_not_called()


def test_generate_summary_llm_failure_returns_none():
    mock_provider = MagicMock()
    mock_provider.generate.side_effect = Exception("LLM timeout")

    generator = BriefingGenerator(provider=mock_provider)
    articles = _make_briefing_articles(2)
    profile = _make_profile()

    result = generator.generate_summary(articles, profile)

    assert result is None


def test_generate_summary_caps_articles_in_prompt():
    """Prompt should include at most 15 articles even if more are provided."""
    mock_provider = MagicMock()
    mock_provider.generate.return_value = "Summary"

    generator = BriefingGenerator(provider=mock_provider)
    articles = _make_briefing_articles(20)
    profile = _make_profile()

    generator.generate_summary(articles, profile)

    call_args = mock_provider.generate.call_args
    prompt = call_args.args[0]
    assert "Article 15" in prompt
    assert "Article 16" not in prompt


def test_generate_summary_uses_system_prompt():
    mock_provider = MagicMock()
    mock_provider.generate.return_value = "Summary"

    generator = BriefingGenerator(provider=mock_provider)
    articles = _make_briefing_articles(1)
    profile = _make_profile()

    generator.generate_summary(articles, profile)

    call_args = mock_provider.generate.call_args
    system = call_args.kwargs.get("system") or call_args.args[1]
    assert "executive briefing" in system.lower()
