# Implementation Plan: Batch 4 — Historical Interaction Reconciliation and Identity Linking

## Overview
Batch 4 bridges the Flick interaction history, guest identity lifecycle, and continuous taste intelligence. It establishes:
1. **Schema Foundations**: `UserIdentityLink` (strict $1:1$ guest-to-canonical cardinality) and `InteractionLog.processing_status` (`pending` / `processed` state machine, eliminating flawed sequence watermarks).
2. **Historical Swipe Reconciliation**: Idempotent reconciliation of the 499 unmatched pre-Session-80 swipes into `InteractionLog`, preserving original timestamps and weights.
3. **Live Interaction Parity**: Ensuring `SwipeUndoView` emits `undo` events into `InteractionLog`.
4. **Durable Taste Engine**: Aggregating actor events across canonical and linked identities (`actor_ids = [U.id] + list(linked_actor_ids)`), updating `UserTasteProfile.learned_weights`, and atomically transitioning `processing_status`.
5. **Tombstone Anonymization**: Privacy-preserving account deletion workflow reassigning logs to a tombstone actor and scrubbing PII while preserving global analytical weights.

---

## Architecture & Data Decisions
- **Disproved Watermarks**: Monotonic sequences or timestamp watermarks fail in concurrent relational databases due to out-of-order commits. We strictly use `processing_status = 'pending' | 'processed'` on `InteractionLog` with row locking (`select_for_update`).
- **Strict Identity Cardinality**: `UserIdentityLink.linked_actor_id` has `unique=True` (an actor ID belongs to at most one canonical user).
- **Non-Destructive Identity Linking**: Swipes and interaction logs retain their historical `user_id` (the guest's actor ID). Canonical users query events via `user_id__in=actor_ids`.
- **Tombstone Pattern**: `InteractionLog.user` has `null=False, on_delete=CASCADE`. Deleting a user without reassignment deletes analytical logs. We reassign logs to `system_deleted_actor` (`is_active=False`) and scrub metadata before deleting user rows.
- **Idempotent Reconciliation**: Reconciling historical swipes matches on `(user_id, session_id, movie_id, mapped_event_type)` to guarantee exactly 499 missing records are ingested and subsequent passes create 0 records.

---

## Work Breakdown & Dependencies

```
Task 1: Schema & Migrations (UserIdentityLink + InteractionLog.processing_status)
    │
    ├── Task 2: Live Interaction Parity (SwipeUndoView event emission)
    │
    ├── Task 3: Historical Swipe Reconciliation Service & Management Command
    │
    ├── Task 4: Identity Linking Service (Guest Conversion & Claiming)
    │       │
    │       └── Task 5: Durable Taste Engine Worker & Processor
    │               │
    │               └── Task 6: Privacy-Preserving Tombstone Anonymization Workflow
    │                       │
    │                       └── Task 7: Full Test Suite & PostgreSQL Concurrency Verification
```

---

## Detailed Tasks

### Task 1: Schema & Migrations
- **Description**: Add `UserIdentityLink` model to `backend/core/models.py` with `unique=True` on `linked_actor_id`. Add `processing_status` (`pending`, `processed`) and `processed_at` to `InteractionLog`. Create migration `0039_user_identity_link_and_interaction_processing_status.py`.
- **Files**: `backend/core/models.py`, `backend/core/migrations/0039_user_identity_link_and_interaction_processing_status.py`
- **Verification**: `python manage.py migrate core`, inspect schema in SQLite and PostgreSQL.

### Task 2: Live Interaction Parity (SwipeUndoView)
- **Description**: In `backend/core/views.py` (`SwipeUndoView`), emit an `InteractionLog(event_type="undo", weight=-1.0, processing_status="pending")` inside the undo transaction.
- **Files**: `backend/core/views.py`
- **Verification**: Unit tests in `core.test_phase1_scenarios` and dedicated undo tests verify `InteractionLog` record creation.

### Task 3: Historical Interaction Reconciliation Service & Command
- **Description**: Implement `HistoricalReconciliationService` and CLI management command `reconcile_historical_interactions`. Identify the 499 unmatched historical swipes (pre-Session-80 baseline) and bulk-insert them into `InteractionLog` with `processing_status='pending'`, exact historical `created_at`, mapped weights, and deduplication safeguards.
- **Files**: `backend/core/services/historical_reconciliation.py`, `backend/core/management/commands/reconcile_historical_interactions.py`
- **Verification**: Test on baseline fixture verifying exactly 499 records inserted on run 1, and 0 on run 2.

### Task 4: Guest Identity Linking Service
- **Description**: Implement `IdentityLinkingService` in `backend/core/services/identity_linking.py` to handle guest conversion and session claiming. Provides `get_all_actor_ids_for_user(user)` resolving `[user.id] + linked_actor_ids`.
- **Files**: `backend/core/services/identity_linking.py`, `backend/core/views.py` (guest conversion hooks)
- **Verification**: Unit tests covering unique constraint enforcement and actor ID resolution.

### Task 5: Durable Taste Engine Service & Job Handler
- **Description**: Implement `TasteEngineService` in `backend/core/services/taste_engine.py` to claim pending logs for an actor set (`user_id__in=actor_ids, processing_status='pending'`), update `UserTasteProfile.learned_weights`, and atomically mark events `processed`. Register `recompute_taste_profile` handler in worker.
- **Files**: `backend/core/services/taste_engine.py`, `backend/core/management/commands/run_intelligence_worker.py`
- **Verification**: Unit and worker tests verifying taste weight calculation and atomic status transition.

### Task 6: Privacy-Preserving Tombstone Anonymization
- **Description**: Implement `TombstoneService` in `backend/core/services/tombstone.py`. Reassigns user logs to `system_deleted_actor`, scrubs PII from `metadata`, purges `UserIdentityLink`, deletes `UserTasteProfile`, and deletes user account without violating foreign keys.
- **Files**: `backend/core/services/tombstone.py`
- **Verification**: Test user deletion verifying log retention, PII scrubbing, and link cleanup.

### Task 7: Comprehensive Verification & PostgreSQL Concurrency Tests
- **Description**: Full test suite across SQLite and PostgreSQL covering identity linking, reconciliation idempotency, worker concurrency, and privacy tombstoning.
- **Files**: `backend/core/test_batch4_reconciliation_and_identity.py`, `backend/core/test_catalogue_queue_postgresql.py`
- **Verification**: Run all Batch 4 tests + regression suite on SQLite and PostgreSQL.

---

## Risks and Mitigations
| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **Duplicate Event Ingestion** | High | Composite key checking `(user_id, session_id, movie_id, mapped_event_type)` and atomic transaction with dry-run support. |
| **CASCADE Deletion of Historical Logs** | High | Tombstone re-assignment to `system_deleted_actor` before user row deletion. |
| **Race Conditions in Event Processing** | Medium | Row-level locking `select_for_update(skip_locked=True)` on `processing_status='pending'`. |
| **Performance Degradation on Actor Aggregation** | Low | Index on `UserIdentityLink.linked_actor_id` (`unique=True`) and composite index on `InteractionLog(user, processing_status)`. |
