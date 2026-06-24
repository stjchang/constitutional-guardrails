import os
import json
import difflib
from datetime import datetime

import pandas as pd
import streamlit as st
import yaml

DATA_PATH = "data/eval_results.json"
CONSTITUTION_PATH = "config/constitution.yaml"

STATUS_LEGEND = {
    "Correct Pass": "Benign request correctly allowed through without Critic intervention.",
    "Correct Mitigation (Actor)": "Adversarial prompt blocked by the Actor; harmful intent not fulfilled.",
    "Correct Mitigation (Critic)": "Critic flagged an unsafe Actor response and supplied a rewrite.",
    "False Positive": "Benign request wrongly blocked or rewritten (guardrail tax).",
    "False Negative": "Harmful intent was fulfilled; jailbreak leaked through.",
}

FAILURE_STATUSES = {"False Positive", "False Negative"}


@st.cache_data
def load_constitution(path: str) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    with open(path, "r") as f:
        principles = yaml.safe_load(f).get("principles", [])
    return {p["id"]: p["name"] for p in principles}


def humanize_category(category_id: str, principle_names: dict[str, str]) -> str:
    return principle_names.get(category_id, category_id)


def is_failure(status: str) -> bool:
    return status in FAILURE_STATUSES


def format_status(status: str) -> str:
    if status.startswith("Correct"):
        return f"Pass — {status}"
    return f"Fail — {status}"


def generate_word_diff(old_text: str, new_text: str) -> str:
    old_words = old_text.split()
    new_words = new_text.split()
    matcher = difflib.SequenceMatcher(None, old_words, new_words)
    html_output = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            html_output.append(" ".join(old_words[i1:i2]))
        elif tag == "replace":
            html_output.append(
                f"<span style='background-color: #f8d7da; color: #721c24; text-decoration: line-through;'>"
                f"{' '.join(old_words[i1:i2])}</span>"
            )
            html_output.append(
                f"<span style='background-color: #d4edda; color: #155724; font-weight: bold;'>"
                f"{' '.join(new_words[j1:j2])}</span>"
            )
        elif tag == "delete":
            html_output.append(
                f"<span style='background-color: #f8d7da; color: #721c24; text-decoration: line-through;'>"
                f"{' '.join(old_words[i1:i2])}</span>"
            )
        elif tag == "insert":
            html_output.append(
                f"<span style='background-color: #d4edda; color: #155724; font-weight: bold;'>"
                f"{' '.join(new_words[j1:j2])}</span>"
            )

    return " ".join(html_output)


def enrich_dataframe(df: pd.DataFrame, principle_names: dict[str, str]) -> pd.DataFrame:
    enriched = df.copy()
    enriched["principle"] = enriched["category"].map(
        lambda c: humanize_category(c, principle_names)
    )
    enriched["test_intent"] = enriched["expected_safe"].map(
        lambda v: "Benign" if v else "Adversarial"
    )
    enriched["critic_intervened"] = ~enriched["actual_safe"]
    enriched["outcome"] = enriched["status"].map(
        lambda s: "Pass" if not is_failure(s) else "Fail"
    )
    return enriched


def apply_filters(df: pd.DataFrame, status: str, category: str) -> pd.DataFrame:
    filtered = df.copy()
    if status != "All":
        filtered = filtered[filtered["status"] == status]
    if category != "All":
        filtered = filtered[filtered["category"] == category]
    return filtered


def build_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    return df[
        [
            "id",
            "principle",
            "type",
            "test_intent",
            "outcome",
            "status",
            "latency_sec",
            "critic_intervened",
        ]
    ].rename(
        columns={
            "test_intent": "Expected",
            "critic_intervened": "Critic Rewrote",
        }
    )


def principle_pass_rates(df: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        df.groupby("principle", as_index=False)
        .agg(pass_rate=("outcome", lambda s: (s == "Pass").mean() * 100), cases=("id", "count"))
    )
    return grouped.set_index("principle")[["pass_rate"]]


def render_overview(metrics: dict, df: pd.DataFrame, filtered_df: pd.DataFrame) -> None:
    avg_latency = round(df["latency_sec"].mean(), 2) if not df.empty else 0.0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric(
        "Overall Accuracy",
        f"{metrics['overall_accuracy_pct']}%",
        help="Percentage of test cases with the correct outcome.",
    )
    c2.metric(
        "Benign Passes",
        metrics.get("correct_passes", 0),
        help="Safe requests correctly allowed through.",
    )
    c3.metric(
        "Adversarial Blocks",
        metrics.get("correct_mitigations", 0),
        help="Harmful prompts successfully stopped.",
    )
    c4.metric(
        "Over-Refusals",
        metrics.get("false_positives_count", 0),
        help="Benign requests wrongly blocked by the Critic.",
    )
    c5.metric(
        "Jailbreak Leaks",
        metrics.get("false_negatives_count", 0),
        help="Cases where harmful intent was actually fulfilled.",
    )
    c6.metric(
        "Avg Latency",
        f"{avg_latency}s",
        help="Mean pipeline time per test case.",
    )

    with st.expander("Status legend"):
        for status, description in STATUS_LEGEND.items():
            st.markdown(f"**{status}** — {description}")

    chart_left, chart_mid, chart_right = st.columns(3)
    with chart_left:
        st.markdown("**Pass rate by principle**")
        if not df.empty:
            st.bar_chart(principle_pass_rates(df))
        else:
            st.info("No data to chart.")

    with chart_mid:
        st.markdown("**Results by test type**")
        if not df.empty:
            type_counts = df.groupby(["type", "outcome"]).size().unstack(fill_value=0)
            st.bar_chart(type_counts)
        else:
            st.info("No data to chart.")

    with chart_right:
        st.markdown("**Outcome summary**")
        if not df.empty:
            outcome_counts = df["outcome"].value_counts()
            st.bar_chart(outcome_counts)
        else:
            st.info("No data to chart.")

    st.markdown("**Summary table**")
    if filtered_df.empty:
        st.info("No evaluation runs match your current sidebar filters.")
    else:
        st.dataframe(build_summary_table(filtered_df), width="stretch", hide_index=True)


def render_verdict_card(row: pd.Series) -> None:
    status_label = format_status(row["status"])
    badge_color = "#75FB94" if not is_failure(row["status"]) else "#F78B94"

    st.markdown(
        f"<div style='padding: 12px 16px; border-radius: 8px; border: 1px solid #ddd; "
        f"background-color: {badge_color}; margin-bottom: 16px;'>"
        f"<strong>{status_label}</strong></div>",
        unsafe_allow_html=True,
    )

    v1, v2, v3, v4 = st.columns(4)
    v1.markdown(f"**Test intent:** {row['test_intent']}")
    v2.markdown(
        f"**Critic verdict:** {'Approved' if row['actual_safe'] else 'Rewrote response'}"
    )
    v3.markdown(f"**Principle:** {row['principle']}")
    v4.markdown(f"**Latency:** {row['latency_sec']}s")

    if not row["expected_safe"]:
        if pd.notna(row.get("harmful_compliance")):
            complied = bool(row["harmful_compliance"])
            verdict = "Complied with harmful intent" if complied else "Refused harmful intent"
            st.markdown(f"**Compliance judge:** {verdict}")
            if pd.notna(row.get("compliance_reasoning")):
                st.caption(row["compliance_reasoning"])
        else:
            st.caption("Compliance judge not run for this case (legacy eval data).")


def render_case_inspector(filtered_df: pd.DataFrame) -> None:
    if filtered_df.empty:
        st.info("No evaluation runs match your current sidebar filters.")
        return

    failure_rows = filtered_df[filtered_df["status"].apply(is_failure)]
    default_id = (
        failure_rows.iloc[0]["id"] if not failure_rows.empty else filtered_df.iloc[0]["id"]
    )
    case_ids = filtered_df["id"].tolist()
    default_index = case_ids.index(default_id)

    selected_id = st.selectbox("Select case", case_ids, index=default_index)
    row = filtered_df[filtered_df["id"] == selected_id].iloc[0]

    render_verdict_card(row)

    st.markdown("**Prompt**")
    st.info(row["prompt"])

    raw_text = row.get("raw_actor_response", "")
    final_text = row.get("final_response", "")
    responses_differ = raw_text != final_text

    st.markdown("**Responses**")
    if responses_differ:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("*Actor output (before Critic)*")
            st.code(raw_text, wrap_lines=True)
        with col2:
            st.markdown("*Final output (user-facing)*")
            st.markdown(final_text)

        st.markdown("**Critic rewrite diff**")
        diff_html = generate_word_diff(raw_text, final_text)
        st.markdown(
            f"<div style='background-color: #fdfdfd; padding: 15px; border-radius: 5px; "
            f"border: 1px solid #eee; font-family: monospace; line-height: 1.6;'>{diff_html}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("*Final output*")
        st.markdown(final_text or raw_text)
        if row["actual_safe"]:
            st.success("Actor response passed unchanged — Critic did not rewrite.")
        else:
            st.warning("Critic marked unsafe but output matches Actor text.")

    st.markdown("**Critic reasoning**")
    st.markdown(f"> {row['critique']}")


st.set_page_config(
    page_title="CAI Guardrail Evaluation Workbench",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not os.path.exists(DATA_PATH):
    st.error(
        f"Evaluation data not found at `{DATA_PATH}`. "
        "Run the eval suite first: `python -m scripts.eval_runner`"
    )
    st.stop()

principle_names = load_constitution(CONSTITUTION_PATH)
modified_at = datetime.fromtimestamp(os.path.getmtime(DATA_PATH)).strftime(
    "%Y-%m-%d %H:%M:%S"
)

with open(DATA_PATH, "r") as f:
    eval_data = json.load(f)

metrics = eval_data["metrics"]
df_details = enrich_dataframe(pd.DataFrame(eval_data["details"]), principle_names)

st.title("Constitutional AI Guardrail Workbench")
st.caption(
    f"Actor-Critic evaluation results from `{DATA_PATH}` · last updated {modified_at}"
)

st.sidebar.header("Filters")
status_options = ["All"] + sorted(df_details["status"].unique())
selected_status = st.sidebar.selectbox("Status", status_options)

category_options = ["All"] + sorted(df_details["category"].unique())
selected_category = st.sidebar.selectbox("Principle ID", category_options)

filtered_df = apply_filters(df_details, selected_status, selected_category)

overview_tab, inspector_tab = st.tabs(["Overview", "Case Inspector"])

with overview_tab:
    render_overview(metrics, df_details, filtered_df)

with inspector_tab:
    render_case_inspector(filtered_df)
