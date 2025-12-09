from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("profile/", views.profile, name="profile"),
    path("result/", views.result, name="result"),
    path("history/", views.history, name="history"),
    path(
        "resume/<int:request_id>/",
        views.resume_detail,
        name="resume_detail",
    ),
    path(
        "resume/<int:request_id>/archive/download/",
        views.download_archive,
        name="download_archive",
    ),
    path(
        "resume/<int:request_id>/archive/view/",
        views.view_archive_file,
        name="view_archive_file",
    ),
    path(
        "result/<int:result_id>/docx/",
        views.download_result_docx,
        name="download_result_docx",
    ),
    path(
        "result/<int:result_id>/json/",
        views.download_result_json,
        name="download_result_json",
    ),
    path("images/upload/", views.upload_images, name="upload_images"),
    path(
        "images/<int:image_id>/delete/",
        views.delete_image,
        name="delete_image",
    ),
    path(
        "experience/<int:experience_id>/delete/",
        views.delete_work_experience,
        name="delete_work_experience",
    ),
    path(
        "education/<int:education_id>/delete/",
        views.delete_education,
        name="delete_education",
    ),
    path(
        "portfolio/<int:item_id>/delete/",
        views.delete_portfolio_item,
        name="delete_portfolio_item",
    ),
    path(
        "experience/<int:experience_id>/edit/",
        views.edit_work_experience,
        name="edit_work_experience",
    ),
    path(
        "education/<int:education_id>/edit/",
        views.edit_education,
        name="edit_education",
    ),
    path(
        "portfolio/<int:item_id>/edit/",
        views.edit_portfolio_item,
        name="edit_portfolio_item",
    ),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("help/", views.help_page, name="help"),
    path("contacts/", views.contacts, name="contacts"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("about/", views.about, name="about"),
]
