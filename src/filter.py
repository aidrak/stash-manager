import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger("stash_manager.filter")

def _is_cup_size_match(scene_cup: str, rule_cup: str) -> bool:
    """
    Check if a scene cup size matches a rule cup size.
    E.g., rule "d" matches scene "dd", "ddd", etc.
    """
    # Only apply this logic for single letters (cup sizes)
    if len(rule_cup) == 1 and rule_cup.isalpha():
        # Check if scene cup starts with the rule letter (case insensitive)
        return scene_cup.lower().startswith(rule_cup.lower()) and scene_cup.isalpha()
    return False

def _parse_measurements(measurements_str: str) -> Dict[str, Any]:
    """
    Parse measurements string like "38DD-20-34" into components.
    Returns dict with cup_size, waist, hip
    """
    if not measurements_str:
        return {'cup_size': None, 'waist': None, 'hip': None}
    
    # Pattern to match measurements like "38DD-20-34" or "36D-24-36"
    pattern_with_cup = r'(\d+)([A-Z]+)-(\d+)-(\d+)'
    match = re.match(pattern_with_cup, measurements_str.strip())
    
    if match:
        cup_size = match.group(2)
        waist = int(match.group(3))
        hip = int(match.group(4))
        
        return {
            'cup_size': cup_size,
            'waist': waist,
            'hip': hip
        }

    # Pattern to match measurements like "38-20-34"
    pattern_without_cup = r'(\d+)-(\d+)-(\d+)'
    match = re.match(pattern_without_cup, measurements_str.strip())

    if match:
        # It matched, but there's no cup size. Return None for cup_size.
        return {'cup_size': None, 'waist': int(match.group(2)), 'hip': int(match.group(3))}

    # Handle cases where measurements don't match expected format
    logger.warning(f"Could not parse measurements: {measurements_str}")
    return {'cup_size': None, 'waist': None, 'hip': None}

def _get_value_from_path(data: Dict, path: str) -> Any:
    """
    Retrieves a value from a nested dictionary using a dot-separated path.
    If the path encounters a list, it recursively calls itself for each item.
    Handles special parsed measurement fields.
    """
    # Handle special parsed measurement fields
    if path in ['performers.cup_size', 'performers.waist', 'performers.hip']:
        performers = data.get('performers', [])
        if not isinstance(performers, list):
            return None
            
        results = []
        measurement_field = path.split('.')[-1]  # cup_size, waist, or hip
        
        for performer in performers:
            measurements_str = performer.get('measurements', '')
            parsed = _parse_measurements(measurements_str)
            value = parsed.get(measurement_field)
            if value is not None:
                results.append(value)
        
        return results if results else None
    
    # Original logic for all other paths
    keys = path.split('.')
    current_value = data
    for i, key in enumerate(keys):
        if current_value is None:
            return None
        if isinstance(current_value, list):
            # If we have a list, collect the value from each item in the list
            remaining_path = '.'.join(keys[i:])
            results = []
            for item in current_value:
                value = _get_value_from_path(item, remaining_path)
                if value is not None:
                    if isinstance(value, list):
                        results.extend(value)
                    else:
                        results.append(value)
            return results
        elif isinstance(current_value, dict):
            current_value = current_value.get(key)
        else:
            return None
    return current_value

def _check_condition(scene_value: Any, operator: str, rule_value: Any, field: str = None) -> Tuple[bool, Any]:
    """
    Checks if a scene value meets a rule's condition based on the operator.
    Returns a tuple of (bool, matched_value).
    """
    if scene_value is None:
        if operator == 'include' and rule_value is None:
            return True, None
        if operator == 'exclude' and rule_value is None:
            return False, None
        return False, None

    # Ensure scene_value is a list for consistent processing
    if not isinstance(scene_value, list):
        scene_value = [scene_value]

    # Normalize all values to lowercase strings for case-insensitive matching
    scene_value_lower = [str(v).lower() for v in scene_value]
    if rule_value is not None:
        if isinstance(rule_value, list):
            rule_value_lower = [str(v).lower() for v in rule_value]
        else:
            rule_value_lower = str(rule_value).lower()
    else:
        rule_value_lower = None

    if operator == 'include':
        rule_values = [v.strip() for v in str(rule_value_lower).split(',')]
        for s_val in scene_value_lower:
            for r_val in rule_values:
                # Special handling for cup sizes - "d" should match "dd", "ddd", etc.
                if field == 'tags.name':
                    # Exact match for tags
                    if r_val == s_val:
                        original_index = scene_value_lower.index(s_val)
                        original_value = scene_value[original_index]
                        return True, original_value
                elif _is_cup_size_match(s_val, r_val) or r_val in s_val:
                    # Substring match for other fields
                    original_index = scene_value_lower.index(s_val)
                    original_value = scene_value[original_index]
                    return True, original_value
        return False, None
    
    if operator == 'exclude':
        rule_values = [v.strip() for v in str(rule_value_lower).split(',')]
        # "Does not contain" check
        if not any(r_val in scene_value_lower for r_val in rule_values):
            return True, f"no {', '.join(rule_values)} found"
        
        return False, None
    
    if operator in ['is_larger_than', 'is_smaller_than']:
        try:
            rule_value_num = float(rule_value_lower)
            scene_value_num = float(scene_value[0])
            if operator == 'is_larger_than':
                if scene_value_num > rule_value_num:
                    return True, scene_value[0]
            if operator == 'is_smaller_than':
                if scene_value_num < rule_value_num:
                    return True, scene_value[0]
        except (ValueError, IndexError):
            return False, None
        return False, None

    logger.warning(f"Unknown operator '{operator}' used in filter rule.")
    return False, None
