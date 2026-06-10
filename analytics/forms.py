from django import forms
from core.forms import BootstrapFormMixin
from .models import Experiment


CLASSIFICATION_MODELS = {
    'random_forest',
    'logistic_regression',
    'svm',
}
CLUSTERING_MODELS = {
    'kmeans',
    'agglomerative',
    'dbscan',
}
ANOMALY_MODELS = {
    'isolation_forest',
}


class ExperimentForm(BootstrapFormMixin, forms.ModelForm):
    MODEL_CHOICES = [
        ('random_forest', 'Random Forest'),
        ('logistic_regression', 'Логістична регресія'),
        ('svm', 'SVM'),
        ('kmeans', 'K-means'),
        ('agglomerative', 'Agglomerative clustering'),
        ('dbscan', 'DBSCAN'),
        ('isolation_forest', 'Isolation Forest'),
    ]

    model_name = forms.ChoiceField(label='Алгоритм аналізу', choices=MODEL_CHOICES, initial='random_forest')
    n_clusters = forms.IntegerField(label='Кількість кластерів', required=False, min_value=2, initial=3)

    class Meta:
        model = Experiment
        fields = [
            'title', 'mode', 'feature_set', 'model_name', 'n_clusters', 'window_size',
            'step_size', 'smoothing_window', 'normalize', 'detrend', 'fill_missing',
            'remove_outliers', 'notes'
        ]
        labels = {
            'title': 'Назва експерименту',
            'mode': 'Режим аналізу',
            'feature_set': 'Набір ознак',
            'n_clusters': 'Кількість кластерів',
            'window_size': 'Розмір ковзного вікна',
            'step_size': 'Крок сегментації',
            'smoothing_window': 'Вікно згладжування',
            'normalize': 'Нормалізувати сигнал',
            'detrend': 'Усунути тренд',
            'fill_missing': 'Заповнити пропуски',
            'remove_outliers': 'Обмежити викиди',
            'notes': 'Нотатки до експерименту',
        }
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'feature_set': 'Порівняння всіх наборів ознак доступне для задач класифікації.',
            'n_clusters': 'Використовується лише для кластеризації. Для інших режимів параметр ігнорується.',
            'window_size': 'Кількість точок у сегменті часового ряду. Для коротких рядів зменшіть це значення.',
            'step_size': 'Крок пересування ковзного вікна. Менший крок дає більше сегментів.',
            'smoothing_window': 'Довжина вікна згладжування. Значення 1 вимикає згладжування.',
            'notes': 'Необов’язково. Можна коротко вказати мету експерименту або особливості набору.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['n_clusters'].required = False
        self.fields['n_clusters'].help_text = self.Meta.help_texts['n_clusters']
        self.fields['feature_set'].required = True
        self.fields['model_name'].required = True

    def clean(self):
        cleaned_data = super().clean()
        window_size = cleaned_data.get('window_size') or 0
        step_size = cleaned_data.get('step_size') or 0
        smoothing_window = cleaned_data.get('smoothing_window') or 0
        n_clusters = cleaned_data.get('n_clusters')
        mode = cleaned_data.get('mode')
        feature_set = cleaned_data.get('feature_set')
        model_name = cleaned_data.get('model_name')

        if window_size < 8:
            self.add_error('window_size', 'Розмір вікна має бути не меншим за 8 точок.')
        if step_size < 1:
            self.add_error('step_size', 'Крок сегментації має бути додатним.')
        if step_size > window_size:
            self.add_error('step_size', 'Крок сегментації не може бути більшим за розмір вікна.')
        if smoothing_window < 1:
            self.add_error('smoothing_window', 'Вікно згладжування має бути не меншим за 1.')

        if mode == Experiment.Mode.CLUSTERING:
            if not n_clusters or n_clusters < 2:
                self.add_error('n_clusters', 'Для кластеризації потрібно щонайменше 2 кластери.')
        else:
            cleaned_data['n_clusters'] = n_clusters or 3

        if feature_set == Experiment.FeatureSet.COMPARE and mode != Experiment.Mode.CLASSIFICATION:
            self.add_error('feature_set', 'Порівняння всіх наборів ознак доступне лише для класифікації.')

        if mode == Experiment.Mode.CLASSIFICATION and model_name not in CLASSIFICATION_MODELS:
            self.add_error('model_name', 'Для класифікації доступні лише Random Forest, логістична регресія або SVM.')
        elif mode == Experiment.Mode.CLUSTERING and model_name not in CLUSTERING_MODELS:
            self.add_error('model_name', 'Для кластеризації доступні лише K-means, Agglomerative clustering або DBSCAN.')
        elif mode == Experiment.Mode.ANOMALY and model_name not in ANOMALY_MODELS:
            self.add_error('model_name', 'Для пошуку аномалій використовується Isolation Forest.')

        return cleaned_data
