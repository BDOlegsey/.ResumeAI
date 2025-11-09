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
    path("resume/<int:request_id>/", views.resume_detail, name="resume_detail"),
    path("resume/<int:request_id>/download/", views.download_resume, name="download_resume"),
    path("resume/<int:request_id>/view/", views.view_resume_file, name="view_resume_file"),

    # Изображения
    path("upload-images/", views.upload_images, name="upload_images"),
    path("delete-image/<int:image_id>/", views.delete_image, name="delete_image"),

    # РЕДАКТИРОВАНИЕ ПРОФИЛЯ - ВАЖНО: правильный порядок!
    path("profile/work-experience/edit/<int:experience_id>/", views.edit_work_experience, name="edit_work_experience"),
    path("profile/work-experience/delete/<int:experience_id>/", views.delete_work_experience, name="delete_work_experience"),
    path("profile/education/edit/<int:education_id>/", views.edit_education, name="edit_education"),
    path("profile/education/delete/<int:education_id>/", views.delete_education, name="delete_education"),
    path("profile/portfolio/edit/<int:item_id>/", views.edit_portfolio_item, name="edit_portfolio_item"),
    path("profile/portfolio/delete/<int:item_id>/", views.delete_portfolio_item, name="delete_portfolio_item"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)