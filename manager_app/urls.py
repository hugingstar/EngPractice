from django.urls import path
from . import views

urlpatterns = [
    path('logs/', views.get_recent_logs, name='get_recent_logs'),
]
