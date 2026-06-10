from django import forms
from core.forms import BootstrapFormMixin
from .models import Dataset


class DatasetForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Dataset
        fields = [
            'title', 'description', 'signal_type', 'file', 'sampling_interval',
            'time_column', 'value_column', 'label_column', 'subject_column', 'is_anonymized'
        ]
        labels = {
            'title': 'Назва набору даних',
            'description': 'Опис набору даних',
            'signal_type': 'Тип медичного сигналу',
            'file': 'Файл з даними',
            'sampling_interval': 'Інтервал дискретизації, с',
            'time_column': 'Колонка часу',
            'value_column': 'Колонка значень сигналу',
            'label_column': 'Колонка міток класів',
            'subject_column': 'Колонка пацієнта або серії',
            'is_anonymized': 'Дані деперсоналізовані',
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'file': 'Підтримуються формати CSV, XLSX та XLS. CSV може мати кому або крапку з комою як розділювач.',
            'sampling_interval': 'Інтервал між сусідніми відліками сигналу у секундах. Якщо в файлі є колонка часу, параметр використовується як довідковий.',
            'time_column': 'Необов’язково. Якщо поле порожнє, система спробує визначити колонку часу автоматично.',
            'value_column': 'Необов’язково. Якщо поле порожнє, система сама підбере основну числову колонку сигналу.',
            'label_column': 'Необов’язково. Потрібно для класифікації. Якщо поле порожнє, система спробує знайти мітки автоматично.',
            'subject_column': 'Необов’язково. Використовується для поділу сигналів різних пацієнтів або серій.',
            'is_anonymized': 'Позначте, якщо файл не містить ПІБ, номера телефону, адреси та інших персональних даних.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ('time_column', 'value_column', 'label_column', 'subject_column'):
            self.fields[field_name].required = False
            self.fields[field_name].initial = ''
            self.fields[field_name].widget.attrs['placeholder'] = 'залиште порожнім для автовизначення'
        self.fields['description'].widget.attrs['placeholder'] = 'Наприклад: деперсоналізований фрагмент ЕКГ/ЕЕГ/PPG з мітками станів'

    def clean_file(self):
        file = self.cleaned_data['file']
        ext = file.name.lower().split('.')[-1]
        if ext not in {'csv', 'xlsx', 'xls'}:
            raise forms.ValidationError('Підтримуються лише файли CSV або XLSX/XLS.')
        if getattr(file, 'size', 0) > 25 * 1024 * 1024:
            raise forms.ValidationError('Файл завеликий для демонстраційної версії. Максимальний розмір – 25 МБ.')
        return file
