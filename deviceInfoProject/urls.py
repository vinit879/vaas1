from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('info/', include('info.urls')),   
    path('HM1/', include('HM1.urls')),
    path('accounts/', include('django.contrib.auth.urls')),  # This includes the default authentication URLs
    path('login/', lambda request: redirect('accounts/login/')),  # Redirect /login to /accounts/login/
    path('accounts/', include('django.contrib.auth.urls')),  # Add this line for authentication URLs
    path('charts/', include('django.contrib.auth.urls')),
    path('register/',lambda request: redirect('/accounts/register/')),  # Point to your app's 
    


    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form1.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done3.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm4.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete5.html'), name='password_reset_complete'),
    

    path('', include('live_preview.urls')),
    
]
