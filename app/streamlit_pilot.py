"""Optional Streamlit mock of the participant flow.

This is a convenience for a quick dry run when the FastAPI interface is not
available. It does **not** record data, track focus, or implement the adaptive
policy. Use the real participant interface for any pilot data.

Run from the repository root:
    streamlit run pilot/app/streamlit_pilot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilot.app import benchmark  # noqa: E402

st.set_page_config(page_title="Pilot mock", layout="centered")
st.title("Pilot interface mock")
st.caption("No data are saved. This mock does not implement the adaptive policy.")

tasks = benchmark.load_tasks()
tasks = tasks[:6]

if "mock_index" not in st.session_state:
    st.session_state.mock_index = 0
if "mock_phase" not in st.session_state:
    st.session_state.mock_phase = "initial"
if "mock_initial" not in st.session_state:
    st.session_state.mock_initial = None
if "mock_confidence" not in st.session_state:
    st.session_state.mock_confidence = 50

if not tasks:
    st.error("No tasks found.")
    st.stop()

index = st.session_state.mock_index
if index >= len(tasks):
    st.success("Mock complete. No data were saved.")
    if st.button("Restart"):
        st.session_state.mock_index = 0
        st.session_state.mock_phase = "initial"
        st.session_state.mock_initial = None
        st.session_state.mock_confidence = 50
        st.rerun()
    st.stop()

task = tasks[index]
public = benchmark.public_task(task)
st.progress(index / len(tasks), text=f"Task {index + 1} of {len(tasks)}")
st.subheader(public["title"])
st.write(public["prompt"])
st.code(public["code"], language="python", line_numbers=True)

if public["type"] == "select_impl":
    candidates = public.get("candidates", [])
    for candidate in candidates:
        st.markdown(f"**{candidate['id']}**")
        st.code(candidate["code"], language="python", line_numbers=True)

phase = st.session_state.mock_phase

if phase == "initial":
    st.markdown("### Your answer")
    if public["type"] == "identify_bug":
        has_bug = st.checkbox("There is a bug", value=True)
        line = st.number_input(
            "Line with the bug (1-based; ignored if no bug)",
            min_value=1,
            max_value=public["line_count"],
            value=1,
        )
        answer = {"has_bug": has_bug, "line": int(line) if has_bug else None}
    elif public["type"] == "check_spec":
        compliant = st.radio(
            "Does the implementation satisfy the specification?",
            [True, False],
            format_func=lambda value: "Yes" if value else "No",
        )
        answer = {"compliant": compliant}
    else:
        choice = st.radio(
            "Select the implementation that satisfies the specification",
            [candidate["id"] for candidate in public.get("candidates", [])],
        )
        answer = {"candidate": choice}

    confidence = st.slider(
        "How confident are you that your answer is correct?",
        min_value=0,
        max_value=100,
        value=st.session_state.mock_confidence,
        step=5,
    )
    if st.button("Submit initial answer", type="primary"):
        st.session_state.mock_initial = answer
        st.session_state.mock_confidence = confidence
        st.session_state.mock_phase = "recommendation"
        st.rerun()

elif phase == "recommendation":
    st.markdown("### Recommendation")
    recommendation = benchmark.public_recommendation(task)
    st.info(recommendation["text"])
    with st.expander("Verification evidence (mock: always available)"):
        for item in benchmark.public_evidence(task):
            st.markdown(f"**{item['title']}**")
            st.write(item["body"])
            if item.get("table"):
                st.dataframe(item["table"], use_container_width=True, hide_index=True)

    st.markdown("### Final answer")
    st.caption(f"Your initial answer: {st.session_state.mock_initial}")
    if public["type"] == "identify_bug":
        has_bug = st.checkbox("There is a bug", value=True, key="final_bug")
        line = st.number_input(
            "Line with the bug (1-based; ignored if no bug)",
            min_value=1,
            max_value=public["line_count"],
            value=1,
            key="final_line",
        )
        answer = {"has_bug": has_bug, "line": int(line) if has_bug else None}
    elif public["type"] == "check_spec":
        compliant = st.radio(
            "Does the implementation satisfy the specification?",
            [True, False],
            format_func=lambda value: "Yes" if value else "No",
            key="final_compliant",
        )
        answer = {"compliant": compliant}
    else:
        choice = st.radio(
            "Select the implementation that satisfies the specification",
            [candidate["id"] for candidate in public.get("candidates", [])],
            key="final_candidate",
        )
        answer = {"candidate": choice}

    if st.button("Submit final answer", type="primary"):
        st.session_state.mock_initial = answer
        st.session_state.mock_phase = "initial"
        st.session_state.mock_index += 1
        st.rerun()
