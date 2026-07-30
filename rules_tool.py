from langchain_core.tools import tool
from services.dqx_service import generate_rules


@tool
def generate_dq_rules(profile_result: dict):
    """Generate suggested data quality rules from a profiling result."""
    return generate_rules(profile_result)
