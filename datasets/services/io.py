from __future__ import annotations

from pathlib import Path
import io

import pandas as pd


TIME_CANDIDATES = [
    'time', 'timestamp', 'datetime', 'date_time', 'date', 'recorded_at', 'created_at', 'measurement_time',
    't', 'seconds', 'sec', 'sample_time'
]
VALUE_CANDIDATES = [
    'value', 'signal', 'amplitude', 'measurement', 'reading', 'glucose', 'ecg', 'eeg', 'ppg', 'resp',
    'hr', 'heart_rate', 'spo2', 'temperature', 'pressure', 'sample', 'x'
]
LABEL_CANDIDATES = [
    'label', 'class', 'target', 'state', 'risk', 'status', 'diagnosis', 'group', 'condition', 'category', 'y'
]
SUBJECT_CANDIDATES = [
    'subject_id', 'subject', 'patient_id', 'patient', 'series_id', 'series', 'record_id', 'case_id', 'id',
    'participant', 'person_id'
]


def _clean_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    cleaned = cleaned.dropna(axis=1, how='all')
    cleaned = cleaned.dropna(axis=0, how='all')
    return cleaned.reset_index(drop=True)


def _read_csv_with_fallback(source) -> pd.DataFrame:
    errors: list[Exception] = []
    for encoding in ('utf-8-sig', 'utf-8', 'cp1251', 'latin1'):
        for sep in (None, ',', ';', '\t'):
            try:
                if hasattr(source, 'seek'):
                    source.seek(0)
                df = pd.read_csv(source, encoding=encoding, sep=sep, engine='python')
                if df.shape[1] == 1 and sep is None:
                    continue
                return _clean_dataframe_columns(df)
            except Exception as exc:  # noqa: PERF203
                errors.append(exc)
                continue
    raise ValueError(f'Не вдалося прочитати CSV-файл. Остання помилка: {errors[-1] if errors else "невідома"}')


def read_dataset_dataframe(file_path: str | Path) -> pd.DataFrame:
    file_path = Path(file_path)
    suffix = file_path.suffix.lower()
    if suffix == '.csv':
        return _read_csv_with_fallback(file_path)
    if suffix in {'.xlsx', '.xls'}:
        return _clean_dataframe_columns(pd.read_excel(file_path))
    raise ValueError('Непідтримуваний формат файлу.')


def read_uploaded_dataframe(uploaded_file) -> pd.DataFrame:
    name = uploaded_file.name.lower()
    uploaded_file.seek(0)
    buffer = io.BytesIO(uploaded_file.read())
    buffer.seek(0)
    try:
        if name.endswith('.csv'):
            return _read_csv_with_fallback(buffer)
        if name.endswith('.xlsx') or name.endswith('.xls'):
            return _clean_dataframe_columns(pd.read_excel(buffer))
        raise ValueError('Непідтримуваний формат файлу.')
    finally:
        uploaded_file.seek(0)


def _normalize_columns(df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for column in df.columns:
        normalized = str(column).strip().lower().replace(' ', '_').replace('-', '_')
        mapping[normalized] = str(column)
    return mapping


def _pick_by_candidates(normalized_map: dict[str, str], candidates: list[str]) -> str:
    for candidate in candidates:
        if candidate in normalized_map:
            return normalized_map[candidate]
    return ''


def _coerce_numeric_ratio(series: pd.Series) -> float:
    if pd.api.types.is_numeric_dtype(series):
        return float(series.notna().mean())
    converted = pd.to_numeric(series.astype(str).str.replace(',', '.', regex=False), errors='coerce')
    return float(converted.notna().mean())


def _infer_time_column(df: pd.DataFrame, normalized_map: dict[str, str]) -> str:
    direct = _pick_by_candidates(normalized_map, TIME_CANDIDATES)
    if direct:
        return direct
    for column in df.columns:
        series = df[column]
        try:
            parsed = pd.to_datetime(series, errors='coerce')
            if parsed.notna().mean() >= 0.8 and _coerce_numeric_ratio(series) < 0.95:
                return str(column)
        except Exception:
            continue
    return ''


def _infer_value_column(df: pd.DataFrame, normalized_map: dict[str, str]) -> str:
    direct = _pick_by_candidates(normalized_map, VALUE_CANDIDATES)
    if direct:
        return direct
    best_column = ''
    best_score = -1.0
    for column in df.columns:
        ratio = _coerce_numeric_ratio(df[column])
        unique_count = df[column].nunique(dropna=True)
        score = ratio * 1000 + min(unique_count, 500)
        if ratio >= 0.75 and score > best_score:
            best_column = str(column)
            best_score = score
    return best_column


def _infer_label_column(df: pd.DataFrame, normalized_map: dict[str, str], excluded: set[str]) -> str:
    direct = _pick_by_candidates(normalized_map, LABEL_CANDIDATES)
    if direct and direct not in excluded:
        return direct
    candidates: list[tuple[int, str]] = []
    for column in df.columns:
        name = str(column)
        if name in excluded:
            continue
        unique_count = df[column].nunique(dropna=True)
        numeric_ratio = _coerce_numeric_ratio(df[column])
        if 2 <= unique_count <= min(20, max(2, len(df) // 4)) and numeric_ratio < 0.95:
            candidates.append((unique_count, name))
    if candidates:
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]
    return ''


def _infer_subject_column(df: pd.DataFrame, normalized_map: dict[str, str], excluded: set[str]) -> str:
    direct = _pick_by_candidates(normalized_map, SUBJECT_CANDIDATES)
    if direct and direct not in excluded:
        return direct
    for column in df.columns:
        name = str(column)
        if name in excluded:
            continue
        unique_count = df[column].nunique(dropna=True)
        if 2 <= unique_count <= max(3, len(df) // 2):
            return name
    return ''


def infer_columns_from_dataframe(df: pd.DataFrame) -> dict[str, str]:
    normalized_map = _normalize_columns(df)
    inferred: dict[str, str] = {}
    inferred['time_column'] = _infer_time_column(df, normalized_map)
    inferred['value_column'] = _infer_value_column(df, normalized_map)
    excluded = {value for value in inferred.values() if value}
    inferred['label_column'] = _infer_label_column(df, normalized_map, excluded)
    excluded = {value for value in inferred.values() if value}
    inferred['subject_column'] = _infer_subject_column(df, normalized_map, excluded)
    return inferred


def dataframe_preview(df: pd.DataFrame, rows: int = 10) -> list[dict]:
    preview = df.head(rows).copy()
    preview = preview.fillna('')
    return preview.to_dict(orient='records')


def summarize_dataframe(df: pd.DataFrame) -> dict:
    numeric = []
    for column in df.columns:
        if _coerce_numeric_ratio(df[column]) >= 0.75:
            numeric.append(str(column))
    return {
        'rows': int(df.shape[0]),
        'columns': int(df.shape[1]),
        'column_names': list(df.columns),
        'missing_values': int(df.isna().sum().sum()),
        'numeric_columns': numeric,
        'inferred_columns': infer_columns_from_dataframe(df),
    }
