from django.core.management.base import BaseCommand, CommandError

from apps.file_tracking.services import record_transfer


class Command(BaseCommand):
    help = "Record a disk-to-disk file transfer from the CLI."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, help="Source path, e.g. C:\\data\\report.pdf")
        parser.add_argument("--destination", required=True, help="Destination path, e.g. D:\\archive\\report.pdf")
        parser.add_argument("--size", type=int, default=0, help="File size in bytes")
        parser.add_argument("--process", default="", help="Process or tool that initiated the transfer")
        parser.add_argument("--status", default="completed", choices=["detected", "in_progress", "completed", "failed", "quarantined"])

    def handle(self, *args, **options):
        if options["source"] == options["destination"]:
            raise CommandError("Source and destination must be different.")
        transfer = record_transfer(
            {
                "source_path": options["source"],
                "destination_path": options["destination"],
                "size_bytes": options["size"],
                "process_name": options["process"],
                "status": options["status"],
            }
        )
        self.stdout.write(self.style.SUCCESS(f"Recorded transfer {transfer.id}: {transfer.file_name}"))

