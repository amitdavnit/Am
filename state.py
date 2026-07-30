from typing import Any, Dict, List, TypedDict


class AIDQXState(TypedDict, total=False):
    catalog: str
    schema: str
    table: str
    full_table_name: str
    profile_result: Dict[str, Any]
    generated_rules: List[Dict[str, Any]]
    approved_rules: List[Dict[str, Any]]
    execution_result: Dict[str, Any]
    requested_action: str
    error: str
