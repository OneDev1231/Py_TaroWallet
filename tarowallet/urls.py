"""tarowallet URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView
from walletapp.sitemaps import StaticViewSitemap
from walletapp.views import health, signup_redirect

sitemaps = {
    "static": StaticViewSitemap,
}

urlpatterns = [
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": sitemaps},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),
    path("admin/", admin.site.urls),
    path("walletapp/", include("walletapp.urls")),
    path("", RedirectView.as_view(url="walletapp/")),
    # path("accounts/", include("django.contrib.auth.urls")),
    path("health", health),
    path("", include("allauth.urls")),
    path("social/signup/", signup_redirect, name="signup_redirect"),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
