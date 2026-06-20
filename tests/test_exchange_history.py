from __future__ import annotations

from datetime import datetime

from app.models import ExchangeHistoryItem
from app.services import ExchangeHistoryService


def test_exchange_history_filters_status_and_date_range():
    repository = FakeExchangeHistoryRepository(EXCHANGE_ITEMS)
    service = ExchangeHistoryService(repository)

    query = service.build_query(status="completed", start_date="2026-06-02", end_date="2026-06-08")
    results = service.list_for_user(1, query=query)

    assert len(results) == 1
    assert results[0].status == "completed"
    assert results[0].listing_title == "Python web basics"
    assert repository.last_filters["status"] == "completed"
    assert repository.last_filters["start_date"].isoformat() == "2026-06-02"
    assert repository.last_filters["end_date"].isoformat() == "2026-06-08"


def test_completed_exchange_requires_review_when_missing():
    service = ExchangeHistoryService(FakeExchangeHistoryRepository(EXCHANGE_ITEMS))

    results = service.list_for_user(1, query=service.build_query(status="completed"))

    assert results[0].can_review is True
    assert results[0].conversation.id == 42
    assert results[0].listing.id == 7


def test_completed_exchange_hides_review_action_after_submission():
    service = ExchangeHistoryService(FakeExchangeHistoryRepository(EXCHANGE_ITEMS))

    history_item = service.find_for_user(1, 4)

    assert history_item.status == "completed"
    assert history_item.review_submitted is True
    assert history_item.can_review is False


def test_exchange_history_is_user_scoped_and_counts_user_items_only():
    repository = FakeExchangeHistoryRepository(EXCHANGE_ITEMS)
    service = ExchangeHistoryService(repository)

    results = service.list_for_user(2)

    assert len(results) == 1
    assert results[0].partner_name == "Other Member"
    assert service.count_for_user(2) == 1


def test_invalid_status_and_reversed_dates_are_normalized():
    service = ExchangeHistoryService(FakeExchangeHistoryRepository(EXCHANGE_ITEMS))

    query = service.build_query(status="cancelled", start_date="2026-06-09", end_date="2026-06-01")

    assert query.status is None
    assert query.start_date.isoformat() == "2026-06-01"
    assert query.end_date.isoformat() == "2026-06-09"


def test_dashboard_summary_limit_is_forwarded_to_repository():
    repository = FakeExchangeHistoryRepository(EXCHANGE_ITEMS)
    service = ExchangeHistoryService(repository)

    results = service.list_for_user(1, limit=1)

    assert len(results) == 1
    assert repository.last_filters["limit"] == 1


EXCHANGE_ITEMS = [
    ExchangeHistoryItem(
        id=1,
        user_id=1,
        listing_id=7,
        listing_title="Python web basics",
        exchange_type="credit",
        partner_name="Sanjay Thapa",
        user_role="learner",
        status="completed",
        conversation_id=42,
        review_submitted=False,
        created_at=datetime(2026, 6, 5, 10, 0, 0),
        completed_at=datetime(2026, 6, 6, 11, 30, 0),
    ),
    ExchangeHistoryItem(
        id=2,
        user_id=1,
        listing_id=8,
        listing_title="Guitar lessons",
        exchange_type="teach",
        partner_name="Mina Rai",
        user_role="teacher",
        status="active",
        conversation_id=43,
        review_submitted=False,
        created_at=datetime(2026, 6, 9, 9, 0, 0),
    ),
    ExchangeHistoryItem(
        id=4,
        user_id=1,
        listing_id=10,
        listing_title="Nepali conversation practice",
        exchange_type="credit",
        partner_name="Asha Gurung",
        user_role="learner",
        status="completed",
        conversation_id=44,
        review_submitted=True,
        created_at=datetime(2026, 6, 1, 14, 0, 0),
        completed_at=datetime(2026, 6, 2, 15, 30, 0),
    ),
    ExchangeHistoryItem(
        id=3,
        user_id=2,
        listing_id=9,
        listing_title="Kitchen basics",
        exchange_type="credit",
        partner_name="Other Member",
        user_role="learner",
        status="pending",
        conversation_id=None,
        review_submitted=False,
        created_at=datetime(2026, 6, 3, 8, 0, 0),
    ),
]


class FakeExchangeHistoryRepository:
    def __init__(self, items):
        self.items = items
        self.last_filters = {}

    def list_for_user(self, user_id, *, status=None, start_date=None, end_date=None, limit=None):
        self.last_filters = {
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        }
        rows = [item for item in self.items if item.user_id == user_id]
        if status:
            rows = [item for item in rows if item.status == status]
        if start_date:
            rows = [item for item in rows if item.created_at.date() >= start_date]
        if end_date:
            rows = [item for item in rows if item.created_at.date() <= end_date]
        if limit:
            rows = rows[:limit]
        return rows

    def count_for_user(self, user_id):
        return len([item for item in self.items if item.user_id == user_id])

    def find_for_user(self, user_id, exchange_id):
        return next((item for item in self.items if item.user_id == user_id and item.id == exchange_id), None)
