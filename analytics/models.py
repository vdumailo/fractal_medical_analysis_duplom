from django.db import models
from datasets.models import Dataset


class Experiment(models.Model):
    class Mode(models.TextChoices):
        CLASSIFICATION = 'classification', 'Класифікація'
        CLUSTERING = 'clustering', 'Кластеризація'
        ANOMALY = 'anomaly', 'Пошук аномалій'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Очікує'
        RUNNING = 'running', 'Виконується'
        COMPLETED = 'completed', 'Завершено'
        FAILED = 'failed', 'Помилка'

    class FeatureSet(models.TextChoices):
        STANDARD = 'standard', 'Лише класичні ознаки'
        FRACTAL = 'fractal', 'Лише фрактальні ознаки'
        COMBINED = 'combined', 'Комбінований набір ознак'
        COMPARE = 'compare', 'Порівняти всі набори'

    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE, related_name='experiments')
    title = models.CharField(max_length=255)
    mode = models.CharField(max_length=20, choices=Mode.choices)
    feature_set = models.CharField(max_length=20, choices=FeatureSet.choices, default=FeatureSet.COMPARE)
    model_name = models.CharField(max_length=100, default='random_forest')
    n_clusters = models.PositiveIntegerField(default=3)
    window_size = models.PositiveIntegerField(default=64)
    step_size = models.PositiveIntegerField(default=32)
    smoothing_window = models.PositiveIntegerField(default=3)
    normalize = models.BooleanField(default=True)
    detrend = models.BooleanField(default=False)
    fill_missing = models.BooleanField(default=True)
    remove_outliers = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    results = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
