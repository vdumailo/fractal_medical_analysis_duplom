from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView

from .forms import DatasetForm
from .models import Dataset
from .services.io import (
    dataframe_preview,
    infer_columns_from_dataframe,
    read_dataset_dataframe,
    read_uploaded_dataframe,
    summarize_dataframe,
)


DEFAULT_COLUMN_VALUES = {
    'time_column': 'time',
    'value_column': 'value',
    'label_column': 'label',
    'subject_column': 'subject_id',
}


class DatasetListView(ListView):
    model = Dataset
    template_name = 'datasets/list.html'
    context_object_name = 'datasets'


class DatasetCreateView(CreateView):
    model = Dataset
    form_class = DatasetForm
    template_name = 'datasets/create.html'
    success_url = reverse_lazy('datasets:list')

    def _apply_column_mapping(self, form):
        uploaded_file = form.cleaned_data['file']
        df = read_uploaded_dataframe(uploaded_file)
        available_columns = [str(column) for column in df.columns]
        inferred = infer_columns_from_dataframe(df)

        resolved: dict[str, str] = {}
        for field_name, default_value in DEFAULT_COLUMN_VALUES.items():
            raw_value = (form.cleaned_data.get(field_name) or '').strip()
            should_autodetect = not raw_value
            if raw_value == default_value and raw_value not in available_columns:
                should_autodetect = True

            if should_autodetect:
                resolved[field_name] = inferred.get(field_name, '')
            else:
                resolved[field_name] = raw_value

        if not resolved['value_column']:
            form.add_error('value_column', 'Не вдалося автоматично визначити колонку значень. Вкажіть її вручну.')
            return None

        for field_name, column_name in resolved.items():
            if column_name and column_name not in available_columns:
                form.add_error(field_name, f"Колонку '{column_name}' не знайдено у файлі. Доступні колонки: {', '.join(available_columns)}")

        if form.errors:
            return None

        for field_name, column_name in resolved.items():
            setattr(form.instance, field_name, column_name)

        return {
            'available_columns': available_columns,
            'resolved': resolved,
        }

    def form_valid(self, form):
        mapping_info = self._apply_column_mapping(form)
        if mapping_info is None:
            return self.form_invalid(form)

        if self.request.user.is_authenticated:
            form.instance.uploaded_by = self.request.user

        response = super().form_valid(form)
        resolved = mapping_info['resolved']
        detected_parts = []
        labels = {
            'time_column': 'час',
            'value_column': 'значення',
            'label_column': 'мітки',
            'subject_column': 'суб’єкт',
        }
        for key, title in labels.items():
            if resolved.get(key):
                detected_parts.append(f"{title}: {resolved[key]}")
        if detected_parts:
            messages.success(self.request, 'Набір даних успішно завантажено. Автоматично визначено структуру колонок: ' + '; '.join(detected_parts) + '.')
        else:
            messages.success(self.request, 'Набір даних успішно завантажено.')
        return response


class DatasetDetailView(DetailView):
    model = Dataset
    template_name = 'datasets/detail.html'
    context_object_name = 'dataset'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        df = read_dataset_dataframe(self.object.file.path)
        context['summary'] = summarize_dataframe(df)
        context['preview'] = dataframe_preview(df)
        context['preview_columns'] = list(df.columns)
        context['experiments'] = self.object.experiments.all()[:10]
        return context


class DatasetPreviewPartialView(TemplateView):
    template_name = 'datasets/partials/preview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dataset = get_object_or_404(Dataset, pk=kwargs['pk'])
        df = read_dataset_dataframe(dataset.file.path)
        context['dataset'] = dataset
        context['summary'] = summarize_dataframe(df)
        context['preview'] = dataframe_preview(df)
        context['preview_columns'] = list(df.columns)
        return context


class DatasetDeleteView(DeleteView):
    model = Dataset
    success_url = reverse_lazy('datasets:list')
    template_name = 'datasets/delete.html'
