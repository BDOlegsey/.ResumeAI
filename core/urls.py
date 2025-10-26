from django.urls import path
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
    path("resume/<int:request_id>/", views.resume_detail, name="resume_detail"),
    path("resume/<int:request_id>/download/", views.download_resume, name="download_resume"),
]