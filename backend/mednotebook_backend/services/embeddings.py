# Embedding generation — implement in Session 5


class EmbeddingService:
    def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


embedding_service = EmbeddingService()
