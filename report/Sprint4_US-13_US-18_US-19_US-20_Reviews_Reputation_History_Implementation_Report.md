# Sprint 4 Gap Closure — US-13, US-18, US-19, US-20 Implementation Report

Date: 2026-06-12
Scope: completes the remaining Sprint 4 stories (Trust, history, credits) found unfinished during the Sprint 1–4 verification pass.

## Stories Covered

| Story | Title | Status before | Status after |
| --- | --- | --- | --- |
| US-18 / F2-2.4 | Leave Review | Frontend stub (fake data, no POST) | Implemented |
| US-19 / F2-2.5 | Reputation Score | Columns existed but never updated | Implemented |
| US-20 / F2-2.6 | Review History | Page existed, no pagination | Implemented |
| US-13 / F4-4.3 | History Dashboard | List only; filters not wired | Implemented |

## What Changed

### Exchange completion (prerequisite for US-18)

- `exchanges` table gained `learner_completed_at` and `teacher_completed_at` (created and migrated in `app/database.py`).
- `POST /exchanges/<id>/complete` now records a per-party confirmation. The exchange only flips to `completed` — and credits only transfer — after **both** parties confirm, matching the US-18 acceptance criterion that reviews unlock after both parties mark the exchange complete. The first confirmation notifies the other party to confirm.
- On finalisation, `profiles.completed_exchange_count` is incremented for both participants (US-04 profile stat).
- `Exchange.completion_marks` reports each party's confirmation; `Exchange.conversation` resolves the message thread between the two participants.

### US-18 Leave Review

- `profile_reviews` gained an `exchange_id` column with a unique key on `(exchange_id, reviewer_id)` — one review per completed exchange per reviewer, enforced in both the controller and the database.
- `GET/POST /reviews/exchange/<id>` is now a real handler: participant-only (403 otherwise), blocked until the exchange is `completed`, validates a 1–5 star rating and an optional comment up to 500 characters, publishes immediately, and notifies the reviewee (`new_review` notification).
- Exchange detail page shows the real reviews for that exchange, and the review button only appears for participants who have not reviewed yet.
- Admin review moderation (`/admin/reviews`) now lists real reviews and supports `POST /admin/reviews/<id>/reject`, which deletes the review, recalculates the recipient's reputation, and writes an admin audit log entry.

### US-19 Reputation Score

- Creating (or admin-deleting) a review recalculates `profiles.reputation_score` as `ROUND(AVG(rating), 1)` and `profiles.review_count` inside the same transaction.
- Profiles, listing cards, listing detail, and match cards display **New Member** instead of a numeric score when the user has fewer than 3 reviews. The top-rated page already required 3+ reviews.

### US-20 Review History

- `/reviews/users/<id>` is paginated at 10 reviews per page with Previous/Next and numbered page controls, newest first, and shows the total review count. The profile page keeps its "View all reviews" link.

### US-13 History Dashboard

- `/exchanges/` now applies the status filter (active / completed / cancelled) and adds from/to date filters (validated `YYYY-MM-DD`, applied in SQL).
- Each entry shows created/completed timestamps and links to the exchange record, the original listing, and the message thread, plus a **Leave a review** button on completed exchanges the current user has not reviewed yet.

### Security fixes found during verification

CSRF hidden inputs were missing from several POST forms (the app rejects POSTs without a valid token outside tests). Added to: request accept/decline/cancel, exchange mark-complete, notification mark-all-read, my-listings delete, account-delete, admin report resolve/dismiss, admin certificate approve/reject, and admin review reject. The decline form also gained the optional decline-reason input that the backend already supported (US-12 acceptance criterion).

## Testing

New automated tests in `tests/test_us18_us19_us20_reviews.py` (8 tests):

- Review blocked until both parties confirm completion.
- Review submission publishes, links to the exchange, updates reputation, and notifies the reviewee.
- One review per completed exchange.
- Rating range and 500-character comment validation.
- Reputation average rounding and the New Member display rule (< 3 reviews).
- Review history pagination (12 reviews → 10 + 2 across two pages).
- History dashboard status/date filters and review-button behaviour.
- `completed_exchange_count` increments for both participants.

Updated tests:

- `tests/test_us21_credit_ledger.py` — completion test now exercises the two-step confirmation before the credit transfer asserts.
- `tests/test_profile.py` — guest profile test seeds reviews whose recalculated average is 4.8 instead of writing the score directly.

Full suite: **105 passed**.
