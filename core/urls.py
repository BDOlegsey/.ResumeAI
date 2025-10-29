from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("result/", views.result, name="result"),
    path("help/", views.help_page, name="help"),
    path("contacts/", views.contacts, name="contacts"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("about/", views.about, name="about"),

    # Аутентификация
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # История и профиль
    path("history/", views.history, name="history"),
    path("profile/", views.profile, name="profile"),

    # Детали и файлы
    path("resume/<int:request_id>/", views.resume_detail, name="resume_detail"),
    path("resume/<int:request_id>/download/", views.download_resume, name="download_resume"),
    path("resume/<int:request_id>/view/", views.view_resume_file, name="view_resume_file"),

    # Изображения
    path("upload-images/", views.upload_images, name="upload_images"),
    path("delete-image/<int:image_id>/", views.delete_image, name="delete_image"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
