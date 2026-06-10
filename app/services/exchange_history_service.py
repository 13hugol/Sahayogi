from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.repositories import ExchangeHistoryRepository


@dataclass(frozen=True)
class ExchangeHistoryQuery:
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    start_date_value: str = ""
    end_date_value: str = ""


class ExchangeHistoryService:
    VALID_STATUSES = ("pending", "active", "completed", "declined")

    def __init__(self, repository: ExchangeHistoryRepository):
        self._repository = repository

    def build_query(
        self,
        *,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> ExchangeHistoryQuery:
        normalized_status = self._normalize_status(status)
        start = self._parse_date(start_date)
        end = self._parse_date(end_date)
        if start and end and start > end:
            start, end = end, start
        return ExchangeHistoryQuery(
            status=normalized_status,
            start_date=start,
            end_date=end,
            start_date_value=start.isoformat() if start else "",
            end_date_value=end.isoformat() if end else "",
        )

    def list_for_user(
        self,
        user_id: int,
        *,
        query: ExchangeHistoryQuery | None = None,
        limit: int | None = None,
    ):
        active_query = query or ExchangeHistoryQuery()
        return self._repository.list_for_user(
            user_id,
            status=active_query.status,
            start_date=active_query.start_date,
            end_date=active_query.end_date,
            limit=limit,
        )

    def count_for_user(self, user_id: int) -> int:
        return self._repository.count_for_user(user_id)

    def find_for_user(self, user_id: int, exchange_id: int):
        return self._repository.find_for_user(user_id, exchange_id)

    def status_options(self) -> tuple[str, ...]:
        return self.VALID_STATUSES

    def _normalize_status(self, status: str | None) -> str | None:
        normalized = (status or "").strip().lower()
        if normalized in self.VALID_STATUSES:
            return normalized
        return None

    @staticmethod
    def _parse_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return None
