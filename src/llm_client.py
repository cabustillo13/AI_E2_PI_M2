import os
import time
from typing import Any, Dict, Tuple
from pydantic import BaseModel
import anthropic
from openai import OpenAI


class LLMProvider:
    """Cliente unificado para interactuar con LLMs garantizando salidas estructuradas."""
    
    def __init__(self, provider_name: str = "openai"):
        self.provider_name = provider_name
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Opcional: Solo si el usuario configuró Anthropic
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key) if anthropic_key else None

    def check_moderation(self, text: str) -> bool:
        """Guardrail de entrada: Detecta toxicidad (OpenAI) + Patrones de Prompt Injection."""
        # 1. Chequeo heurístico rápido de palabras clave de ataque (Prompt Injection / Jailbreak)
        attack_keywords = [
            "ignore previous", "system prompt", "developer message", 
            "jailbreak", "dan", "exfiltrate", "reveal your", "act as an administrator"
        ]
        text_lower = text.lower()
        if any(keyword in text_lower for keyword in attack_keywords):
            return True # Bloqueado por heurística de inyección

        # 2. Si pasa la heurística, consultamos la API de moderación tradicional
        if self.provider_name != "openai":
            return False # Anthropic modera internamente
        
        response = self.openai_client.moderations.create(input=text)
        return response.results[0].flagged

    def generate_structured(
        self, system_prompt: str, user_message: str, response_model: type[BaseModel], model: str = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Devuelve una tupla: (Datos_Parseados_Como_Dict, Metricas)"""
        start_time = time.time()

        if self.provider_name == "openai":
            model_name = model or "gpt-4o-mini"
            # Uso de Structured Outputs nativo de OpenAI (Nuevo estándar)
            response = self.openai_client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format=response_model,
                temperature=0.0, # Control de aleatoriedad para salidas consistentes
                max_tokens=4096  # Evita bucles infinitos y controla costos
            )
            
            latency = time.time() - start_time
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            
            # Cálculo de costos: (Tokens / 1M) * Tarifa por millón (GPT-4o-mini: $0.150 in / $0.600 out)
            cost = (tokens_in * 0.150 / 1_000_000) + (tokens_out * 0.600 / 1_000_000)
            
            # response.choices[0].message.parsed contiene el objeto Pydantic
            return response.choices[0].message.parsed.model_dump(), {
                "latency_sec": round(latency, 2), "input_tokens": tokens_in, "output_tokens": tokens_out, "cost_usd": cost
            }

        elif self.provider_name == "anthropic":
            if not self.anthropic_client:
                raise ValueError("Anthropic API Key no configurada.")
            model_name = model or "claude-3-haiku-20240307"
            
            # Anthropic requiere Tool Calling para estructurar salidas
            schema = response_model.model_json_schema()
            tool = {"name": "output_formatter", "description": "Formatea la salida.", "input_schema": schema}
            
            response = self.anthropic_client.messages.create(
                model=model_name,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                tools=[tool],
                tool_choice={"type": "tool", "name": "output_formatter"}
            )
            
            latency = time.time() - start_time
            tokens_in = response.usage.input_tokens
            tokens_out = response.usage.output_tokens
            
            # Cálculo de costos: (Tokens / 1M) * Tarifa por millón (Claude 3 Haiku: $0.25 in / $1.25 out)
            cost = (tokens_in * 0.25 / 1_000_000) + (tokens_out * 1.25 / 1_000_000)
            
            tool_use = next(block for block in response.content if block.type == "tool_use")
            return tool_use.input, {
                "latency_sec": round(latency, 2), "input_tokens": tokens_in, "output_tokens": tokens_out, "cost_usd": cost
            }