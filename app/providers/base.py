
from abc import ABC, abstractmethod
from typing import Dict

class LLMProvider(ABC):
    @abstractmethod
    def infer(self, system: str, user: str) -> str:
        raise NotImplementedError
