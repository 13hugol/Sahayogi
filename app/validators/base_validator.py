from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping


class BaseValidator(ABC):
    @abstractmethod
    def validate(self, data):
        raise NotImplementedError

    @staticmethod
    def _text(form: Mapping[str, object], key: str) -> str:
        return str(form.get(key, "")).strip()

