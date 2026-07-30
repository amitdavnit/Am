from langchain_core.tools import tool
from services.dqx_service import run_profiling


@tool
def profile_table(catalog: str, schema: str, table: str):
    """Run profiling for a Databricks table and return column-level statistics."""
    return run_profiling(catalog, schema, table)
