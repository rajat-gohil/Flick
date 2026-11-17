import time
from django.core.management.base import BaseCommand
from core.services.outbox import ProposalExecutionWorker


class Command(BaseCommand):
    help = "Processes pending proposal replenishment messages from the transactional outbox."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-messages",
            type=int,
            default=10,
            help="Maximum messages to claim and process in one run.",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=300,
            help="Stale claim recovery timeout in seconds (default 300).",
        )
        parser.add_argument(
            "--daemon",
            action="store_true",
            help="Run continuously in a loop.",
        )
        parser.add_argument(
            "--interval",
            type=int,
            default=5,
            help="Loop sleep interval in seconds when in daemon mode (default 5).",
        )

    def handle(self, *args, **options):
        max_messages = options["max_messages"]
        timeout = options["timeout"]
        is_daemon = options["daemon"]
        interval = options["interval"]

        worker = ProposalExecutionWorker(claim_timeout_seconds=timeout)
        self.stdout.write(
            self.style.NOTICE(f"Starting ProposalExecutionWorker {worker.worker_id}...")
        )

        while True:
            summary = worker.process_batch(max_messages=max_messages)
            if summary["processed"] > 0 or summary["recovered_stale"] > 0 or summary["reaped_expired"] > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Processed batch: {summary['processed']} processed "
                        f"({summary['succeeded']} succeeded, {summary['failed']} failed), "
                        f"{summary['recovered_stale']} stale recovered, "
                        f"{summary['reaped_expired']} expired reaped."
                    )
                )

            if not is_daemon:
                break

            time.sleep(interval)
