from django.db import models
from analytics.models import Experiment


class ExperimentReport(models.Model):
    experiment = models.OneToOneField(Experiment, on_delete=models.CASCADE, related_name='report')
    pdf_file = models.FileField(upload_to='reports/', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Звіт: {self.experiment.title}'
