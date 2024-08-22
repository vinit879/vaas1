from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import logout_view

urlpatterns = [
    # Login URL
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    
    # Logout URL using CustomLogoutView
    path('logout/', logout_view, name='logout'),

    # Dashboard and other views
    path('dashboard/', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),  # URL for registration
    path('profile/', views.profile, name='profile'),     # URL for user profile
    path('charts/', views.dashboard_view, name='charts'),
]
