from __future__ import annotations

from collections.abc import Callable

from app.database import Database


class BaseRepository:
    def __init__(self, db_factory: Callable[[], Database] | None = None):
        self._db_factory = db_factory or Database

    def _db(self) -> Database:
        return self._db_factory()

