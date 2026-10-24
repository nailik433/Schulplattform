"""Delete old student submissions (files + records) for data retention.

Examples:
    python manage.py purge_submissions                 # use retention setting
    python manage.py purge_submissions --days 400      # older than 400 days
    python manage.py purge_submissions --before 2026-08-01  # before a date
    python manage.py purge_submissions --dry-run       # only show what would go
"""

from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from worksheets.models import Submission, SubmissionFile


class Command(BaseCommand):
    help = "Löscht alte Abgaben (Submissions) inklusive der hochgeladenen Dateien."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Abgaben löschen, die älter als N Tage sind.",
        )
        parser.add_argument(
            "--before",
            type=str,
            default=None,
            help="Abgaben vor diesem Datum löschen (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Nur anzeigen, was gelöscht würde – nichts löschen.",
        )

    def _cutoff(self, days, before):
        if before:
            try:
                naive = datetime.strptime(before, "%Y-%m-%d")
            except ValueError:
                raise CommandError("--before muss im Format YYYY-MM-DD sein.")
            return timezone.make_aware(naive)
        if days is None:
            days = settings.SUBMISSION_RETENTION_DAYS
        if days < 0:
            raise CommandError("--days darf nicht negativ sein.")
        return timezone.now() - timezone.timedelta(days=days)

    def handle(self, *args, **options):
        cutoff = self._cutoff(options["days"], options["before"])
        dry_run = options["dry_run"]

        submissions = Submission.objects.filter(created_at__lt=cutoff)
        sub_count = submissions.count()
        files = SubmissionFile.objects.filter(submission__in=submissions)
        file_count = files.count()

        self.stdout.write(
            f"Stichtag: {cutoff:%d.%m.%Y %H:%M} – {sub_count} Abgabe(n) "
            f"mit {file_count} Datei(en) betroffen."
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Testlauf – es wird nichts gelöscht."))
            return

        # Remove file blobs first so no orphaned files remain on disk.
        for sf in files.iterator():
            sf.file.delete(save=False)
        submissions.delete()  # cascades to the SubmissionFile rows

        self.stdout.write(
            self.style.SUCCESS(
                f"{sub_count} Abgabe(n) und {file_count} Datei(en) gelöscht."
            )
        )
