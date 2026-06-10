from __future__ import annotations

import io
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from analytics.models import Experiment
from reports.models import ExperimentReport

FONT_REGULAR = 'DejaVuSans'
FONT_BOLD = 'DejaVuSans-Bold'
FONT_DIR = Path(__file__).resolve().parents[2] / 'assets' / 'fonts'


def _register_fonts() -> None:
    candidates = [
        (FONT_DIR / 'DejaVuSans.ttf', FONT_REGULAR),
        (FONT_DIR / 'DejaVuSans-Bold.ttf', FONT_BOLD),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'), FONT_REGULAR),
        (Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'), FONT_BOLD),
        (Path('C:/Windows/Fonts/DejaVuSans.ttf'), FONT_REGULAR),
        (Path('C:/Windows/Fonts/DejaVuSans-Bold.ttf'), FONT_BOLD),
        (Path('C:/Windows/Fonts/arial.ttf'), FONT_REGULAR),
        (Path('C:/Windows/Fonts/arialbd.ttf'), FONT_BOLD),
    ]

    missing = {FONT_REGULAR, FONT_BOLD} - set(pdfmetrics.getRegisteredFontNames())
    for path, name in candidates:
        if name not in missing:
            continue
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
            missing.discard(name)
    if FONT_REGULAR in pdfmetrics.getRegisteredFontNames() and FONT_BOLD in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFontFamily(
            FONT_REGULAR,
            normal=FONT_REGULAR,
            bold=FONT_BOLD,
            italic=FONT_REGULAR,
            boldItalic=FONT_BOLD,
        )


def _styles():
    _register_fonts()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='BodyUA',
        parent=styles['BodyText'],
        fontName=FONT_REGULAR,
        fontSize=10,
        leading=14,
        spaceAfter=6,
        textColor=colors.HexColor('#1f2937'),
    ))
    styles.add(ParagraphStyle(
        name='TitleUA',
        parent=styles['Title'],
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#173b8b'),
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name='HeadingUA',
        parent=styles['Heading2'],
        fontName=FONT_BOLD,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=8,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name='SmallUA',
        parent=styles['BodyText'],
        fontName=FONT_REGULAR,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#64748b'),
    ))
    return styles


def _safe_text(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, float):
        return f'{value:.4f}'
    return str(value)


def _paragraph(text: Any, style):
    value = escape(_safe_text(text)).replace('\n', '<br/>')
    value = value.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
    return Paragraph(value, style)


def _card_table(rows: list[list[Any]], col_widths: list[float]) -> Table:
    table = Table(rows, colWidths=col_widths, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#dbe2ea')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#eef2f7')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return table


def _data_table(data: list[list[Any]], col_widths: list[float], header_rows: int = 1) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=header_rows, hAlign='LEFT')
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, max(0, header_rows - 1)), colors.HexColor('#eef4ff')),
        ('TEXTCOLOR', (0, 0), (-1, max(0, header_rows - 1)), colors.HexColor('#173b8b')),
        ('FONTNAME', (0, 0), (-1, max(0, header_rows - 1)), FONT_BOLD),
        ('FONTNAME', (0, header_rows), (-1, -1), FONT_REGULAR),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dbe2ea')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
    ]))
    return table


def _sanitize_preview(experiment: Experiment) -> tuple[list[str], list[dict[str, Any]]]:
    columns = experiment.results.get('feature_columns', [])[:6]
    rows = []
    for item in experiment.results.get('feature_preview', [])[:8]:
        rows.append({key: item.get(key, '') for key in columns})
    return columns, rows


def _summary_cards(experiment: Experiment, styles) -> Table:
    summary = experiment.results.get('dataset_summary', {})
    rows = [[
        _paragraph(f'<b>Рядків після оброблення</b><br/>{summary.get("row_count", "н/д")}', styles['BodyUA']),
        _paragraph(f'<b>Сегментів</b><br/>{summary.get("segment_count", "н/д")}', styles['BodyUA']),
        _paragraph(f'<b>Ознак</b><br/>{summary.get("feature_count", "н/д")}', styles['BodyUA']),
    ]]
    return _card_table(rows, [55 * mm, 55 * mm, 55 * mm])


def _metadata_table(experiment: Experiment, styles) -> Table:
    data = [
        [_paragraph('<b>Набір даних</b>', styles['BodyUA']), _paragraph(experiment.dataset.title, styles['BodyUA'])],
        [_paragraph('<b>Режим аналізу</b>', styles['BodyUA']), _paragraph(experiment.get_mode_display(), styles['BodyUA'])],
        [_paragraph('<b>Набір ознак</b>', styles['BodyUA']), _paragraph(experiment.get_feature_set_display(), styles['BodyUA'])],
        [_paragraph('<b>Алгоритм</b>', styles['BodyUA']), _paragraph(experiment.model_name, styles['BodyUA'])],
        [_paragraph('<b>Розмір вікна</b>', styles['BodyUA']), _paragraph(str(experiment.window_size), styles['BodyUA'])],
        [_paragraph('<b>Крок сегментації</b>', styles['BodyUA']), _paragraph(str(experiment.step_size), styles['BodyUA'])],
        [_paragraph('<b>Дата формування звіту</b>', styles['BodyUA']), _paragraph(timezone.localtime().strftime('%d.%m.%Y %H:%M'), styles['BodyUA'])],
    ]
    return _data_table(data, [58 * mm, 110 * mm], header_rows=0)



def _fractal_summary_section(experiment: Experiment, styles, story: list[Any]) -> None:
    summary = experiment.results.get('fractal_summary') or {}
    if not summary:
        return
    story.append(_paragraph('Фрактальні характеристики', styles['HeadingUA']))
    data = [['Ознака', 'Середнє', 'Std', 'Min', 'Max']]
    for key, values in summary.items():
        data.append([
            _safe_text(key),
            _safe_text(values.get('mean', 'н/д')),
            _safe_text(values.get('std', 'н/д')),
            _safe_text(values.get('min', 'н/д')),
            _safe_text(values.get('max', 'н/д')),
        ])
    story.append(_data_table(data, [58 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm]))
    story.append(Spacer(1, 8))

def _comparison_section(experiment: Experiment, styles, story: list[Any]) -> None:
    comparison = experiment.results.get('comparison') or {}
    if not comparison:
        return
    story.append(_paragraph('Порівняння наборів ознак', styles['HeadingUA']))
    data = [['Набір ознак', 'Accuracy', 'Precision', 'Recall', 'F1', 'Стан']]
    labels = {
        'standard': 'Класичні',
        'fractal': 'Фрактальні',
        'combined': 'Комбіновані',
    }
    for key, metrics in comparison.items():
        if metrics.get('error'):
            data.append([
                labels.get(key, key), 'н/д', 'н/д', 'н/д', 'н/д', _safe_text(metrics.get('error'))[:80]
            ])
        else:
            data.append([
                labels.get(key, key),
                _safe_text(metrics.get('accuracy', 'н/д')),
                _safe_text(metrics.get('precision_macro', 'н/д')),
                _safe_text(metrics.get('recall_macro', 'н/д')),
                _safe_text(metrics.get('f1_macro', 'н/д')),
                'виконано',
            ])
    story.append(_data_table(data, [36 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm, 38 * mm]))
    story.append(Spacer(1, 8))


def _classification_section(experiment: Experiment, styles, story: list[Any]) -> None:
    analysis = experiment.results.get('analysis') or {}
    if not analysis:
        return
    story.append(_paragraph('Основні метрики класифікації', styles['HeadingUA']))
    metrics_data = [['Accuracy', 'Precision', 'Recall', 'F1', 'ROC-AUC']]
    metrics_data.append([
        _safe_text(analysis.get('accuracy', 'н/д')),
        _safe_text(analysis.get('precision_macro', 'н/д')),
        _safe_text(analysis.get('recall_macro', 'н/д')),
        _safe_text(analysis.get('f1_macro', 'н/д')),
        _safe_text(analysis.get('roc_auc', 'н/д')),
    ])
    story.append(_data_table(metrics_data, [34 * mm, 34 * mm, 34 * mm, 34 * mm, 34 * mm]))
    story.append(Spacer(1, 8))

    top_features = analysis.get('top_features') or []
    if top_features:
        story.append(_paragraph('Найважливіші ознаки', styles['HeadingUA']))
        data = [['Ознака', 'Важливість']]
        for item in top_features[:10]:
            data.append([_safe_text(item.get('feature', '')), _safe_text(item.get('importance', ''))])
        story.append(_data_table(data, [120 * mm, 50 * mm]))
        story.append(Spacer(1, 8))

    cm = analysis.get('confusion_matrix') or []
    classes = analysis.get('classes') or []
    if cm and classes:
        story.append(_paragraph('Матриця помилок', styles['HeadingUA']))
        cm_data = [['Факт / прогноз'] + list(classes)]
        for idx, row in enumerate(cm):
            cm_data.append([classes[idx]] + [ _safe_text(value) for value in row ])
        story.append(_data_table(cm_data, [40 * mm] + [min(30, 138 / max(1, len(classes))) * mm] * len(classes)))
        story.append(Spacer(1, 8))


def _clustering_or_anomaly_section(experiment: Experiment, styles, story: list[Any]) -> None:
    analysis = experiment.results.get('analysis') or {}
    if not analysis:
        return
    if experiment.mode == Experiment.Mode.CLUSTERING:
        story.append(_paragraph('Показники кластеризації', styles['HeadingUA']))
        data = [['Кількість кластерів', 'Silhouette score', 'Davies-Bouldin', 'Кількість сегментів']]
        data.append([
            _safe_text(analysis.get('cluster_count', 'н/д')),
            _safe_text(analysis.get('silhouette_score', 'н/д')),
            _safe_text(analysis.get('davies_bouldin_score', 'н/д')),
            _safe_text(analysis.get('sample_count', 'н/д')),
        ])
        story.append(_data_table(data, [42 * mm, 42 * mm, 42 * mm, 42 * mm]))
    else:
        story.append(_paragraph('Показники виявлення аномалій', styles['HeadingUA']))
        data = [['Аномальні сегменти', 'Частка аномалій', 'Кількість сегментів']]
        ratio = analysis.get('anomaly_ratio')
        ratio_text = f'{ratio * 100:.1f}%' if isinstance(ratio, (int, float)) else 'н/д'
        data.append([
            _safe_text(analysis.get('anomaly_count', 'н/д')),
            ratio_text,
            _safe_text(analysis.get('sample_count', 'н/д')),
        ])
        story.append(_data_table(data, [56 * mm, 56 * mm, 56 * mm]))
    story.append(Spacer(1, 8))


def _interpretation_section(experiment: Experiment, styles, story: list[Any]) -> None:
    interpretation = experiment.results.get('interpretation') or []
    if not interpretation:
        return
    story.append(_paragraph('Аналітичний висновок', styles['HeadingUA']))
    items = [ListItem(_paragraph(text, styles['BodyUA'])) for text in interpretation]
    story.append(ListFlowable(items, bulletType='bullet', start='circle', bulletFontName=FONT_REGULAR))
    story.append(Spacer(1, 8))


def _preview_section(experiment: Experiment, styles, story: list[Any]) -> None:
    columns, rows = _sanitize_preview(experiment)
    if not columns or not rows:
        return
    story.append(_paragraph('Фрагмент матриці ознак', styles['HeadingUA']))
    data = [columns]
    for row in rows:
        data.append([_safe_text(row.get(col, '')) for col in columns])
    total_width = 178 * mm
    col_widths = [total_width / len(columns)] * len(columns)
    story.append(_data_table(data, col_widths))


def generate_report(experiment: Experiment) -> ExperimentReport:
    styles = _styles()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=experiment.title,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
    )
    story: list[Any] = []

    story.append(_paragraph('Звіт експерименту з фрактального аналізу медичних часових рядів', styles['TitleUA']))
    story.append(_paragraph(experiment.title, styles['HeadingUA']))
    story.append(_paragraph(
        'Документ містить структуроване зведення результатів без вставлення сирого JSON або HTML-фрагментів. '
        'Звіт придатний для демонстрації під час захисту дипломної роботи та подальшого включення в додатки.',
        styles['BodyUA'],
    ))
    story.append(Spacer(1, 6))
    story.append(_metadata_table(experiment, styles))
    story.append(Spacer(1, 10))
    story.append(_summary_cards(experiment, styles))
    story.append(Spacer(1, 10))

    _interpretation_section(experiment, styles, story)
    _fractal_summary_section(experiment, styles, story)

    if experiment.results.get('comparison'):
        _comparison_section(experiment, styles, story)
    elif experiment.mode == Experiment.Mode.CLASSIFICATION:
        _classification_section(experiment, styles, story)
    else:
        _clustering_or_anomaly_section(experiment, styles, story)

    _preview_section(experiment, styles, story)

    doc.build(story)

    report, _ = ExperimentReport.objects.get_or_create(experiment=experiment)
    if report.pdf_file:
        report.pdf_file.delete(save=False)
    filename = f'report_experiment_{experiment.pk}.pdf'
    report.pdf_file.save(filename, ContentFile(buffer.getvalue()), save=True)
    return report
