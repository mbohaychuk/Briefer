import json
import logging
from uuid import UUID

from sentence_transformers import SentenceTransformer

from app.reasoning.models import InterestBlock, UserProfile

logger = logging.getLogger(__name__)


class ProfileLoader:
    """Loads user profiles from config and embeds interest blocks."""

    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def load_from_file(self, path: str) -> list[UserProfile]:
        with open(path) as f:
            data = json.load(f)
        return self.load_from_dict(data)

    def load_from_dict(self, data: dict) -> list[UserProfile]:
        profiles = []
        for entry in data["profiles"]:
            blocks = [
                InterestBlock(label=i["label"], text=i["text"])
                for i in entry["interests"]
            ]

            # Batch-embed all interest texts for this profile
            texts = [b.text for b in blocks]
            embeddings = self.model.encode(texts)
            for block, embedding in zip(blocks, embeddings):
                block.embedding = (
                    embedding.tolist()
                    if hasattr(embedding, "tolist")
                    else list(embedding)
                )

            profile = UserProfile(
                user_id=UUID(entry["user_id"]),
                name=entry["name"],
                interest_blocks=blocks,
            )
            profiles.append(profile)
            logger.info(
                "Loaded profile '%s' with %d interest blocks",
                profile.name,
                len(blocks),
            )

        return profiles
