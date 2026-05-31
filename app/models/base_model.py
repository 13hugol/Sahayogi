from __future__ import annotations

from abc import ABC, abstractmethod

from app.database import Database


class BaseModel(ABC):
    @staticmethod
    def db() -> Database:
        return Database()

    @classmethod
    @abstractmethod
    def from_row(cls, row: dict | None):
        raise NotImplementedError

