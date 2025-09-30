import re
from typing import Any, Dict


class ValidationError(Exception):
    pass


def validate_string(
    value: str,
    field_name: str,
    min_length: int = 0,
    max_length: int = 255,
    required: bool = True,
) -> str:
    """Validate string input"""
    if not value and required:
        raise ValidationError(f"{field_name} is required")

    if not value:
        return ""

    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")

    value = value.strip()

    if len(value) < min_length:
        raise ValidationError(
            f"{field_name} must be at least {min_length} characters long"
        )

    if len(value) > max_length:
        raise ValidationError(
            f"{field_name} must be no more than {max_length} characters long"
        )

    return value


def validate_operator(value: str) -> str:
    """Validate filter operator"""
    valid_operators = [
        "include",
        "exclude",
        "is_larger_than",
        "is_smaller_than",
        "equals",
        "not_equals",
        "contains",
        "not_contains",
        "starts_with",
        "ends_with",
        "regex",
    ]
    value = validate_string(value, "operator", required=True)

    if value not in valid_operators:
        raise ValidationError(
            f"Invalid operator. Must be one of: {', '.join(valid_operators)}"
        )

    return value


def validate_action(value: str) -> str:
    """Validate filter action"""
    valid_actions = ["accept", "reject"]
    value = validate_string(value, "action", required=True)

    if value not in valid_actions:
        raise ValidationError(
            f"Invalid action. Must be one of: {', '.join(valid_actions)}"
        )

    return value


def validate_condition_type(value: str) -> str:
    """Validate condition type"""
    value = validate_string(value, "condition type", required=True)

    return value


def validate_regex(pattern: str) -> str:
    """Validate regex pattern"""
    if not pattern:
        return pattern

    try:
        re.compile(pattern)
        return pattern
    except re.error as e:
        raise ValidationError(f"Invalid regex pattern: {e}")


def validate_filter_rule(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a complete filter rule"""
    validated = {}

    # The form field names are 'condition-type', 'condition-operator', 'condition-value'
    # The rule structure is 'field', 'match', 'value'
    validated["field"] = validate_string(
        form_data.get("condition-type", ""), "condition type", required=True
    )
    validated["match"] = validate_operator(form_data.get("condition-operator", ""))
    validated["value"] = validate_string(
        form_data.get("condition-value", ""),
        "condition value",
        required=True,
        max_length=1000,
    )
    validated["action"] = validate_action(form_data.get("action", ""))
    validated["name"] = (
        f"{validated['field']} {validated['match']} {validated['value']}"
    )

    # Special validation for regex operator
    if validated["match"] == "regex":
        validated["value"] = validate_regex(validated["value"])

    return validated


def validate_job_parameters(job_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate job execution parameters"""
    validated = {}

    if job_name == "add_new_scenes_to_whisparr":
        if params.get("start_date"):
            start_date = validate_string(
                params["start_date"], "start_date", required=False
            )
            if start_date and not re.match(r"^\d{4}-\d{2}-\d{2}$", start_date):
                raise ValidationError("Start date must be in YYYY-MM-DD format")
            validated["start_date"] = start_date

        if params.get("end_date"):
            end_date = validate_string(params["end_date"], "end_date", required=False)
            if end_date and not re.match(r"^\d{4}-\d{2}-\d{2}$", end_date):
                raise ValidationError("End date must be in YYYY-MM-DD format")
            validated["end_date"] = end_date

        validated["dry_run"] = str(params.get("dry_run", "false")).lower() == "true"

        sort_direction = params.get("sort_direction", "DESC")
        if sort_direction not in ["ASC", "DESC"]:
            raise ValidationError("Sort direction must be ASC or DESC")
        validated["sort_direction"] = sort_direction

    return validated
