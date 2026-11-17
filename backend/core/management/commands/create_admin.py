import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class Command(BaseCommand):
    help = 'Create initial administrator user with securely supplied credentials'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Admin username')
        parser.add_argument('--email', type=str, help='Admin email')
        parser.add_argument('--password', type=str, help='Admin password')

    def handle(self, *args, **options):
        username = (
            options.get('username')
            or os.getenv('DJANGO_ADMIN_USERNAME')
            or os.getenv('DJANGO_SUPERUSER_USERNAME')
        )
        email = (
            options.get('email')
            or os.getenv('DJANGO_ADMIN_EMAIL')
            or os.getenv('DJANGO_SUPERUSER_EMAIL')
        )
        password = (
            options.get('password')
            or os.getenv('DJANGO_ADMIN_PASSWORD')
            or os.getenv('DJANGO_SUPERUSER_PASSWORD')
        )

        missing = []
        if not username:
            missing.append('username (--username or DJANGO_ADMIN_USERNAME)')
        if not email:
            missing.append('email (--email or DJANGO_ADMIN_EMAIL)')
        if not password:
            missing.append('password (--password or DJANGO_ADMIN_PASSWORD)')

        if missing:
            raise CommandError(
                f"Missing required administrator credentials: {', '.join(missing)}. "
                "Hardcoded fallback credentials have been disabled for security. "
                "Supply explicit credentials via CLI arguments or environment variables."
            )

        username = str(username).strip()
        email = str(email).strip()

        # Check if user already exists
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            if user.is_superuser:
                self.stdout.write(
                    self.style.WARNING(f"Administrator account '{username}' already exists. No changes made.")
                )
                return
            else:
                raise CommandError(
                    f"User '{username}' already exists as a non-administrator account. "
                    "Refusing to automatically promote an existing account to superuser."
                )

        # Validate password against configured validators
        temp_user = User(username=username, email=email)
        try:
            validate_password(password, user=temp_user)
        except ValidationError as e:
            raise CommandError(f"Password validation failed: {'; '.join(e.messages)}")

        # Create new superuser
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created admin user: {username} with staff/superuser permissions"
            )
        )
