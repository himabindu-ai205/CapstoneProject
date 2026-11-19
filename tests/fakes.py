class ScriptedModel:
    def __init__(self):
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        if "http" in prompt:
            url = [part for part in prompt.split() if part.startswith("http")][0]
            return f"GROUNDED::{url}::DP charges apply per sell transaction."
        return "NOT_COVERED"
