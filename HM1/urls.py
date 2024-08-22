from django.urls import path
from . import views
from .views import display_alerts, resolve_alert
from django.conf import settings
from django.conf.urls.static import static
from .views import create_alert_view  # Import the view function
from .views import create_alert_view, update_alert_view
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [

    path('alert-dashboard/', views.alert_dashboard, name='alert_dashboard'),
    path('alerts/', views.display_alerts, name='display_alerts'),
    path('alerts/resolve/<int:alert_id>/', views.resolve_alert, name='resolve_alert'),
    path('alerts/dismiss/<int:alert_id>/', views.dismiss_alert, name='dismiss_alert'),
    path('resolved_alerts/', views.resolved_alerts, name='resolved_alerts'),  # For viewing resolved alerts
    path('dismissed_alerts/', views.dismissed_alerts, name='dismissed_alerts'),
    path('dismiss_alert/<int:alert_id>/', views.dismiss_alert, name='dismiss_alert'),
    path('create_alert/', create_alert_view, name='create_alert'),
    path('update_alert/<int:pk>/', update_alert_view, name='update_alert'),
    path('add-site/', views.add_site, name='add_site'),
    path('sites/', views.list_sites, name='list_sites'),
    path('success/', views.success_page, name='success_page'),

   

] 

# Only add this in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)






