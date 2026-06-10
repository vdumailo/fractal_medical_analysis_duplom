from __future__ import annotations

from django.utils import timezone

from analytics.models import Experiment
from .pipeline import ExperimentConfig, run_experiment


def build_config(experiment: Experiment) -> ExperimentConfig:
    return ExperimentConfig(
        mode=experiment.mode,
        feature_set=experiment.feature_set,
        model_name=experiment.model_name,
        n_clusters=experiment.n_clusters,
        window_size=experiment.window_size,
        step_size=experiment.step_size,
        smoothing_window=experiment.smoothing_window,
        normalize=experiment.normalize,
        detrend=experiment.detrend,
        fill_missing=experiment.fill_missing,
        remove_outliers=experiment.remove_outliers,
    )


def execute_experiment(experiment: Experiment) -> Experiment:
    experiment.status = Experiment.Status.RUNNING
    experiment.started_at = timezone.now()
    experiment.error_message = ''
    experiment.save(update_fields=['status', 'started_at', 'error_message', 'updated_at'])
    try:
        result = run_experiment(experiment.dataset, build_config(experiment))
        experiment.results = result
        experiment.status = Experiment.Status.COMPLETED
        experiment.finished_at = timezone.now()
        experiment.save(update_fields=['results', 'status', 'finished_at', 'updated_at'])
        if hasattr(experiment, 'report') and experiment.report.pdf_file:
            experiment.report.pdf_file.delete(save=False)
    except Exception as exc:
        experiment.status = Experiment.Status.FAILED
        experiment.error_message = str(exc)
        experiment.finished_at = timezone.now()
        experiment.save(update_fields=['status', 'error_message', 'finished_at', 'updated_at'])
    return experiment
