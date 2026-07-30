from __future__ import annotations

import pandas as pd
import streamlit as st

from agent.graph import aidqx_graph
from services.dqx_service import (
    execute_rules,
    list_catalogs,
    list_schemas,
    list_tables,
)


st.set_page_config(page_title="AIDQX Agent", layout="wide")
st.title("AIDQX Agent")
st.caption("Profile data, review generated rules, execute DQ checks, and view results.")

if "profile_result" not in st.session_state:
    st.session_state.profile_result = None
if "rules" not in st.session_state:
    st.session_state.rules = []
if "execution_result" not in st.session_state:
    st.session_state.execution_result = None

with st.sidebar:
    st.header("Dataset Selection")

    catalogs = list_catalogs()
    catalog = st.selectbox("Catalog", catalogs)

    schemas = list_schemas(catalog)
    schema = st.selectbox("Schema", schemas)

    tables = list_tables(catalog, schema)
    table = st.selectbox("Table", tables)

    run_profile = st.button("Run Profiling", use_container_width=True)

if run_profile:
    with st.spinner("Running profiling and generating rules..."):
        output = aidqx_graph.invoke(
            {
                "catalog": catalog,
                "schema": schema,
                "table": table,
                "requested_action": "profile_and_rules",
            }
        )

    if output.get("error"):
        st.error(output["error"])
    else:
        st.session_state.profile_result = output.get("profile_result")
        st.session_state.rules = output.get("generated_rules", [])
        st.session_state.execution_result = None
        st.success("Profiling completed and rules generated.")

profile = st.session_state.profile_result

if profile:
    st.subheader("Profiling Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", profile["row_count"])
    c2.metric("Columns", profile["column_count"])
    c3.metric("Duplicates", profile["duplicate_count"])
    c4.metric("Table", profile["table_name"])

    profile_df = pd.DataFrame(profile["columns"])
    st.dataframe(profile_df, use_container_width=True)

if st.session_state.rules:
    st.subheader("Generated Rules")
    rules_df = pd.DataFrame(st.session_state.rules)

    editable_columns = [
        "enabled",
        "rule_id",
        "column",
        "rule_type",
        "description",
        "parameters",
    ]

    edited = st.data_editor(
        rules_df[editable_columns],
        use_container_width=True,
        num_rows="dynamic",
        key="rules_editor",
    )

    if st.button("Run DQX Execution", type="primary"):
        approved_rules = edited.to_dict(orient="records")

        with st.spinner("Executing DQ rules..."):
            result = execute_rules(
                catalog,
                schema,
                table,
                approved_rules,
            )

        st.session_state.execution_result = result
        st.success("DQX execution completed.")

result = st.session_state.execution_result

if result:
    st.subheader("Execution Summary")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Records", result["total_records"])
    c2.metric("Valid Records", result["valid_records"])
    c3.metric("Invalid Records", result["invalid_records"])
    c4.metric("Pass %", result["passed_percentage"])

    st.markdown("#### Rule-wise Result")
    st.dataframe(pd.DataFrame(result["rule_summary"]), use_container_width=True)

    st.markdown("#### Failed / Quarantine Details")
    failed_df = pd.DataFrame(result["failed_records"])
    if failed_df.empty:
        st.success("No failed records.")
    else:
        st.dataframe(failed_df, use_container_width=True)
