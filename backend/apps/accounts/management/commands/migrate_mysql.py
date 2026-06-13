from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Run every migration and prepare login accounts for a MySQL database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=None,
            help="Password assigned to the default login accounts.",
        )
        parser.add_argument(
            "--skip-login-accounts",
            action="store_true",
            help="Only run migrations; do not create or repair default login accounts.",
        )
        parser.add_argument(
            "--approve-existing-active",
            action="store_true",
            help="Mark all active existing accounts as approved after migrations.",
        )
        parser.add_argument(
            "--seed-demo",
            action="store_true",
            help="Seed the full demo workspace after migrations and login accounts.",
        )
        parser.add_argument(
            "--allow-non-mysql",
            action="store_true",
            help="Allow this helper to run against the configured non-MySQL database.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "mysql" and not options["allow_non_mysql"]:
            raise CommandError(
                "DB_ENGINE is not configured for MySQL. Set DB_ENGINE=mysql in backend/.env, "
                "or pass --allow-non-mysql for local validation."
            )

        verbosity = options.get("verbosity", 1)
        self.stdout.write("Running all Django migrations...")
        call_command("migrate", interactive=False, verbosity=verbosity)

        if not options["skip_login_accounts"]:
            seed_options = {
                "verbosity": verbosity,
                "approve_existing_active": options["approve_existing_active"],
            }
            if options["password"]:
                seed_options["password"] = options["password"]
            call_command("seed_login_accounts", **seed_options)

        if options["seed_demo"]:
            call_command("seed_demo", verbosity=verbosity)

        self.stdout.write(self.style.SUCCESS("MySQL migration bootstrap complete."))
