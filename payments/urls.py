from django.urls import path

from . import app_api as a
from . import dashboard as d
from .views import (
    HistoryView, PaymentStatusView, PaymentView, TerminalPaymentStatusView,
    TerminalPaymentView, WalletView,
)

# Mounted at api/dev/mock/: shared-token development API.
urlpatterns = [
    path("payments/", PaymentView.as_view(), name="demo-payment"),
    path("payments/<str:payment_id>/", PaymentStatusView.as_view(), name="demo-payment-status"),
    path("wallets/", WalletView.as_view(), name="demo-wallets"),
    path("history/", HistoryView.as_view(), name="demo-history"),
]

# Mounted at api/terminal/: per-terminal key, mock fingerprint.
terminal_urlpatterns = [
    path("payments/", TerminalPaymentView.as_view(), name="terminal-payment"),
    path("payments/<str:payment_id>/", TerminalPaymentStatusView.as_view(), name="terminal-payment-status"),
]

# Mounted at api/: human session login and dashboards.
web_urlpatterns = [
    path("auth/csrf/", d.CsrfView.as_view()),
    path("auth/login/", d.LoginView.as_view()),
    path("auth/logout/", d.LogoutView.as_view()),
    path("auth/me/", d.MeView.as_view()),
    path("auth/register/", a.RegisterView.as_view()),
    path("customer/terminals/", a.CustomerTerminals.as_view()),
    path("customer/enroll/", a.CustomerEnroll.as_view()),
    path("customer/payments/<str:pk>/", a.CustomerPaymentDetail.as_view()),
    path("merchant/payments/<str:pk>/", a.MerchantPaymentDetail.as_view()),
    path("merchant/simulate/", a.MerchantSimulate.as_view()),
    path("admin/audit/", a.AdminAudit.as_view()),
    path("customer/overview/", d.CustomerOverview.as_view()),
    path("customer/payments/", d.CustomerPayments.as_view()),
    path("customer/enrollments/<int:pk>/deletion-request/", d.DeletionRequest.as_view()),
    path("merchant/overview/", d.MerchantOverview.as_view()),
    path("merchant/payments/", d.MerchantPayments.as_view()),
    path("admin/overview/", d.AdminOverview.as_view()),
    path("admin/payments/", d.AdminPayments.as_view()),
    path("admin/terminals/<int:pk>/revoke/", d.RevokeTerminal.as_view()),
    path("admin/enrollments/<int:pk>/revoke/", d.RevokeEnrollment.as_view()),
]
