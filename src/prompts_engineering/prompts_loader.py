# src/config/prompt_loader.py
import yaml
from pathlib import Path

class PromptLoader:
    def __init__(self, path: str = "config/prompts_templates.yaml"):
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"Prompt template file not found: {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            self.prompts = yaml.safe_load(f)

    def get(self, key: str) -> str:
        if key not in self.prompts:
            raise KeyError(f"Prompt '{key}' not found in template file.")
        return self.prompts[key]


prompt_loader = PromptLoader()
