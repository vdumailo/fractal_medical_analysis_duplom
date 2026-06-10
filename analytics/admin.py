from django.contrib import admin
from .models import Experiment


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = ('title', 'dataset', 'mode', 'feature_set', 'status', 'created_at')
    list_filter = ('mode', 'feature_set', 'status')
    search_fields = ('title', 'dataset__title')
