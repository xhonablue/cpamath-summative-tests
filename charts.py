"""Teacher-portal visualizations for Summative Test Sessions, in the spirit of
i-Ready's "Inform" teacher dashboard (score distributions, standards/domain
mastery, item-level difficulty, growth over time), plus a dedicated chart for
Xavier's representation-and-misconception research.

Colors follow the validated palette in the dataviz skill (references/palette.md):
categorical slot 1 = blue #2a78d6, slot 2 = orange #eb6834; sequential = the
blue 100->700 ramp; chart chrome (gridlines, muted axis ink, etc.) matches the
light-surface roles from that same palette. One axis per chart, no dual-axis.
"""
import plotly.graph_objects as go
import pandas as pd

# --- palette (light mode; see dataviz skill references/palette.md) ---
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

CAT_1_BLUE = "#2a78d6"     # series/variant A
CAT_2_ORANGE = "#eb6834"   # series/variant B
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"

SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

BASE_FONT = dict(family="system-ui, -apple-system, 'Segoe UI', sans-serif", color=INK_PRIMARY, size=13)


def _base_layout(title, height=380):
    return dict(
        title=dict(text=title, font=dict(size=15, color=INK_PRIMARY)),
        font=BASE_FONT,
        plot_bgcolor=SURFACE,
        paper_bgcolor=SURFACE,
        height=height,
        margin=dict(l=50, r=30, t=50, b=50),
        xaxis=dict(gridcolor=GRIDLINE, linecolor=BASELINE, tickfont=dict(color=INK_MUTED)),
        yaxis=dict(gridcolor=GRIDLINE, linecolor=BASELINE, tickfont=dict(color=INK_MUTED)),
    )


def score_distribution_chart(sessions_df: pd.DataFrame, day: int) -> go.Figure:
    """Histogram of score_percent for one day's test — mirrors an i-Ready
    lesson-quiz score spread."""
    day_scores = sessions_df[sessions_df["day"].astype(str) == str(day)]["score_percent"].astype(float)
    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=day_scores, marker_color=CAT_1_BLUE, marker_line_color=SURFACE, marker_line_width=2,
        xbins=dict(start=0, end=100, size=10),
    ))
    fig.add_vline(x=70, line_dash="dash", line_color=INK_MUTED,
                   annotation_text="mastery target (70%)", annotation_font_color=INK_SECONDARY)
    fig.update_layout(**_base_layout(f"Day {day} — Score Distribution"))
    fig.update_xaxes(title_text="Score (%)")
    fig.update_yaxes(title_text="Number of students")
    return fig


def growth_over_time_chart(sessions_df: pd.DataFrame) -> go.Figure:
    """One line: cohort average score (%) by day, 1-30 — the 'growth' view."""
    df = sessions_df.copy()
    df["day"] = df["day"].astype(int)
    df["score_percent"] = df["score_percent"].astype(float)
    avg_by_day = df.groupby("day")["score_percent"].mean().reset_index().sort_values("day")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=avg_by_day["day"], y=avg_by_day["score_percent"],
        mode="lines+markers", line=dict(color=CAT_1_BLUE, width=2),
        marker=dict(size=8, color=CAT_1_BLUE),
    ))
    fig.add_hline(y=70, line_dash="dash", line_color=INK_MUTED,
                   annotation_text="mastery target (70%)", annotation_font_color=INK_SECONDARY)
    fig.update_layout(**_base_layout("Cohort Average Score by Day"))
    fig.update_xaxes(title_text="Day", dtick=1)
    fig.update_yaxes(title_text="Average score (%)", range=[0, 100])
    return fig


def item_difficulty_chart(item_responses_df: pd.DataFrame, day: int) -> go.Figure:
    """Bar chart of % correct per item for one day, sorted ascending so the
    hardest items (most likely to need reteaching) are on the left."""
    df = item_responses_df[item_responses_df["day"].astype(str) == str(day)].copy()
    df["correct"] = df["correct"].astype(str).str.lower().isin(["true", "1"])
    pct = (df.groupby("item_id")["correct"].mean() * 100).reset_index()
    pct = pct.sort_values("correct")

    colors = [STATUS_CRITICAL if v < 50 else (CAT_1_BLUE if v < 70 else STATUS_GOOD) for v in pct["correct"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=pct["item_id"], y=pct["correct"], marker_color=colors,
        text=[f"{v:.0f}%" for v in pct["correct"]], textposition="outside",
        textfont=dict(color=INK_SECONDARY),
    ))
    fig.add_hline(y=70, line_dash="dash", line_color=INK_MUTED,
                   annotation_text="mastery target (70%)", annotation_font_color=INK_SECONDARY)
    fig.update_layout(**_base_layout(f"Day {day} — % Correct by Item (lowest first)"))
    fig.update_xaxes(title_text="Item")
    fig.update_yaxes(title_text="% correct", range=[0, 105])
    return fig


def standards_mastery_heatmap(item_responses_df: pd.DataFrame, item_meta: dict) -> go.Figure:
    """Heatmap: standard (row) x day (column) -> % correct. item_meta maps
    item_id -> {'standard': ..., 'day': ...} so items roll up to standards
    the same way i-Ready rolls skills up to domains."""
    df = item_responses_df.copy()
    df["correct"] = df["correct"].astype(str).str.lower().isin(["true", "1"])
    df["standard"] = df["item_id"].map(lambda i: item_meta.get(i, {}).get("standard", "Unknown"))

    pivot = df.pivot_table(index="standard", columns="day", values="correct", aggfunc="mean") * 100
    pivot = pivot.sort_index()

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values, x=[str(c) for c in pivot.columns], y=list(pivot.index),
        colorscale=[[i / (len(SEQ_BLUE) - 1), c] for i, c in enumerate(SEQ_BLUE)],
        zmin=0, zmax=100, colorbar=dict(title="% correct", tickfont=dict(color=INK_MUTED)),
        hovertemplate="Standard: %{y}<br>Day: %{x}<br>%% correct: %{z:.0f}%<extra></extra>",
    ))
    fig.update_layout(**_base_layout("Standards Mastery — % Correct by Day", height=max(320, 40 * len(pivot.index))))
    fig.update_xaxes(title_text="Day")
    fig.update_yaxes(title_text="Standard")
    return fig


def misconception_trend_chart(item_responses_df: pd.DataFrame, sessions_df: pd.DataFrame,
                               research_tag: str = "height_vs_slant_misconception",
                               misconception_choice: str = "B") -> go.Figure:
    """THE research chart: for the height-vs-slant misconception (tracked at
    d8_q4 -> d9_q3 -> d30_q2), plots the % of students who picked the 'used
    slant instead of height' distractor at each checkpoint, split by which
    representation-variant image their class saw. A falling line = the
    misconception is fading; comparing the two variants' slopes is the actual
    research signal for the representation study.

    NOTE ON INTERPRETING THIS CHART: with typical single-classroom sample
    sizes (a few dozen students per variant), differences of a few percentage
    points are within noise. Treat this as a formative/descriptive tool, not
    as statistical proof that one image caused a difference — especially
    important since this compares small, non-randomly-assigned groups.
    """
    items = item_responses_df[item_responses_df["research_tag"] == research_tag].copy()
    items["is_misconception"] = items["given_answer"].astype(str).str.upper() == misconception_choice

    merged = items.merge(sessions_df[["session_id", "representation_variant"]], on="session_id", how="left")

    # order checkpoints by the day they occurred on, not alphabetically by item_id
    day_by_item = merged.groupby("item_id")["day"].first().astype(int)
    order = day_by_item.sort_values().index.tolist()

    fig = go.Figure()
    colors = {}
    for i, variant in enumerate(sorted(merged["representation_variant"].dropna().unique())):
        color = CAT_1_BLUE if i == 0 else CAT_2_ORANGE
        colors[variant] = color
        sub = merged[merged["representation_variant"] == variant]
        rates = sub.groupby("item_id")["is_misconception"].mean().reindex(order) * 100
        fig.add_trace(go.Scatter(
            x=[f"Day {day_by_item[i]}" for i in order], y=rates.values,
            mode="lines+markers+text", name=str(variant),
            line=dict(color=color, width=2), marker=dict(size=9, color=color),
            text=[f"{v:.0f}%" if pd.notna(v) else "" for v in rates.values],
            textposition="top center", textfont=dict(color=color, size=12),
        ))

    fig.update_layout(**_base_layout(
        "Height-vs-Slant Misconception Rate Over Time, by Representation Variant"
    ))
    fig.update_xaxes(title_text="Checkpoint")
    fig.update_yaxes(title_text="% choosing the slant-height distractor", range=[0, 100])
    fig.update_layout(legend=dict(title="Image variant shown"))
    return fig
