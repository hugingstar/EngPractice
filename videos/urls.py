from django.urls import path
from . import views

urlpatterns = [
    path('transcript/', views.get_video_transcript, name='get_transcript'),
]
