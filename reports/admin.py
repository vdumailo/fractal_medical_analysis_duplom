from django.contrib import admin
from .models import ExperimentReport


@admin.register(ExperimentReport)
class ExperimentReportAdmin(admin.ModelAdmin):
    list_display = ('experiment', 'created_at')
