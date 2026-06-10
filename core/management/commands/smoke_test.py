from django.core.management.base import BaseCommand
from django.core.management import call_command

from analytics.models import Experiment
from analytics.services.runner import execute_experiment
from datasets.models import Dataset
from reports.services.pdf import generate_report


class Command(BaseCommand):
    help = 'Виконує швидку перевірку демонстраційного сценарію: дані, класифікація, кластеризація, аномалії та PDF.'

    def handle(self, *args, **options):
        call_command('seed_demo')
        dataset = Dataset.objects.filter(title='Демонстраційний медичний часовий ряд').first()
        if not dataset:
            raise RuntimeError('Демонстраційний набір даних не знайдено.')

        scenarios = [
            ('Smoke classification compare', Experiment.Mode.CLASSIFICATION, Experiment.FeatureSet.COMPARE, 'random_forest'),
            ('Smoke clustering', Experiment.Mode.CLUSTERING, Experiment.FeatureSet.COMBINED, 'kmeans'),
            ('Smoke anomaly', Experiment.Mode.ANOMALY, Experiment.FeatureSet.COMBINED, 'isolation_forest'),
        ]

        for title, mode, feature_set, model_name in scenarios:
            experiment = Experiment.objects.create(
                dataset=dataset,
                title=title,
                mode=mode,
                feature_set=feature_set,
                model_name=model_name,
                n_clusters=3,
                window_size=64,
                step_size=32,
                smoothing_window=3,
                normalize=True,
                detrend=False,
                fill_missing=True,
                remove_outliers=True,
            )
            execute_experiment(experiment)
            experiment.refresh_from_db()
            if experiment.status != Experiment.Status.COMPLETED:
                raise RuntimeError(f'Сценарій "{title}" завершився помилкою: {experiment.error_message}')
            if not experiment.results.get('dataset_summary'):
                raise RuntimeError(f'Сценарій "{title}" не сформував зведення результатів.')
            self.stdout.write(self.style.SUCCESS(f'{title}: OK'))

        report = generate_report(experiment)
        if not report.pdf_file:
            raise RuntimeError('PDF-звіт не сформовано.')
        self.stdout.write(self.style.SUCCESS('PDF report: OK'))
        self.stdout.write(self.style.SUCCESS('Smoke test completed successfully.'))
