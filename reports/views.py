from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from analytics.models import Experiment
from .services.pdf import generate_report


class ReportDownloadView(View):
    def get(self, request, experiment_pk):
        experiment = get_object_or_404(Experiment, pk=experiment_pk)
        if experiment.status != Experiment.Status.COMPLETED:
            messages.warning(request, 'PDF-звіт доступний лише після успішного завершення експерименту.')
            return redirect('analytics:detail', pk=experiment.pk)

        try:
            report = generate_report(experiment)
        except Exception as exc:
            messages.error(request, f'Не вдалося сформувати PDF-звіт: {exc}')
            return redirect('analytics:detail', pk=experiment.pk)

        return FileResponse(report.pdf_file.open('rb'), as_attachment=True, filename=report.pdf_file.name.split('/')[-1])
