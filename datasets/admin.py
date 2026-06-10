from django.contrib import admin
from .models import Dataset


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ('title', 'signal_type', 'sampling_interval', 'created_at')
    search_fields = ('title', 'description')
    list_filter = ('signal_type', 'created_at')
