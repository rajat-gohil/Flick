"""
URL configuration for backend project.
"""
from django.contrib import admin
from django.urls import path, include
from core.views import HealthCheckView
from core.views_invite import SessionInvitePreviewView

urlpatterns = [
    path('healthz/', HealthCheckView.as_view(), name='root-healthz'),
    path('admin/', admin.site.urls),
    path('j/<str:code>/', SessionInvitePreviewView.as_view(), name='invite-preview-short'),
    path('join/<str:code>/', SessionInvitePreviewView.as_view(), name='invite-preview-long'),
    path('api/', include('core.urls')),
]
