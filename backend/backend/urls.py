"""
URL configuration for backend project.
"""
from django.contrib import admin
from django.urls import path, include
from core.views import HealthCheckView

urlpatterns = [
    path('healthz/', HealthCheckView.as_view(), name='root-healthz'),
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
]
