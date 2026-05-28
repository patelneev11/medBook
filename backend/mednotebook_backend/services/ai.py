# Claude API calls — implement in Session 6


class AIService:
    def generate_answer(self, question: str, context_chunks: list[str]) -> dict:
        raise NotImplementedError


ai_service = AIService()
