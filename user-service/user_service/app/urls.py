from django.urls import path

from .views import LoginView, RegisterView, UserListView


urlpatterns = [
    path('auth/register', RegisterView.as_view(), name='auth-register'),
    path('auth/login', LoginView.as_view(), name='auth-login'),
    path('users/', UserListView.as_view(), name='user-list'),
]
