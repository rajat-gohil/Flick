"""
Batch 3 Job Handlers for Flick Catalogue Intelligence.

Handlers:
- handle_sync_changes_feed: Polls TMDB Movie Changes Feed and enqueues enrichment jobs.
- handle_full_reconciliation: Executes 90-day staleness sweep across movie catalogue and enqueues enrichment jobs.
"""

from __future__ import annotations

import datetime
import inspect
import logging
import uuid
from typing import Any, Dict, Optional

from core.models import CatalogueJob

logger = logging.getLogger(__name__)


def to_json_safe(obj: Any) -> Any:
    """Recursively converts dates, datetimes, and UUIDs to JSON-safe primitives."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_json_safe(item) for item in obj]
    return obj


def handle_sync_changes_feed(
    job: CatalogueJob,
    worker_id: str,
    lease_token: uuid.UUID,
    generation: int,
) -> Dict[str, Any]:
    """
    Handler for 'sync_changes_feed' jobs:
    - Extracts parameters from job.payload (e.g., limit_pages, start_date, end_date, dry_run, force_reset).
    - Invokes poll_tmdb_changes() from core.services.tmdb_changes.
    - Returns summary dictionary with changes detected and enqueued.
    """
    payload = job.payload if isinstance(job.payload, dict) else {}
    logger.info(
        f"[{worker_id}] Handling sync_changes_feed for Job {job.id} (gen={generation}) with payload={payload}"
    )

    try:
        from core.services.tmdb_changes import poll_tmdb_changes
        func = poll_tmdb_changes
    except (ImportError, AttributeError):
        from core.services.tmdb_changes import TmdbChangesService
        service = TmdbChangesService()
        func = service.poll

    sig = inspect.signature(func)
    has_var_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    valid_params = {
        k: v for k, v in payload.items()
        if has_var_kwargs or k in sig.parameters
    }

    result = func(**valid_params)
    if isinstance(result, dict):
        return to_json_safe(result)
    return {
        "status": "success",
        "result": to_json_safe(result),
    }


def handle_full_reconciliation(
    job: CatalogueJob,
    worker_id: str,
    lease_token: uuid.UUID,
    generation: int,
) -> Dict[str, Any]:
    """
    Handler for 'full_reconciliation' jobs:
    - Extracts parameters from job.payload (e.g., batch_size, limit, dry_run, force_reset).
    - Invokes run_staleness_sweep() from core.services.staleness_sweep.
    - Returns summary dictionary with records scanned and enqueued.
    """
    payload = job.payload if isinstance(job.payload, dict) else {}
    logger.info(
        f"[{worker_id}] Handling full_reconciliation for Job {job.id} (gen={generation}) with payload={payload}"
    )

    try:
        from core.services.staleness_sweep import run_staleness_sweep
        func = run_staleness_sweep
    except (ImportError, AttributeError):
        from core.services import staleness_sweep as sweep_module
        if hasattr(sweep_module, "StalenessSweepService"):
            service = getattr(sweep_module, "StalenessSweepService")()
            func = getattr(service, "run_sweep", getattr(service, "sweep", None))
        else:
            raise

    sig = inspect.signature(func)
    has_var_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
    )
    valid_params = {
        k: v for k, v in payload.items()
        if has_var_kwargs or k in sig.parameters
    }

    result = func(**valid_params)
    if isinstance(result, dict):
        return to_json_safe(result)
    return {
        "status": "success",
        "result": to_json_safe(result),
    }
