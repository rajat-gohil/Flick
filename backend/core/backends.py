import logging
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Custom authentication backend that allows login with either email or username.
    Emits structured log messages without printing raw passwords, tokens, or personal credentials.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)

        if username is None or password is None:
            return None

        if isinstance(username, str):
            username = username.strip()

        user = (
            User.objects.filter(username__iexact=username).first()
            or User.objects.filter(email__iexact=username).first()
        )
        if user is None:
            logger.debug("Authentication failed: identity not found")
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            logger.info("Authentication succeeded for user_id=%s", user.id)
            return user

        logger.warning("Authentication failed: invalid credentials for user_id=%s", user.id)
        return None
