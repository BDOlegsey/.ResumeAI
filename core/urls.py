from django.urls import path
from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("result/", views.result, name="result"),
    path("help/", views.help_page, name="help"),
    path("contacts/", views.contacts, name="contacts"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("about/", views.about, name="about"),
]