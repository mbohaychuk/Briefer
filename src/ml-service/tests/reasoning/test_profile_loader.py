from uuid import UUID

from conftest import make_normalized_article

from app.reasoning.models import (
    InterestBlock,
    ScoredArticle,
    ScoringResult,
    UserProfile,
)


def test_interest_block_defaults():
    block = InterestBlock(label="Test", text="Some interest")
    assert block.label == "Test"
    assert block.text == "Some interest"
    assert block.embedding == []


def test_user_profile_creation():
    profile = UserProfile(
        user_id=UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890"),
        name="Test User",
        interest_blocks=[
            InterestBlock(label="Role", text="I work in policy"),
        ],
    )
    assert profile.name == "Test User"
    assert len(profile.interest_blocks) == 1


def test_scored_article_defaults():
    article = make_normalized_article()
    scored = ScoredArticle(article=article)
    assert scored.vector_score is None
    assert scored.rerank_score is None
    assert scored.llm_score is None
    assert scored.route is None


def test_scoring_result_defaults():
    result = ScoringResult()
    assert result.candidates_retrieved == 0
    assert result.stored == 0


import json
from unittest.mock import MagicMock, patch


@patch("app.reasoning.profile_loader.SentenceTransformer")
def test_load_profiles_parses_json(mock_st_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.1] * 384]
    mock_st_cls.return_value = mock_model

    from app.reasoning.profile_loader import ProfileLoader

    profiles_data = {
        "profiles": [
            {
                "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "name": "Test User",
                "interests": [
                    {"label": "Role", "text": "I work in policy"},
                ],
            }
        ]
    }

    loader = ProfileLoader(model_name="test-model")
    profiles = loader.load_from_dict(profiles_data)
    assert len(profiles) == 1
    assert profiles[0].name == "Test User"
    assert len(profiles[0].interest_blocks) == 1
    assert profiles[0].interest_blocks[0].label == "Role"


@patch("app.reasoning.profile_loader.SentenceTransformer")
def test_load_profiles_embeds_interests(mock_st_cls):
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.1] * 384, [0.2] * 384]
    mock_st_cls.return_value = mock_model

    from app.reasoning.profile_loader import ProfileLoader

    profiles_data = {
        "profiles": [
            {
                "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "name": "Test User",
                "interests": [
                    {"label": "A", "text": "Interest A"},
                    {"label": "B", "text": "Interest B"},
                ],
            }
        ]
    }

    loader = ProfileLoader(model_name="test-model")
    profiles = loader.load_from_dict(profiles_data)
    assert len(profiles[0].interest_blocks[0].embedding) == 384
    assert len(profiles[0].interest_blocks[1].embedding) == 384
    mock_model.encode.assert_called_once()


@patch("app.reasoning.profile_loader.SentenceTransformer")
def test_load_profiles_from_file(mock_st_cls, tmp_path):
    mock_model = MagicMock()
    mock_model.encode.return_value = [[0.5] * 384]
    mock_st_cls.return_value = mock_model

    from app.reasoning.profile_loader import ProfileLoader

    profiles_data = {
        "profiles": [
            {
                "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "name": "File User",
                "interests": [
                    {"label": "Role", "text": "I analyze data"},
                ],
            }
        ]
    }
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(profiles_data))

    loader = ProfileLoader(model_name="test-model")
    profiles = loader.load_from_file(str(path))
    assert profiles[0].name == "File User"
