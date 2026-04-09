from unittest.mock import MagicMock, patch


@patch("app.reasoning.providers.ollama.httpx")
def test_generate_returns_text(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Hello world"}
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    result = provider.generate("Say hello")
    assert result == "Hello world"
    mock_httpx.post.assert_called_once()


@patch("app.reasoning.providers.ollama.httpx")
def test_generate_with_system_prompt(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "System aware"}
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    provider.generate("Prompt", system="You are helpful")

    call_args = mock_httpx.post.call_args
    body = call_args[1]["json"]
    assert body["system"] == "You are helpful"


@patch("app.reasoning.providers.ollama.httpx")
def test_generate_json_parses_response(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "response": '{"score": 7, "explanation": "Relevant"}'
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    result = provider.generate_json("Score this")
    assert result["score"] == 7
    assert result["explanation"] == "Relevant"

    call_args = mock_httpx.post.call_args
    body = call_args[1]["json"]
    assert body["format"] == "json"


@patch("app.reasoning.providers.ollama.httpx")
def test_chat_returns_content_and_tool_calls(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "content": "I'll help with that",
            "tool_calls": [
                {
                    "function": {
                        "name": "search",
                        "arguments": {"query": "deer disease"},
                    }
                }
            ],
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    result = provider.chat(
        messages=[{"role": "user", "content": "Find deer diseases"}],
        tools=[{"type": "function", "function": {"name": "search"}}],
    )
    assert result["content"] == "I'll help with that"
    assert len(result["tool_calls"]) == 1


@patch("app.reasoning.providers.ollama.httpx")
def test_chat_without_tool_calls(mock_httpx):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "Just a response"}
    }
    mock_response.raise_for_status = MagicMock()
    mock_httpx.post.return_value = mock_response

    from app.reasoning.providers.ollama import OllamaProvider

    provider = OllamaProvider(
        base_url="http://localhost:11434", model="gemma4", timeout=30
    )
    result = provider.chat(
        messages=[{"role": "user", "content": "Hello"}],
    )
    assert result["content"] == "Just a response"
    assert result["tool_calls"] is None
