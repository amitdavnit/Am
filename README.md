# AIDQX Agent App

Generic Databricks App for:

1. Selecting a catalog, schema, and table
2. Running basic profiling
3. Viewing generated DQ rules
4. Running DQ execution
5. Viewing pass/fail summary and invalid records

## Architecture

- `app.py`: Streamlit UI
- `agent/graph.py`: LangGraph workflow
- `agent/state.py`: Shared graph state
- `tools/`: LangChain tools
- `services/dqx_service.py`: Profiling, rule generation, and execution logic

## Databricks setup

1. Import this folder into Databricks Workspace or upload it to a Git folder.
2. Create a Databricks App and select this folder as the source.
3. Ensure the app service principal has:
   - `USE CATALOG`
   - `USE SCHEMA`
   - `SELECT` on target tables
4. Deploy the app.

## Notes

- This starter version uses Spark SQL when running inside Databricks.
- Outside Databricks, it uses a small demo pandas DataFrame.
- Rule registration/versioning can be added in phase 2.
- Replace the generic rule-generation logic in `services/dqx_service.py`
  with Databricks Labs DQX APIs when the DQX package is available in the target workspace.
