import os
import time
from typing import List, Dict, Any
from openai import OpenAI


class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY no configurada en las variables de entorno.")
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        response = self.client.embeddings.create(
            input=texts,
            model=self.embedding_model
        )
        return [data.embedding for data in response.data]

    def get_completion(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        start_time = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )
        latency = time.time() - start_time
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        
        # Costo aproximado para gpt-4o-mini ($0.15/1M input, $0.60/1M output)
        cost = (prompt_tokens * 0.00000015) + (completion_tokens * 0.00000060)

        return {
            "content": response.choices[0].message.content,
            "latency": latency,
            "cost": cost,
            "tokens": response.usage.total_tokens
        }