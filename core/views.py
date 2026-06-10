from django.views.generic import TemplateView
from datasets.models import Dataset
from analytics.models import Experiment


class HomeView(TemplateView):
    template_name = 'core/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['datasets_count'] = Dataset.objects.count()
        context['experiments_count'] = Experiment.objects.count()
        context['completed_experiments'] = Experiment.objects.filter(status=Experiment.Status.COMPLETED).count()
        context['latest_datasets'] = Dataset.objects.order_by('-created_at')[:5]
        context['latest_experiments'] = Experiment.objects.select_related('dataset').order_by('-created_at')[:5]
        return context


class HelpView(TemplateView):
    template_name = 'core/help.html'
