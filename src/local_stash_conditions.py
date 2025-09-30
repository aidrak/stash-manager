# File: src/local_stash_conditions.py
LOCAL_STASH_CONDITIONS = {
    "tags": {
        "label": "Tags",
        "operators": ["include", "exclude"],
        "type": "text",
        "help_text": (
            "Check if a scene has specific tags. Use a comma-separated list for multiple values."
        ),
    },
    "performers.name": {
        "label": "Performer Name",
        "operators": ["include", "exclude"],
        "type": "text",
        "help_text": "Check if at least one performer matches the criteria.",
    },
    "studio.name": {
        "label": "Studio",
        "operators": ["include", "exclude"],
        "type": "text",
        "help_text": "Check the studio that produced the scene.",
    },
    "title": {
        "label": "Title",
        "operators": ["include", "exclude"],
        "type": "text",
        "help_text": "Check the title of a scene.",
    },
    "performers.ethnicity": {
        "label": "Performer Ethnicity",
        "operators": ["include", "exclude"],
        "type": "text",
        "help_text": (
            "Check if at least one performer matches the ethnicity. Use comma-separated "
            "list for multiple values."
        ),
    },
    "performers.gender": {
        "label": "Performer Gender",
        "operators": ["include", "exclude"],
        "type": "text",
        "help_text": (
            "Check if at least one performer matches the gender (MALE, FEMALE, "
            "TRANSGENDER_MALE, TRANSGENDER_FEMALE, INTERSEX, NON_BINARY)."
        ),
    },
    "performers.cup_size": {
        "label": "Cup Size",
        "operators": ["include", "exclude"],
        "type": "text",
        "help_text": (
            "Check if at least one performer matches the cup size. Use single letters (D "
            "matches D, DD, DDD, etc.) - parsed from measurements"
        ),
    },
    "performers.waist": {
        "label": "Waist Size",
        "operators": ["include", "exclude", "is_larger_than", "is_smaller_than"],
        "type": "number",
        "help_text": (
            "Check if at least one performer matches waist measurements in inches - parsed "
            "from measurements"
        ),
    },
    "performers.hip": {
        "label": "Hip Size",
        "operators": ["include", "exclude", "is_larger_than", "is_smaller_than"],
        "type": "number",
        "help_text": (
            "Check if at least one performer matches hip measurements in inches - parsed "
            "from measurements"
        ),
    },
    "date": {
        "label": "Release Date",
        "operators": ["include", "exclude", "is_larger_than", "is_smaller_than"],
        "type": "date",
        "help_text": "Check the release date of the scene (YYYY-MM-DD format)",
    },
}
