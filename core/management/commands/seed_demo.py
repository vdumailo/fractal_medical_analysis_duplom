from pathlib import Path
from django.core.files import File
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from datasets.models import Dataset


class Command(BaseCommand):
    help = 'Створює демонстраційного користувача та завантажує приклад набору даних.'

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username='demo')
        if created:
            user.set_password('demo12345')
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.SUCCESS('Створено користувача demo / demo12345'))
        else:
            self.stdout.write('Користувач demo уже існує.')

        sample_path = Path('sample_data/demo_medical_timeseries.csv')
        if not sample_path.exists():
            self.stdout.write(self.style.ERROR('Файл sample_data/demo_medical_timeseries.csv не знайдено.'))
            return

        if Dataset.objects.filter(title='Демонстраційний медичний часовий ряд').exists():
            self.stdout.write('Демонстраційний набір уже існує.')
            return

        with sample_path.open('rb') as fh:
            dataset = Dataset(
                title='Демонстраційний медичний часовий ряд',
                description='Синтетичний набір для перевірки класифікації, кластеризації та виявлення аномалій.',
                signal_type=Dataset.SignalType.ECG,
                sampling_interval=1.0,
                value_column='value',
                time_column='time',
                label_column='label',
                subject_column='subject_id',
                uploaded_by=user,
            )
            dataset.file.save(sample_path.name, File(fh), save=True)
        self.stdout.write(self.style.SUCCESS('Демонстраційний набір даних завантажено.'))
