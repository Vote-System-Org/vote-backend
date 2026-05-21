from django.urls import path
from .views import LogAuditListView, VerifierIntegriteView

urlpatterns = [
    path('audit/logs/',      LogAuditListView.as_view(),    name='logs_audit'),
    path('audit/integrite/', VerifierIntegriteView.as_view(), name='integrite_audit'),
]