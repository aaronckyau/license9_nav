from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.templatetags.static import static
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

from navapp.forms import ChineseAuthenticationForm, ChinesePasswordChangeForm

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url=static("favicon.svg"), permanent=False)),
    path("admin/", admin.site.urls),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=ChineseAuthenticationForm,
        ),
        name="login",
    ),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "accounts/password-change/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            form_class=ChinesePasswordChangeForm,
            success_url=reverse_lazy("dashboard"),
        ),
        name="password_change",
    ),
    path("", include("navapp.urls")),
]
