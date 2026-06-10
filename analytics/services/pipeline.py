from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import plot
from scipy import signal, stats
from sklearn.cluster import AgglomerativeClustering, DBSCAN, KMeans
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    davies_bouldin_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    silhouette_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from datasets.models import Dataset
from datasets.services.io import read_dataset_dataframe
from .fractal import fractal_features


@dataclass
class ExperimentConfig:
    mode: str
    feature_set: str
    model_name: str
    n_clusters: int
    window_size: int
    step_size: int
    smoothing_window: int
    normalize: bool
    detrend: bool
    fill_missing: bool
    remove_outliers: bool


CLASSIFICATION_LABELS = {
    'standard': 'лише класичні ознаки',
    'fractal': 'лише фрактальні ознаки',
    'combined': 'комбінований набір ознак',
}

FRACTAL_COLUMNS = ['hurst_exponent', 'dfa_alpha', 'higuchi_fd', 'katz_fd', 'petrosian_fd']


def _series_to_numeric(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors='coerce')
    return pd.to_numeric(series.astype(str).str.replace(',', '.', regex=False), errors='coerce')


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except Exception:
        pass
    return fallback


def _group_columns(df: pd.DataFrame, dataset: Dataset) -> list[str]:
    return [dataset.subject_column] if dataset.subject_column and dataset.subject_column in df.columns else []


def _apply_per_series(df: pd.DataFrame, dataset: Dataset, func) -> pd.Series:
    value_column = dataset.value_column
    groups = _group_columns(df, dataset)
    if groups:
        return df.groupby(groups, sort=False, group_keys=False)[value_column].apply(func)
    return func(df[value_column])


def _clip_outliers(series: pd.Series) -> pd.Series:
    values = series.copy()
    if values.notna().sum() < 4:
        return values
    q1 = values.quantile(0.01)
    q99 = values.quantile(0.99)
    z = np.abs(stats.zscore(values, nan_policy='omit'))
    z = np.nan_to_num(z)
    clipped = values.clip(q1, q99)
    values.loc[z > 3] = clipped.loc[z > 3]
    return values


def _detrend_series(series: pd.Series) -> pd.Series:
    values = series.to_numpy(dtype=float)
    if len(values) <= 2:
        return series
    return pd.Series(signal.detrend(values), index=series.index)


def _normalize_series(series: pd.Series) -> pd.Series:
    values = series.astype(float)
    std = values.std(ddof=0)
    if not std or not math.isfinite(float(std)):
        return values * 0.0
    return (values - values.mean()) / std


def preprocess_dataframe(df: pd.DataFrame, dataset: Dataset, config: ExperimentConfig) -> pd.DataFrame:
    result = df.copy()
    if dataset.value_column not in result.columns:
        raise ValueError(f"У файлі відсутня колонка значень '{dataset.value_column}'.")

    result[dataset.value_column] = _series_to_numeric(result[dataset.value_column])

    sort_columns: list[str] = []
    if dataset.subject_column and dataset.subject_column in result.columns:
        sort_columns.append(dataset.subject_column)
    if dataset.time_column and dataset.time_column in result.columns:
        parsed_time = pd.to_datetime(result[dataset.time_column], errors='coerce')
        if parsed_time.notna().mean() >= 0.6:
            result[dataset.time_column] = parsed_time
        sort_columns.append(dataset.time_column)
    if sort_columns:
        result = result.sort_values(sort_columns, kind='mergesort').reset_index(drop=True)

    if config.fill_missing:
        result[dataset.value_column] = _apply_per_series(
            result,
            dataset,
            lambda s: s.interpolate(limit_direction='both').fillna(s.median()),
        )

    if config.remove_outliers:
        result[dataset.value_column] = _apply_per_series(result, dataset, _clip_outliers)

    if config.smoothing_window and config.smoothing_window > 1:
        result[dataset.value_column] = _apply_per_series(
            result,
            dataset,
            lambda s: s.rolling(config.smoothing_window, min_periods=1, center=True).mean(),
        )

    if config.detrend:
        result[dataset.value_column] = _apply_per_series(result, dataset, _detrend_series)

    if config.normalize:
        result[dataset.value_column] = _apply_per_series(result, dataset, _normalize_series)

    result = result.dropna(subset=[dataset.value_column]).reset_index(drop=True)
    if result.empty:
        raise ValueError('Після попереднього оброблення не залишилося валідних значень.')
    return result


def compute_standard_features(series: np.ndarray) -> dict[str, float]:
    arr = np.asarray(series, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        raise ValueError('Недостатньо значень для виділення ознак.')

    fft = np.abs(np.fft.rfft(arr))
    energy = _safe_float(np.sum(arr ** 2) / arr.size)

    if arr.size > 2 and np.std(arr[:-1]) > 0 and np.std(arr[1:]) > 0:
        autocorr = _safe_float(np.corrcoef(arr[:-1], arr[1:])[0, 1])
    else:
        autocorr = 0.0

    return {
        'mean': _safe_float(np.mean(arr)),
        'std': _safe_float(np.std(arr)),
        'min': _safe_float(np.min(arr)),
        'max': _safe_float(np.max(arr)),
        'median': _safe_float(np.median(arr)),
        'iqr': _safe_float(np.percentile(arr, 75) - np.percentile(arr, 25)),
        'skew': _safe_float(stats.skew(arr, nan_policy='omit')),
        'kurtosis': _safe_float(stats.kurtosis(arr, nan_policy='omit')),
        'energy': energy,
        'autocorr_lag1': autocorr,
        'spectral_peak': _safe_float(np.argmax(fft)),
        'spectral_energy': _safe_float(np.sum(fft ** 2) / max(len(fft), 1)),
    }


def segment_dataframe(df: pd.DataFrame, dataset: Dataset, config: ExperimentConfig) -> tuple[list[np.ndarray], list[Any], list[Any]]:
    window = max(8, int(config.window_size))
    step = max(1, int(config.step_size))

    if dataset.subject_column and dataset.subject_column in df.columns:
        groups = list(df.groupby(dataset.subject_column, sort=False))
    else:
        groups = [('series_0', df)]

    segments, segment_labels, segment_subjects = [], [], []
    for group_id, group_df in groups:
        values = group_df[dataset.value_column].to_numpy(dtype=float)
        labels = group_df[dataset.label_column].to_numpy() if dataset.label_column and dataset.label_column in group_df.columns else None
        if len(values) < window:
            continue
        for start in range(0, len(values) - window + 1, step):
            end = start + window
            segment = values[start:end]
            if not np.isfinite(segment).all():
                continue
            segments.append(segment)
            if labels is not None:
                label_slice = labels[start:end]
                mode = pd.Series(label_slice).mode(dropna=True)
                segment_labels.append(mode.iat[0] if not mode.empty else None)
            else:
                segment_labels.append(None)
            segment_subjects.append(group_id)

    if not segments:
        raise ValueError('Після сегментації не отримано жодного валідного вікна. Зменште розмір вікна або перевірте дані.')
    return segments, segment_labels, segment_subjects


def build_feature_matrix(df: pd.DataFrame, dataset: Dataset, config: ExperimentConfig) -> tuple[pd.DataFrame, list[Any], list[Any]]:
    segments, labels, segment_ids = segment_dataframe(df, dataset, config)
    rows = []
    for segment in segments:
        std = compute_standard_features(segment)
        frac = fractal_features(segment)
        if config.feature_set == 'standard':
            row = std
        elif config.feature_set == 'fractal':
            row = frac
        else:
            row = {**std, **frac}
        rows.append({key: _safe_float(value) for key, value in row.items()})
    features = pd.DataFrame(rows)
    features = features.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return features, labels, segment_ids


def compute_fractal_summary(features: pd.DataFrame) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for column in FRACTAL_COLUMNS:
        if column not in features.columns:
            continue
        values = pd.to_numeric(features[column], errors='coerce').dropna()
        if values.empty:
            continue
        summary[column] = {
            'mean': round(float(values.mean()), 4),
            'std': round(float(values.std(ddof=0)), 4),
            'min': round(float(values.min()), 4),
            'max': round(float(values.max()), 4),
        }
    return summary


def _test_size_for_labels(y: pd.Series) -> float:
    n_classes = max(2, y.nunique())
    min_test_count = max(n_classes, int(np.ceil(len(y) * 0.25)))
    return min(0.4, max(0.25, min_test_count / len(y)))


def _compare_feature_sets(df: pd.DataFrame, dataset: Dataset, config: ExperimentConfig) -> dict[str, Any]:
    variants = ['standard', 'fractal', 'combined']
    comparison: dict[str, Any] = {}
    original = config.feature_set
    successes = 0
    for variant in variants:
        try:
            config.feature_set = variant
            features, labels, _ = build_feature_matrix(df, dataset, config)
            comparison[variant] = classification_analysis(features, labels, config.model_name)
            successes += 1
        except Exception as exc:
            comparison[variant] = {'error': str(exc)}
    config.feature_set = original
    if successes == 0:
        errors = '; '.join(f'{key}: {value.get("error")}' for key, value in comparison.items())
        raise ValueError('Порівняння наборів ознак не виконано: ' + errors)
    return comparison


def classification_analysis(features: pd.DataFrame, labels: list[Any], model_name: str) -> dict[str, Any]:
    if not labels or all(label is None for label in labels):
        raise ValueError('Для класифікації потрібна колонка міток label.')

    y = pd.Series(labels).astype('string')
    valid_mask = y.notna() & (y.str.len() > 0)
    features = features.loc[valid_mask.to_numpy()].reset_index(drop=True)
    y = y.loc[valid_mask].astype(str).reset_index(drop=True)

    if y.nunique() < 2:
        raise ValueError('Для класифікації потрібно щонайменше два різні класи.')
    if len(y) < 8:
        raise ValueError('Для класифікації потрібно щонайменше 8 сегментів.')
    if y.value_counts().min() < 2:
        raise ValueError('Для класифікації кожен клас має бути представлений щонайменше двома сегментами.')

    test_size = _test_size_for_labels(y)
    if len(y) - int(np.ceil(test_size * len(y))) < y.nunique():
        raise ValueError('Недостатньо сегментів для коректного поділу на навчальну та тестову вибірки.')

    stratify = y
    X_train, X_test, y_train, y_test = train_test_split(
        features,
        y,
        test_size=test_size,
        random_state=42,
        stratify=stratify,
    )

    if model_name == 'logistic_regression':
        estimator = LogisticRegression(max_iter=1000, class_weight='balanced')
    elif model_name == 'svm':
        estimator = SVC(probability=True, class_weight='balanced')
    else:
        estimator = RandomForestClassifier(n_estimators=250, random_state=42, class_weight='balanced')

    pipeline = Pipeline([
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler()),
        ('model', estimator),
    ])
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test) if hasattr(pipeline, 'predict_proba') else None
    classes = sorted(y.unique().tolist())

    result: dict[str, Any] = {
        'accuracy': round(float(accuracy_score(y_test, y_pred)), 4),
        'precision_macro': round(float(precision_score(y_test, y_pred, average='macro', zero_division=0)), 4),
        'recall_macro': round(float(recall_score(y_test, y_pred, average='macro', zero_division=0)), 4),
        'f1_macro': round(float(f1_score(y_test, y_pred, average='macro', zero_division=0)), 4),
        'classification_report': classification_report(y_test, y_pred, labels=classes, output_dict=True, zero_division=0),
        'confusion_matrix': confusion_matrix(y_test, y_pred, labels=classes).tolist(),
        'classes': classes,
        'top_features': feature_importance(pipeline, features.columns.tolist()),
        'sample_count': int(len(features)),
        'train_count': int(len(X_train)),
        'test_count': int(len(X_test)),
    }
    if y_proba is not None and len(classes) == 2 and len(set(y_test)) == 2:
        try:
            result['roc_auc'] = round(float(roc_auc_score(y_test, y_proba[:, 1])), 4)
        except Exception:
            result['roc_auc'] = None
    return result


def feature_importance(pipeline: Pipeline, columns: list[str]) -> list[dict[str, Any]]:
    model = pipeline.named_steps['model']
    if hasattr(model, 'feature_importances_'):
        values = model.feature_importances_
    elif hasattr(model, 'coef_'):
        coef = np.abs(model.coef_)
        values = coef.mean(axis=0) if coef.ndim > 1 else coef
    else:
        return []
    ranking = sorted(zip(columns, values), key=lambda x: x[1], reverse=True)[:10]
    return [{'feature': name, 'importance': round(float(score), 4)} for name, score in ranking]


def clustering_analysis(features: pd.DataFrame, model_name: str, n_clusters: int) -> dict[str, Any]:
    if len(features) < 2:
        raise ValueError('Для кластеризації потрібно щонайменше 2 сегменти.')
    scaler = StandardScaler()
    X = scaler.fit_transform(features)

    used_clusters = int(max(2, n_clusters))
    used_clusters = min(used_clusters, max(2, len(features) - 1))

    if model_name == 'agglomerative':
        model = AgglomerativeClustering(n_clusters=used_clusters)
        labels = model.fit_predict(X)
    elif model_name == 'dbscan':
        model = DBSCAN(eps=0.9, min_samples=max(2, min(4, len(features) // 4 or 2)))
        labels = model.fit_predict(X)
    else:
        model = KMeans(n_clusters=used_clusters, random_state=42, n_init=10)
        labels = model.fit_predict(X)

    unique_labels = np.unique(labels)
    cluster_count = int(len(set(labels)) - (1 if -1 in labels else 0))
    metrics: dict[str, Any] = {
        'cluster_count': cluster_count,
        'used_n_clusters': used_clusters if model_name != 'dbscan' else None,
        'labels': labels.tolist(),
        'sample_count': int(len(labels)),
    }
    if 1 < len(unique_labels) < len(labels):
        try:
            metrics['silhouette_score'] = round(float(silhouette_score(X, labels)), 4)
        except Exception:
            metrics['silhouette_score'] = None
        try:
            metrics['davies_bouldin_score'] = round(float(davies_bouldin_score(X, labels)), 4)
        except Exception:
            metrics['davies_bouldin_score'] = None
    return metrics


def anomaly_analysis(features: pd.DataFrame) -> dict[str, Any]:
    if len(features) < 2:
        raise ValueError('Для виявлення аномалій потрібно щонайменше 2 сегменти.')
    scaler = StandardScaler()
    X = scaler.fit_transform(features)
    contamination = min(0.2, max(1.0 / len(features), 0.05))
    model = IsolationForest(contamination=contamination, random_state=42)
    preds = model.fit_predict(X)
    scores = model.score_samples(X)
    anomaly_count = int(np.sum(preds == -1))
    return {
        'anomaly_count': anomaly_count,
        'anomaly_ratio': round(float(anomaly_count / len(preds)), 4),
        'predictions': preds.tolist(),
        'scores': [round(float(x), 4) for x in scores],
        'sample_count': int(len(preds)),
        'contamination': round(float(contamination), 4),
    }


def line_chart_html(df: pd.DataFrame, dataset: Dataset) -> str:
    x = df[dataset.time_column] if dataset.time_column and dataset.time_column in df.columns else list(range(len(df)))
    fig = px.line(df, x=x, y=dataset.value_column, title='Підготовлений часовий ряд')
    fig.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='white', plot_bgcolor='white')
    return plot(fig, output_type='div', include_plotlyjs=False)


def feature_boxplot_html(features: pd.DataFrame) -> str:
    preview = features.iloc[:, : min(features.shape[1], 6)]
    fig = go.Figure()
    for column in preview.columns:
        fig.add_trace(go.Box(y=preview[column], name=column))
    fig.update_layout(title='Розподіли основних ознак', height=420, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='white', plot_bgcolor='white')
    return plot(fig, output_type='div', include_plotlyjs=False)


def fractal_profile_html(features: pd.DataFrame) -> str:
    columns = [column for column in FRACTAL_COLUMNS if column in features.columns]
    fig = go.Figure()
    if not columns:
        fig.add_annotation(text='Фрактальні ознаки не входили до вибраного набору.', x=0.5, y=0.5, showarrow=False)
    else:
        for column in columns:
            fig.add_trace(go.Scatter(y=features[column], mode='lines+markers', name=column))
    fig.update_layout(title='Фрактальні характеристики сегментів', height=420, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='white', plot_bgcolor='white')
    return plot(fig, output_type='div', include_plotlyjs=False)


def scatter_html(features: pd.DataFrame, labels: list[Any] | None = None, title: str = 'Проєкція ознак') -> str:
    cols = features.columns[:2].tolist()
    if len(cols) < 2:
        cols = [features.columns[0], features.columns[0]]
    frame = features.copy()
    if labels and len(labels) == len(frame) and any(label is not None for label in labels):
        frame['group'] = [str(label) for label in labels]
    else:
        frame['group'] = 'Сегмент'
    fig = px.scatter(frame, x=cols[0], y=cols[1], color='group', title=title)
    fig.update_layout(height=420, margin=dict(l=20, r=20, t=50, b=20), paper_bgcolor='white', plot_bgcolor='white')
    return plot(fig, output_type='div', include_plotlyjs=False)


def build_interpretation(mode: str, feature_set: str, result_payload: dict[str, Any]) -> list[str]:
    messages: list[str] = []
    fractal_summary = result_payload.get('fractal_summary') or {}
    if fractal_summary:
        hurst = fractal_summary.get('hurst_exponent', {}).get('mean')
        dfa = fractal_summary.get('dfa_alpha', {}).get('mean')
        if hurst is not None:
            messages.append(f"Середній показник Герста становить {hurst}, що використовується як ознака довготривалої залежності або антиперсистентності сигналу.")
        if dfa is not None:
            messages.append(f"Середня DFA-експонента дорівнює {dfa}, тому в експерименті враховано масштабну поведінку часового ряду.")

    if mode == 'classification' and 'comparison' in result_payload:
        items = [
            (variant, metrics.get('f1_macro', -1))
            for variant, metrics in result_payload['comparison'].items()
            if isinstance(metrics, dict) and not metrics.get('error')
        ]
        if items:
            best_variant, best_f1 = max(items, key=lambda item: item[1])
            messages.append(f"Найкращий результат за F1-мірoю показав варіант '{CLASSIFICATION_LABELS.get(best_variant, best_variant)}' зі значенням {best_f1:.4f}.")
            messages.append('Порівняння наборів ознак дозволяє оцінити внесок фрактальних дескрипторів у якість класифікації.')
    elif mode == 'classification' and 'analysis' in result_payload:
        analysis = result_payload['analysis']
        messages.append(f"Модель класифікації досягла accuracy {analysis.get('accuracy', 'н/д')} та F1 {analysis.get('f1_macro', 'н/д')}.")
        if analysis.get('top_features'):
            top = analysis['top_features'][0]['feature']
            messages.append(f"Найбільш інформативною ознакою стала '{top}'.")
    elif mode == 'clustering' and 'analysis' in result_payload:
        analysis = result_payload['analysis']
        messages.append(f"Алгоритм сформував {analysis.get('cluster_count', 'н/д')} кластерів на основі ознак сегментів.")
        if analysis.get('silhouette_score') is not None:
            messages.append(f"Silhouette score становить {analysis.get('silhouette_score')}, що характеризує щільність і відокремленість кластерів.")
    elif mode == 'anomaly' and 'analysis' in result_payload:
        analysis = result_payload['analysis']
        messages.append(f"Виявлено {analysis.get('anomaly_count', 'н/д')} аномальних сегментів, що становить {analysis.get('anomaly_ratio', 0) * 100:.1f}% від усіх сегментів.")
    if feature_set in CLASSIFICATION_LABELS and mode != 'classification':
        messages.append(f"Для аналізу використано {CLASSIFICATION_LABELS.get(feature_set, feature_set)}.")
    return messages


def _build_visual_labels(mode: str, true_labels: list[Any], analysis: dict[str, Any] | None) -> tuple[list[Any], str]:
    if mode == 'clustering' and analysis and analysis.get('labels'):
        return [f'Кластер {label}' if label != -1 else 'Шум' for label in analysis['labels']], 'Проєкція сегментів за кластерами'
    if mode == 'anomaly' and analysis and analysis.get('predictions'):
        return ['Аномалія' if value == -1 else 'Норма' for value in analysis['predictions']], 'Проєкція сегментів за аномальністю'
    return true_labels, 'Проєкція ознак за класами'


def _common_payload(processed_df: pd.DataFrame, dataset: Dataset, config: ExperimentConfig, features: pd.DataFrame, labels: list[Any], visual_labels: list[Any], scatter_title: str) -> dict[str, Any]:
    return {
        'dataset_summary': {
            'row_count': int(processed_df.shape[0]),
            'segment_count': int(features.shape[0]),
            'feature_count': int(features.shape[1]),
        },
        'charts': {
            'signal': line_chart_html(processed_df, dataset),
            'features': feature_boxplot_html(features),
            'fractal_profile': fractal_profile_html(features),
            'scatter': scatter_html(features, visual_labels, scatter_title),
        },
        'fractal_summary': compute_fractal_summary(features),
        'feature_preview': features.head(10).round(4).to_dict(orient='records'),
        'feature_columns': list(features.columns),
        'mode': config.mode,
        'feature_set': config.feature_set,
        'model_name': config.model_name,
    }


def run_experiment(dataset: Dataset, config: ExperimentConfig) -> dict[str, Any]:
    raw_df = read_dataset_dataframe(dataset.file.path)
    processed_df = preprocess_dataframe(raw_df, dataset, config)

    if config.mode == 'classification' and config.feature_set == 'compare':
        comparison = _compare_feature_sets(processed_df, dataset, config)
        combined_config = ExperimentConfig(
            mode=config.mode,
            feature_set='combined',
            model_name=config.model_name,
            n_clusters=config.n_clusters,
            window_size=config.window_size,
            step_size=config.step_size,
            smoothing_window=config.smoothing_window,
            normalize=config.normalize,
            detrend=config.detrend,
            fill_missing=config.fill_missing,
            remove_outliers=config.remove_outliers,
        )
        features, labels, _ = build_feature_matrix(processed_df, dataset, combined_config)
        payload = _common_payload(processed_df, dataset, config, features, labels, labels, 'Проєкція комбінованих ознак за класами')
        payload['comparison'] = comparison
        payload['interpretation'] = build_interpretation(config.mode, config.feature_set, payload)
        return payload

    features, labels, segment_ids = build_feature_matrix(processed_df, dataset, config)

    if config.mode == 'classification':
        analysis = classification_analysis(features, labels, config.model_name)
    elif config.mode == 'clustering':
        analysis = clustering_analysis(features, config.model_name, config.n_clusters)
    else:
        analysis = anomaly_analysis(features)

    visual_labels, scatter_title = _build_visual_labels(config.mode, labels, analysis)
    payload = _common_payload(processed_df, dataset, config, features, labels, visual_labels, scatter_title)
    payload['dataset_summary']['segment_ids'] = segment_ids[:20]
    payload['analysis'] = analysis
    payload['interpretation'] = build_interpretation(config.mode, config.feature_set, payload)
    return payload
