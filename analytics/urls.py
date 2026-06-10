from django.urls import path
from .views import ExperimentCreateView, ExperimentDetailView, ExperimentListView, ExperimentRerunView

app_name = 'analytics'

urlpatterns = [
    path('', ExperimentListView.as_view(), name='list'),
    path('<int:pk>/', ExperimentDetailView.as_view(), name='detail'),
    path('<int:pk>/rerun/', ExperimentRerunView.as_view(), name='rerun'),
    path('dataset/<int:dataset_pk>/create/', ExperimentCreateView.as_view(), name='create'),
]
