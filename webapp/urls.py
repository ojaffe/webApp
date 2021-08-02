from django.conf.urls import url
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.contrib.auth.views import LoginView, LogoutView
from django.views.generic import RedirectView

urlpatterns = [
    path('experiment/', include('experimentApp.urls'), name="experiment"),
    path('admin/', admin.site.urls),

    url(r'^login/$', LoginView.as_view(), name="jh"),
    url(r'^logout/$', LogoutView.as_view()),

    url(r'^$', RedirectView.as_view(url='/experiment/', permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)

    urlpatterns += staticfiles_urlpatterns()