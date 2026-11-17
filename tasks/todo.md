# Batch 4: Historical Interaction Reconciliation & Identity Linking — Task List

## Phase 1: Foundations & Parity
- [x] **Task 1: Schema & Migrations**
  - Add `UserIdentityLink` model with `unique=True` on `linked_actor_id`.
  - Add `processing_status` (`pending`, `processed`), `processed_at`, and `source_swipe_id` to `InteractionLog`.
  - Create and apply migration `0039_user_identity_link_and_interaction_processing_status`.
  - *Verification*: `python backend/manage.py test core.test_intelligence_models` passes (9/9).

- [x] **Task 2: Live Interaction Parity (`SwipeUndoView`)**
  - Wire `InteractionLog.objects.create(event_type='undo', weight=undo_weight, processing_status='pending')` into `SwipeUndoView` with exact inverse weights (-1.0 for LIKE, +1.2 for DISLIKE, -3.0 for SUPERLIKE).
  - *Verification*: Dedicated test verifying undo creates pending log event with inverse weights.

### Checkpoint 1: Foundations Complete
- [x] Schema applied cleanly to SQLite and PostgreSQL test databases.
- [x] Undo interaction parity tests pass.

---

## Phase 2: Reconciliation & Identity
- [x] **Task 3: Historical Interaction Reconciliation**
  - Implement `HistoricalReconciliationService` in `backend/core/services/historical_reconciliation.py`.
  - Implement management command `reconcile_historical_interactions` (`--dry-run`, `--limit`, `--batch-size`).
  - Idempotently ingest missing historical swipes into `InteractionLog` with `source_swipe_id` uniqueness.
  - *Verification*: Automated test asserts missing records ingested on run 1; 0 on run 2 (idempotency).

- [x] **Task 4: Guest Identity Linking Service**
  - Implement `IdentityLinkingService` (`link_guest_to_user`, `get_all_actor_ids_for_user`).
  - Strict cardinality check (one guest actor linked to at most one canonical user).
  - *Verification*: Unit tests verifying guest conversion, rejection of duplicate links, and query aggregation.

### Checkpoint 2: Reconciliation & Identity Complete
- [x] Historical reconciliation is verified idempotent.
- [x] Guest identity linking enforces strict uniqueness.

---

## Phase 3: Durable Taste Engine & Tombstone Anonymization
- [x] **Task 5: Durable Taste Engine Processor**
  - Implement `TasteEngineService.recompute_user_taste_profile(user)` with row locks.
  - Calculate updated `learned_weights` on `UserTasteProfile`.
  - Atomically transition `processing_status` to `processed`.
  - Register `recompute_taste_profile` handler in `run_intelligence_worker.py`.
  - *Verification*: Worker test claiming and processing pending user events.

- [x] **Task 6: Privacy-Preserving Tombstone Anonymization**
  - Implement `TombstoneService.anonymize_and_delete_user(user)`.
  - Reassign logs to `system_deleted_actor`, scrub metadata, purge identity links.
  - Delete user account without CASCADE loss of analytical interaction logs.
  - *Verification*: Test account deletion preserving scrubbed interaction history.

- [x] **Task 7: Comprehensive Verification & PostgreSQL Concurrency Suite**
  - Build `backend/core/test_batch4_reconciliation_and_identity.py` (25 unit tests).
  - Add PostgreSQL concurrency tests in `core.test_catalogue_queue_postgresql`.
  - Run full regression suite across SQLite and PostgreSQL.
  - *Verification*: 100% test pass rate across both backends (32 tests on SQLite, 38 tests on PostgreSQL, 68 regression tests).

### Checkpoint 3: Batch 4 Complete
- [x] All 7 tasks completed.
- [x] Zero unhandled errors or data leaks.
- [x] Ready for Batch 5 multi-surface personalization.
