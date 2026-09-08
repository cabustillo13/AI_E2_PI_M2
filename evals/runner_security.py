import json
from pathlib import Path
from src.llm_client import LLMProvider

# Cargar variables de entorno desde .env
from dotenv import load_dotenv
load_dotenv()

# Definir Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = PROJECT_ROOT / "evals"


def main():
    print("Iniciando suite de pruebas de seguridad (Adversarial Evals)...")
    provider = LLMProvider(provider_name="openai") # Por defecto usará OpenAI (o el que hayas configurado)

    evals_adversarial_path = EVALS_DIR / "adversarial.jsonl"
    with open(evals_adversarial_path, "r", encoding="utf-8") as f:
        attacks = [json.loads(line) for line in f if line.strip()]
        
    blocked_count = 0
    total_attacks = len(attacks)
    
    for attack in attacks:
        query = attack["query"]
        attack_id = attack["id"]
        
        # Probamos el guardrail de entrada (moderación o heurística)
        is_blocked = provider.check_moderation(query)
        
        if is_blocked:
            blocked_count += 1
            print(f"[{attack_id}] Bloqueado correctamente.")
        else:
            print(f"[{attack_id}] ATENCIÓN: El prompt pasó el guardrail: '{query}'")
            
    print(f"\nResultado de seguridad: {blocked_count}/{total_attacks} ataques bloqueados.")


if __name__ == "__main__":
    main()