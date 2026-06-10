from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Dataset(models.Model):
    class SignalType(models.TextChoices):
        ECG = 'ecg', 'ЕКГ'
        EEG = 'eeg', 'ЕЕГ'
        PPG = 'ppg', 'Фотоплетизмограма'
        RESP = 'resp', 'Респіраторний сигнал'
        GLUCOSE = 'glucose', 'Глікемічний моніторинг'
        OTHER = 'other', 'Інший тип'

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    signal_type = models.CharField(max_length=20, choices=SignalType.choices, default=SignalType.OTHER)
    file = models.FileField(upload_to='datasets/')
    sampling_interval = models.FloatField(default=1.0, help_text='Інтервал дискретизації у секундах')
    value_column = models.CharField(max_length=100, default='value')
    time_column = models.CharField(max_length=100, blank=True, default='time')
    label_column = models.CharField(max_length=100, blank=True, default='label')
    subject_column = models.CharField(max_length=100, blank=True, default='subject_id')
    is_anonymized = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
