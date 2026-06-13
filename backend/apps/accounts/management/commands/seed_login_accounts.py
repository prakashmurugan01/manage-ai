import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone


User = get_user_model()


LOGIN_ACCOUNTS = [
    {
        "email": "super@manageai.local",
        "username": "super",
        "first_name": "Avery",
        "last_name": "Stone",
        "role": User.Role.SUPER_ADMIN,
        "is_staff": True,
        "is_superuser": True,
    },
    {
        "email": "admin@manageai.local",
        "username": "admin",
        "first_name": "Mira",
        "last_name": "Kapoor",
        "role": User.Role.ADMIN,
        "is_staff": True,
        "is_superuser": False,
    },
    {
        "email": "dev@manageai.local",
        "username": "dev",
        "first_name": "Jon",
        "last_name": "Reed",
        "role": User.Role.DEVELOPER,
        "is_staff": False,
        "is_superuser": False,
    },
    {
        "email": "client@manageai.local",
        "username": "client",
        "first_name": "Nina",
        "last_name": "Shah",
        "role": User.Role.CLIENT,
        "is_staff": False,
        "is_superuser": False,
    },
]


class Command(BaseCommand):
    help = "Create or repair the default approved login accounts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=os.getenv("MANAGEAI_SEED_PASSWORD", "ManageAI@12345"),
            help="Password assigned to the default login accounts.",
        )
        parser.add_argument(
            "--no-reset-passwords",
            action="store_true",
            help="Do not reset passwords for accounts that already exist.",
        )
        parser.add_argument(
            "--approve-existing-active",
            action="store_true",
            help="Mark all active existing accounts as approved after seeding login accounts.",
        )

    def handle(self, *args, **options):
        password = options["password"]
        reset_passwords = not options["no_reset_passwords"]
        now = timezone.now()

        for account in LOGIN_ACCOUNTS:
            user, created = User.objects.get_or_create(
                email=account["email"],
                defaults={
                    "username": account["username"],
                    "first_name": account["first_name"],
                    "last_name": account["last_name"],
                    "role": account["role"],
                    "is_staff": account["is_staff"],
                    "is_superuser": account["is_superuser"],
                    "is_active": True,
                    "approval_status": User.ApprovalStatus.APPROVED,
                    "approved_at": now,
                },
            )
            update_fields = set()

            for field in ("first_name", "last_name", "role", "is_staff", "is_superuser"):
                desired = account[field]
                if getattr(user, field) != desired:
                    setattr(user, field, desired)
                    update_fields.add(field)

            if user.username != account["username"] and not User.objects.exclude(pk=user.pk).filter(username=account["username"]).exists():
                user.username = account["username"]
                update_fields.add("username")

            if not user.is_active:
                user.is_active = True
                update_fields.add("is_active")
            if user.approval_status != User.ApprovalStatus.APPROVED:
                user.approval_status = User.ApprovalStatus.APPROVED
                update_fields.add("approval_status")
            if user.rejection_reason:
                user.rejection_reason = ""
                update_fields.add("rejection_reason")
            if user.suspended_at is not None:
                user.suspended_at = None
                update_fields.add("suspended_at")
            if user.approved_at is None:
                user.approved_at = now
                update_fields.add("approved_at")

            if created or reset_passwords:
                user.set_password(password)
                update_fields.add("password")

            if update_fields:
                user.save(update_fields=update_fields)

            action = "created" if created else "repaired"
            self.stdout.write(self.style.SUCCESS(f"{account['email']} {action} and approved for login."))

        if options["approve_existing_active"]:
            updated = User.objects.filter(is_active=True).exclude(approval_status=User.ApprovalStatus.APPROVED).update(
                approval_status=User.ApprovalStatus.APPROVED,
                rejection_reason="",
                suspended_at=None,
            )
            self.stdout.write(self.style.SUCCESS(f"Approved {updated} additional active account(s)."))

        self.stdout.write(self.style.SUCCESS("Default login accounts are ready."))
