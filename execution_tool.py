from langchain_core.tools import tool
from services.dqx_service import execute_rules


@tool
def execute_dqx(catalog: str, schema: str, table: str, rules: list):
    """Execute approved data quality rules and return pass/fail results."""
    return execute_rules(catalog, schema, table, rules)
