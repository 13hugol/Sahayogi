from __future__ import annotations

from app.database import Database


class BaseModel:
    @staticmethod
    def db() -> Database:
        return Database()

