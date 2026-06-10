from django.urls import path
from .views import (
    DatasetCreateView,
    DatasetDeleteView,
    DatasetDetailView,
    DatasetListView,
    DatasetPreviewPartialView,
)

app_name = 'datasets'

urlpatterns = [
    path('', DatasetListView.as_view(), name='list'),
    path('create/', DatasetCreateView.as_view(), name='create'),
    path('<int:pk>/', DatasetDetailView.as_view(), name='detail'),
    path('<int:pk>/preview/', DatasetPreviewPartialView.as_view(), name='preview'),
    path('<int:pk>/delete/', DatasetDeleteView.as_view(), name='delete'),
]
