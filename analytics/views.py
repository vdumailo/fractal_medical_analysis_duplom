from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, View

from datasets.models import Dataset
from .forms import ExperimentForm
from .models import Experiment
from .services.runner import execute_experiment


class ExperimentListView(ListView):
    model = Experiment
    template_name = 'analytics/list.html'
    context_object_name = 'experiments'


class ExperimentCreateView(CreateView):
    model = Experiment
    form_class = ExperimentForm
    template_name = 'analytics/create.html'

    def dispatch(self, request, *args, **kwargs):
        self.dataset = get_object_or_404(Dataset, pk=kwargs['dataset_pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dataset'] = self.dataset
        return context

    def form_valid(self, form):
        form.instance.dataset = self.dataset
        self.object = form.save()
        execute_experiment(self.object)
        self.object.refresh_from_db()
        if self.object.status == Experiment.Status.COMPLETED:
            messages.success(self.request, 'Експеримент виконано. Результати доступні на сторінці експерименту.')
        else:
            messages.error(self.request, 'Експеримент створено, але під час виконання виникла помилка. Деталі показано на сторінці результатів.')
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        messages.error(self.request, 'Експеримент не запущено: перевірте підсвічені поля форми.')
        return super().form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('analytics:detail', kwargs={'pk': self.object.pk})


class ExperimentDetailView(DetailView):
    model = Experiment
    template_name = 'analytics/detail.html'
    context_object_name = 'experiment'


class ExperimentRerunView(View):
    def post(self, request, pk):
        experiment = get_object_or_404(Experiment, pk=pk)
        execute_experiment(experiment)
        experiment.refresh_from_db()
        if experiment.status == Experiment.Status.COMPLETED:
            messages.success(request, 'Експеримент перезапущено та успішно виконано.')
        else:
            messages.error(request, 'Під час перезапуску виникла помилка. Деталі показано нижче.')
        return redirect('analytics:detail', pk=pk)
