import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fractal_medical_analysis.settings')
app = Celery('fractal_medical_analysis')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
