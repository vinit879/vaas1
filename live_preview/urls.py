from django.urls import path
from . import views

urlpatterns = [
    path('live_preview/video_feed/<str:site>/<int:stream_id>/', views.video_feed, name='video_feed'),
    path('live_preview/control_stream/<str:site>/<int:stream_id>/<str:action>/', views.control_stream, name='control_stream'),
    path('live_preview/stop_all_streams/', views.stop_all_streams, name='stop_all_streams'),
    path('live_preview/stop_site_streams/<str:site>/', views.stop_site_streams, name='stop_site_streams'),
    path('live_preview/', views.live_stream1, name='live_stream1'),
]
