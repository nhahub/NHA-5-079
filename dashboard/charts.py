"""Editorial Plotly chart builders for the MOI Criminal Releases Dashboard."""

from __future__ import annotations

import math
from typing import Callable

import pandas as pd
import plotly.graph_objects as go

from dashboard.labels import PALETTE, fmt_egp

_FONT_STACK = "IBM Plex Sans Arabic, Plus Jakarta Sans, -apple-system, BlinkMacSystemFont, sans-serif"


def _empty_figure(message: str, height: int = 320) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(family=_FONT_STACK, size=14, color=PALETTE["muted_ink"]),
    )
    return apply_editorial_layout(fig, height=height)


def apply_editorial_layout(
    fig: go.Figure,
    height: int = 340,
    margin: dict | None = None,
) -> go.Figure:
    """Apply consistent Warm-Stone editorial styling and collision-free margins."""
    base_margin = dict(l=18, r=24, t=30, b=36)
    if margin:
        base_margin.update(margin)
    fig.update_layout(
        height=height,
        margin=base_margin,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=PALETTE["surface"],
        font=dict(family=_FONT_STACK, size=12, color=PALETTE["ink"]),
        hoverlabel=dict(
            bgcolor=PALETTE["ink"],
            bordercolor=PALETTE["ink"],
            font=dict(family=_FONT_STACK, size=12, color="#FFFFFF"),
        ),
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor=PALETTE["grid"],
        zeroline=False,
        linecolor=PALETTE["hairline"],
        automargin=True,
        ticklabelstandoff=8,
    )
    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        linecolor=PALETTE["hairline"],
        automargin=True,
        ticklabelstandoff=8,
    )
    return fig


def chart_monthly_trajectory(df: pd.DataFrame, lang: str = "ar") -> go.Figure:
    """Monthly release volume bars with a 3-month rolling average overlay."""
    if df.empty:
        return _empty_figure("لا توجد بيانات في النطاق المحدد" if lang == "ar" else "لا توجد بيانات · No data in slice")

    monthly = (
        df.groupby("year_month", as_index=False)["incident_key"]
        .count()
        .rename(columns={"incident_key": "releases"})
        .sort_values("year_month")
    )
    monthly["rolling_3m"] = monthly["releases"].rolling(3, min_periods=1).mean()

    bar_name = "البيانات الشهرية" if lang == "ar" else "Monthly Releases \u200e·\u200e البيانات الشهرية"
    line_name = "المتوسط المتحرك (3 أشهر)" if lang == "ar" else "Rolling Avg (3M) \u200e·\u200e المتوسط المتحرك"
    hover_bar = (
        "<b>%{x}</b><br>عدد البيانات: %{y:,}<extra></extra>"
        if lang == "ar"
        else "<b>%{x}</b><br>Releases: %{y:,}<extra></extra>"
    )
    hover_line = (
        "<b>%{x}</b><br>المتوسط (3 أشهر): %{y:.1f}<extra></extra>"
        if lang == "ar"
        else "<b>%{x}</b><br>3M Rolling Avg: %{y:.1f}<extra></extra>"
    )

    ym_list = monthly["year_month"].tolist()
    step = max(1, len(ym_list) // 13)
    tick_vals = ym_list[::step]
    if ym_list and tick_vals[-1] != ym_list[-1]:
        tick_vals.append(ym_list[-1])

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly["year_month"],
            y=monthly["releases"],
            name=bar_name,
            marker_color=PALETTE["navy"],
            opacity=0.88,
            hovertemplate=hover_bar,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=monthly["year_month"],
            y=monthly["rolling_3m"],
            name=line_name,
            mode="lines+markers",
            line=dict(color=PALETTE["ochre"], width=2.5),
            marker=dict(size=5, color=PALETTE["ochre"]),
            hovertemplate=hover_line,
        )
    )
    apply_editorial_layout(fig, height=340, margin=dict(t=46, b=48, l=20, r=20))
    fig.update_layout(
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            type="category",
            tickmode="array",
            tickvals=tick_vals,
            ticktext=tick_vals,
            tickangle=-25,
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor=PALETTE["grid"],
            title="عدد البيانات" if lang == "ar" else "Releases",
        ),
    )
    return fig


def chart_ranked_barh(
    agg_df: pd.DataFrame,
    y_col: str,
    x_col: str,
    color: str = PALETTE["navy"],
    value_fmt: str = "{:,.0f}",
    height: int = 340,
    highlight_map: dict[str, str] | None = None,
    formatter: Callable[[float], str] | None = None,
) -> go.Figure:
    """Horizontal ranked bar chart with direct outside value labels and headroom."""
    if agg_df.empty:
        return _empty_figure("لا توجد بيانات مطابقة" if color else "No matching records", height=height)

    work = agg_df.copy()
    work[x_col] = pd.to_numeric(work[x_col], errors="coerce").fillna(0)
    work = work.sort_values(x_col, ascending=True).reset_index(drop=True)

    colors = (
        [highlight_map.get(str(lbl), color) for lbl in work[y_col]]
        if highlight_map
        else color
    )
    labels = [
        formatter(v) if formatter is not None else value_fmt.format(v)
        for v in work[x_col]
    ]
    max_val = float(work[x_col].max()) if len(work) else 0.0
    headroom = max_val * 1.28 if max_val > 0 else 1.0

    fig = go.Figure(
        go.Bar(
            x=work[x_col],
            y=work[y_col],
            orientation="h",
            marker_color=colors,
            text=labels,
            textposition="outside",
            cliponaxis=False,
            textfont=dict(family=_FONT_STACK, size=11, color=PALETTE["ink"]),
            hovertemplate="<b>%{y}</b><br>%{text}<extra></extra>",
        )
    )
    apply_editorial_layout(fig, height=height, margin=dict(t=16, b=28, l=18, r=36))
    fig.update_xaxes(range=[0, headroom], showticklabels=False, showgrid=False)
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=work[y_col].tolist(),
        automargin=True,
        ticklabelstandoff=8,
    )
    return fig


def chart_operation_divergence(df: pd.DataFrame, lang: str = "ar") -> go.Figure:
    """Compare single-incident operations vs multi-case campaigns by event type."""
    if df.empty:
        return _empty_figure("لا توجد بيانات في النطاق المحدد" if lang == "ar" else "لا توجد بيانات · No data in slice")

    label_col = "event_label_ar" if lang == "ar" else "event_label_bi"
    work = df.copy()
    work["scope_bucket"] = work["is_campaign"].map({False: "single", True: "campaign"})
    piv = (
        work.groupby([label_col, "scope_bucket"])["incident_key"]
        .count()
        .unstack(fill_value=0)
    )
    for col in ("single", "campaign"):
        if col not in piv.columns:
            piv[col] = 0
    piv["total"] = piv["single"] + piv["campaign"]
    piv = piv.sort_values("total", ascending=True)

    single_lbl = "وقائع منفردة" if lang == "ar" else "وقائع منفردة · Single Incidents"
    camp_lbl = "حملات أمنية مجمعة" if lang == "ar" else "حملات أمنية · Campaigns"

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=piv.index.tolist(),
            x=piv["single"].tolist(),
            name=single_lbl,
            orientation="h",
            marker_color=PALETTE["navy"],
            hovertemplate=f"<b>%{{y}}</b><br>{single_lbl}: %{{x:,}}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            y=piv.index.tolist(),
            x=piv["campaign"].tolist(),
            name=camp_lbl,
            orientation="h",
            marker_color=PALETTE["teal"],
            hovertemplate=f"<b>%{{y}}</b><br>{camp_lbl}: %{{x:,}}<extra></extra>",
        )
    )
    apply_editorial_layout(fig, height=340, margin=dict(t=48, b=28, l=18, r=24))
    fig.update_layout(
        barmode="stack",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,
            xanchor="left",
            x=0,
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    fig.update_xaxes(showgrid=True, gridcolor=PALETTE["grid"], title="عدد البيانات" if lang == "ar" else "Releases")
    fig.update_yaxes(automargin=True, ticklabelstandoff=8)
    return fig


def chart_crime_event_heatmap(df: pd.DataFrame, lang: str = "ar") -> go.Figure:
    """Matrix of top crime categories against operational classification."""
    if df.empty:
        return _empty_figure("لا توجد بيانات في النطاق المحدد" if lang == "ar" else "لا توجد بيانات · No data in slice", height=400)

    crime_col = "crime_label_ar" if lang == "ar" else "crime_label_bi"
    event_col = "event_label_ar" if lang == "ar" else "event_label_bi"

    top_crimes = df[crime_col].value_counts().head(10).index.tolist()
    sub = df[df[crime_col].isin(top_crimes)]
    ct = pd.crosstab(sub[crime_col], sub[event_col])
    ct = ct.loc[ct.sum(axis=1).sort_values(ascending=True).index]

    text_matrix = [[str(int(v)) if v > 0 else "" for v in row] for row in ct.values]
    hover_tpl = (
        "الجريمة: %{y}<br>نوع العملية: %{x}<br>البيانات: %{z:,}<extra></extra>"
        if lang == "ar"
        else "Crime: %{y}<br>Operation: %{x}<br>Releases: %{z:,}<extra></extra>"
    )

    fig = go.Figure(
        go.Heatmap(
            z=ct.values,
            x=ct.columns.tolist(),
            y=ct.index.tolist(),
            text=text_matrix,
            texttemplate="%{text}",
            textfont=dict(family=_FONT_STACK, size=11),
            colorscale=[
                [0.0, "#F7F6F2"],
                [0.2, "#DDE7EE"],
                [0.6, "#2E6F95"],
                [1.0, "#1B365D"],
            ],
            showscale=False,
            hovertemplate=hover_tpl,
        )
    )
    apply_editorial_layout(fig, height=400, margin=dict(t=20, b=56, l=24, r=18))
    fig.update_xaxes(showgrid=False, tickangle=-18, automargin=True, ticklabelstandoff=8)
    fig.update_yaxes(showgrid=False, automargin=True, ticklabelstandoff=8)
    return fig


def chart_lethality_rate(df: pd.DataFrame, lang: str = "ar") -> go.Figure:
    """Fatality rate per 100 releases across operation types, isolating armed clashes."""
    if df.empty:
        return _empty_figure("لا توجد بيانات في النطاق المحدد" if lang == "ar" else "لا توجد بيانات · No data in slice", height=320)

    event_col = "event_label_ar" if lang == "ar" else "event_label_bi"
    grp = (
        df.groupby(["event_type", event_col], as_index=False)
        .agg(deaths=("death_count", "sum"), cases=("incident_key", "count"))
    )
    grp["deaths_per_100"] = (grp["deaths"] / grp["cases"].clip(lower=1)) * 100.0
    grp = grp.sort_values("deaths_per_100", ascending=True).reset_index(drop=True)

    colors = [
        PALETTE["crimson"] if et == "armed_clash" else PALETTE["stone"]
        for et in grp["event_type"]
    ]
    if lang == "ar":
        labels = [
            f" {r.deaths_per_100:.1f} لكل 100 ({int(r.deaths)}/{int(r.cases):,})"
            for r in grp.itertuples()
        ]
        hover_details = [
            f"{int(r.deaths):,} وفاة من أصل {int(r.cases):,} بيان"
            for r in grp.itertuples()
        ]
    else:
        labels = [
            f" {r.deaths_per_100:.1f}/100 ({int(r.deaths)}/{int(r.cases):,})"
            for r in grp.itertuples()
        ]
        hover_details = [
            f"{int(r.deaths):,} deaths / {int(r.cases):,} releases"
            for r in grp.itertuples()
        ]

    max_rate = float(grp["deaths_per_100"].max()) if len(grp) else 0.0
    headroom = max_rate * 1.75 if max_rate > 0 else 1.0

    fig = go.Figure(
        go.Bar(
            y=grp[event_col],
            x=grp["deaths_per_100"],
            orientation="h",
            marker_color=colors,
            text=labels,
            textposition="outside",
            cliponaxis=False,
            customdata=hover_details,
            textfont=dict(family=_FONT_STACK, size=11, color=PALETTE["ink"]),
            hovertemplate="<b>%{y}</b><br>%{x:.1f} / 100 · %{customdata}<extra></extra>",
        )
    )
    apply_editorial_layout(fig, height=320, margin=dict(t=16, b=28, l=18, r=24))
    fig.update_xaxes(range=[0, headroom], showgrid=False, showticklabels=False)
    fig.update_yaxes(
        categoryorder="array",
        categoryarray=grp[event_col].tolist(),
        automargin=True,
        ticklabelstandoff=8,
    )
    return fig


def chart_egypt_map(
    gov_summary: pd.DataFrame,
    metric_col: str,
    metric_label: str,
    color: str,
    value_fmt: str,
    height: int = 450,
    lang: str = "ar",
) -> go.Figure:
    """Proportional symbol map across mapped Egyptian governorates."""
    if gov_summary.empty:
        return _empty_figure("لا توجد محافظات مطابقة على الخريطة" if lang == "ar" else "No mappable governorates in slice", height=height)

    work = gov_summary.copy()
    work[metric_col] = pd.to_numeric(work[metric_col], errors="coerce").fillna(0.0)
    work = work[work[metric_col] >= 0].reset_index(drop=True)
    max_val = float(work[metric_col].max()) if len(work) else 0.0

    sizes = [
        10.0 + 34.0 * math.sqrt(float(v) / max_val) if max_val > 0 else 12.0
        for v in work[metric_col]
    ]
    if metric_col == "financial":
        formatted_vals = [fmt_egp(v, lang=lang) for v in work[metric_col]]
    else:
        formatted_vals = [value_fmt.format(v) for v in work[metric_col]]

    customdata = list(
        zip(
            work["gov_en"].tolist(),
            work["governorate"].tolist(),
            formatted_vals,
            work["releases"].astype(int).tolist(),
            work["arrests"].astype(int).tolist(),
            work["deaths"].astype(int).tolist(),
        )
    )

    if lang == "ar":
        hover_tpl = (
            "<b>%{customdata[1]}</b><br>"
            f"{metric_label}: %{{customdata[2]}}<br>"
            "البيانات: %{customdata[3]:,}<br>"
            "الموقوفون: %{customdata[4]:,}<br>"
            "الوفيات: %{customdata[5]:,}<extra></extra>"
        )
    else:
        hover_tpl = (
            "<b>%{customdata[1]} · %{customdata[0]}</b><br>"
            f"{metric_label}: %{{customdata[2]}}<br>"
            "Releases: %{customdata[3]:,} · Arrests: %{customdata[4]:,} · Deaths: %{customdata[5]:,}<extra></extra>"
        )

    fig = go.Figure(
        go.Scattermap(
            lat=work["lat"].tolist(),
            lon=work["lon"].tolist(),
            mode="markers",
            marker=dict(
                size=sizes,
                color=color,
                opacity=0.82,
            ),
            customdata=customdata,
            hovertemplate=hover_tpl,
        )
    )
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family=_FONT_STACK, size=12, color=PALETTE["ink"]),
        map=dict(
            style="carto-positron",
            center=dict(lat=26.9, lon=30.8),
            zoom=5.15,
        ),
        hoverlabel=dict(
            bgcolor=PALETTE["ink"],
            bordercolor=PALETTE["ink"],
            font=dict(family=_FONT_STACK, size=12, color="#FFFFFF"),
        ),
    )
    return fig
