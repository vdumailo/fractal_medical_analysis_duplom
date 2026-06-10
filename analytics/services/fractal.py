from __future__ import annotations

import math
import numpy as np


def _safe_array(series) -> np.ndarray:
    arr = np.asarray(series, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 8:
        raise ValueError('Недостатньо даних для фрактального аналізу.')
    return arr


def hurst_exponent(series) -> float:
    x = _safe_array(series)
    max_lag = min(20, x.size // 2)
    lags = np.arange(2, max_lag)
    tau = [np.std(x[lag:] - x[:-lag]) for lag in lags]
    tau = np.asarray(tau)
    valid = tau > 0
    if valid.sum() < 2:
        return 0.5
    poly = np.polyfit(np.log(lags[valid]), np.log(tau[valid]), 1)
    return float(poly[0] * 2.0)


def dfa_alpha(series) -> float:
    x = _safe_array(series)
    x = x - np.mean(x)
    y = np.cumsum(x)
    scales = np.unique(np.floor(np.logspace(np.log10(4), np.log10(max(8, x.size // 4)), num=8)).astype(int))
    flucts = []
    valid_scales = []
    for scale in scales:
        if scale < 4:
            continue
        n_segments = x.size // scale
        if n_segments < 2:
            continue
        segments = y[: n_segments * scale].reshape(n_segments, scale)
        t = np.arange(scale)
        local_flucts = []
        for seg in segments:
            coeffs = np.polyfit(t, seg, 1)
            trend = np.polyval(coeffs, t)
            local_flucts.append(np.sqrt(np.mean((seg - trend) ** 2)))
        mean_fluct = np.mean(local_flucts)
        if mean_fluct > 0:
            flucts.append(mean_fluct)
            valid_scales.append(scale)
    if len(flucts) < 2:
        return 0.5
    poly = np.polyfit(np.log(valid_scales), np.log(flucts), 1)
    return float(poly[0])


def higuchi_fd(series, kmax: int = 8) -> float:
    x = _safe_array(series)
    n = len(x)
    lk = []
    k_values = []
    for k in range(1, min(kmax, n // 2)):
        lm = []
        for m in range(k):
            idx = np.arange(m, n, k)
            if len(idx) < 2:
                continue
            diffs = np.abs(np.diff(x[idx]))
            norm = (n - 1) / (((n - m - 1) // k) * k)
            lm.append(np.sum(diffs) * norm / k)
        if lm:
            lk.append(np.mean(lm))
            k_values.append(k)
    lk = np.asarray(lk)
    k_values = np.asarray(k_values)
    valid = lk > 0
    if valid.sum() < 2:
        return 1.0
    poly = np.polyfit(np.log(1.0 / k_values[valid]), np.log(lk[valid]), 1)
    return float(poly[0])


def katz_fd(series) -> float:
    x = _safe_array(series)
    n = len(x)
    ll = np.sum(np.sqrt(1 + np.diff(x) ** 2))
    d = np.max(np.sqrt((np.arange(n) - 0) ** 2 + (x - x[0]) ** 2))
    if d == 0 or ll == 0:
        return 1.0
    return float(np.log10(n) / (np.log10(d / ll) + np.log10(n)))


def petrosian_fd(series) -> float:
    x = _safe_array(series)
    diff = np.diff(x)
    sign_changes = np.sum(diff[1:] * diff[:-1] < 0)
    n = len(x)
    return float(np.log10(n) / (np.log10(n) + np.log10(n / (n + 0.4 * sign_changes))))


def fractal_features(series) -> dict[str, float]:
    return {
        'hurst_exponent': hurst_exponent(series),
        'dfa_alpha': dfa_alpha(series),
        'higuchi_fd': higuchi_fd(series),
        'katz_fd': katz_fd(series),
        'petrosian_fd': petrosian_fd(series),
    }
