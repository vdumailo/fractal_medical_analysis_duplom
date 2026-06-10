from celery import shared_task
from .models import Experiment
from .services.runner import execute_experiment


@shared_task
def run_experiment_task(experiment_id: int) -> None:
    experiment = Experiment.objects.get(pk=experiment_id)
    execute_experiment(experiment)
