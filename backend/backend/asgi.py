import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from core.routing import websocket_urlpatterns
from core.middleware import TokenAuthMiddlewareStack

django_asgi_app = get_asgi_application()

def _ensure_admin_account():
    username = (
        os.getenv("DJANGO_ADMIN_USERNAME")
        or os.getenv("DJANGO_SUPERUSER_USERNAME")
    )
    password = (
        os.getenv("DJANGO_ADMIN_PASSWORD")
        or os.getenv("DJANGO_SUPERUSER_PASSWORD")
    )
    email = (
        os.getenv("DJANGO_ADMIN_EMAIL")
        or os.getenv("DJANGO_SUPERUSER_EMAIL")
        or ""
    )

    # Fail-closed: never create or reset admin when credentials are not explicitly supplied
    if not (username and password):
        return

    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # Never reset an existing administrator password on application startup
        if User.objects.filter(username=username).exists():
            return

        User.objects.create_superuser(
            username=str(username).strip(),
            email=str(email).strip(),
            password=str(password)
        )
    except Exception as e:
        import logging
        logging.getLogger("core").warning("Could not auto-ensure admin account: %s", e)

_ensure_admin_account()

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": TokenAuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})