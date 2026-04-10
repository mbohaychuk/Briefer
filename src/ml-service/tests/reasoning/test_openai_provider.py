from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.reasoning.providers.openai import OpenAiProvider


def _mock_completion(content, tool_calls=None):
    """Build a fake ChatCompletion response."""
    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
    )
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@patch("app.reasoning.providers.openai.OpenAI")
def test_generate_returns_text(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_completion(
        "Hello, world!"
    )

    provider = OpenAiProvider(api_key="test-key")
    result = provider.generate("Say hello")

    assert result == "Hello, world!"
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs.kwargs["messages"]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"


@patch("app.reasoning.providers.openai.OpenAI")
def test_generate_with_system_prompt(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_completion("Ok")

    provider = OpenAiProvider(api_key="test-key")
    provider.generate("Do something", system="You are helpful")

    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs.kwargs["messages"]
    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": "You are helpful"}
    assert messages[1] == {"role": "user", "content": "Do something"}


@patch("app.reasoning.providers.openai.OpenAI")
def test_generate_json_parses_response(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_completion(
        '{"score": 8, "explanation": "Highly relevant"}'
    )

    provider = OpenAiProvider(api_key="test-key")
    result = provider.generate_json("Score this article")

    assert result == {"score": 8, "explanation": "Highly relevant"}
    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs["response_format"] == {"type": "json_object"}


@patch("app.reasoning.providers.openai.OpenAI")
def test_chat_returns_content(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_completion(
        "I can help with that"
    )

    provider = OpenAiProvider(api_key="test-key")
    result = provider.chat([{"role": "user", "content": "Help me"}])

    assert result["content"] == "I can help with that"
    assert result["tool_calls"] is None


@patch("app.reasoning.providers.openai.OpenAI")
def test_chat_with_tool_calls(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client

    tool_call = SimpleNamespace(
        id="call_123",
        function=SimpleNamespace(
            name="get_weather",
            arguments='{"city": "Edmonton"}',
        ),
    )
    mock_client.chat.completions.create.return_value = _mock_completion(
        "", tool_calls=[tool_call]
    )

    provider = OpenAiProvider(api_key="test-key")
    result = provider.chat(
        [{"role": "user", "content": "What's the weather?"}],
        tools=[{"type": "function", "function": {"name": "get_weather"}}],
    )

    assert result["tool_calls"] is not None
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["function"]["name"] == "get_weather"
    assert result["tool_calls"][0]["id"] == "call_123"


@patch("app.reasoning.providers.openai.OpenAI")
def test_chat_with_system_prompt(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_completion("Done")

    provider = OpenAiProvider(api_key="test-key")
    provider.chat(
        [{"role": "user", "content": "Hi"}],
        system="You are a news assistant",
    )

    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs.kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "You are a news assistant"}
    assert messages[1] == {"role": "user", "content": "Hi"}


@patch("app.reasoning.providers.openai.OpenAI")
def test_provider_uses_configured_model(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_completion("Ok")

    provider = OpenAiProvider(api_key="test-key", model="gpt-4o")
    provider.generate("Test")

    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs["model"] == "gpt-4o"


@patch("app.reasoning.providers.openai.OpenAI")
def test_generate_handles_none_content(mock_openai_cls):
    """generate() should handle None content from the API response."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.return_value = _mock_completion(None)

    provider = OpenAiProvider(api_key="test-key")
    result = provider.generate("Say hello")

    # When content is None, generate returns None (no special handling)
    assert result is None
