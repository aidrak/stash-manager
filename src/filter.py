import logging
import re

class SceneFilter:
    """
    Filters scenes based on configurable criteria.
    """

    def __init__(self, config: dict):
        self.filters = config.get("filters", {})
        self.controls = config.get("filter_controls", {})
        
        enabled_filters = [k for k, v in self.controls.items() if v]
        logging.info("Filter initialized - Enabled filters: %s", enabled_filters)
        
        if self.controls.get('enable_performer_filters', False):
            whitelist = self.filters.get('performer_whitelist', [])
            blacklist = self.filters.get('performer_blacklist', [])
            logging.info("Performer whitelist loaded: %d performers", len(whitelist))
            logging.info("Performer blacklist loaded: %d performers", len(blacklist))
            logging.debug("Whitelist: %s", whitelist)
            logging.debug("Blacklist: %s", blacklist)
        
        logging.debug("Filter config: %s", self.filters)

    def _normalize_list(self, filter_list: list) -> list:
        return [item.lower().strip() for item in filter_list if item.strip()]

    def _check_title_filters(self, title: str) -> tuple[bool, str]:
        if not self.controls.get('enable_title_filters', False):
            return True, "Title filters disabled"
        if not title:
            return True, "No title to check"
        
        title_lower = title.lower()
        exclude_words = self._normalize_list(self.filters.get('title_exclude_words', []))
        if exclude_words:
            for word in exclude_words:
                if word in title_lower:
                    return False, f"Title contains excluded word: '{word}'"
        
        include_words = self._normalize_list(self.filters.get('title_include_words', []))
        if include_words:
            for word in include_words:
                if word in title_lower:
                    return True, f"Title contains required word: '{word}'"
            return False, f"Title missing required words: {include_words}"
        
        return True, "Title passed filters"

    def _check_studio_filters(self, studio: dict) -> tuple[bool, str]:
        if not self.controls.get('enable_studio_filters', False):
            return True, "Studio filters disabled"
        if not studio:
            return True, "No studio to check"
        
        studio_name = studio.get('name', '').lower()
        exclude_studios = self._normalize_list(self.filters.get('exclude_studios', []))
        if exclude_studios:
            for excluded in exclude_studios:
                if excluded in studio_name:
                    return False, f"Studio is excluded: '{studio.get('name')}'"
        
        include_studios = self._normalize_list(self.filters.get('include_studios', []))
        if include_studios:
            for included in include_studios:
                if included in studio_name:
                    return True, f"Studio is included: '{studio.get('name')}'"
            return False, f"Studio not in include list: '{studio.get('name')}'"
        
        return True, "Studio passed filters"

    def _check_tag_filters(self, tags: list) -> tuple[bool, str]:
        if not self.controls.get('enable_tag_filters', False):
            return True, "Tag filters disabled"
        if not tags:
            return True, "No tags to check"
        
        tag_names = [tag.get('name', '').lower() for tag in tags]
        exclude_tags = self._normalize_list(self.filters.get('exclude_tags', []))
        if exclude_tags:
            for tag_name in tag_names:
                for excluded in exclude_tags:
                    if excluded in tag_name:
                        return False, f"Scene has excluded tag: '{tag_name}'"
        
        include_tags = self._normalize_list(self.filters.get('include_tags', []))
        if include_tags:
            for included in include_tags:
                for tag_name in tag_names:
                    if included in tag_name:
                        return True, f"Scene has required tag: '{tag_name}'"
            return False, f"Scene missing required tags: {include_tags}"
        
        return True, "Tags passed filters"

    def _check_performer_whitelist_blacklist(self, performer_names: list) -> tuple[bool, str]:
        whitelist = self._normalize_list(self.filters.get('performer_whitelist', []))
        if whitelist:
            for name in performer_names:
                for whitelisted in whitelist:
                    if whitelisted in name:
                        return True, f"Scene has whitelisted performer: '{name}'"

        blacklist = self._normalize_list(self.filters.get('performer_blacklist', []))
        if blacklist:
            for name in performer_names:
                for blacklisted in blacklist:
                    if blacklisted in name:
                        return False, f"Scene has blacklisted performer: '{name}'"
        
        return None, "No whitelist/blacklist matches"

    def _check_ethnicity_filters(self, ethnicities: list) -> tuple[bool, str]:
        if not self.controls.get('enable_ethnicity_filters', False):
            return True, "Ethnicity filters disabled"
            
        exclude_ethnicities = [e.upper() for e in self.filters.get('exclude_ethnicities', [])]
        if exclude_ethnicities:
            for ethnicity in ethnicities:
                if ethnicity in exclude_ethnicities:
                    return False, f"Scene has excluded ethnicity: '{ethnicity}'"

        include_ethnicities = [e.upper() for e in self.filters.get('include_ethnicities', [])]
        if include_ethnicities:
            found_included = False
            for ethnicity in ethnicities:
                if ethnicity in include_ethnicities:
                    found_included = True
                    break
            if not found_included:
                return False, f"Scene missing required ethnicities: {include_ethnicities}"

        return True, "Ethnicity filters passed"

    def _check_breast_size_filters(self, measurements_list: list) -> tuple[bool, str]:
        if not self.controls.get('enable_breast_size_filters', False):
            return True, "Breast size filters disabled"
        
        include_sizes = self._normalize_list(self.filters.get('include_breast_sizes', []))
        exclude_sizes = self._normalize_list(self.filters.get('exclude_breast_sizes', []))

        # If no filters are set, or "any" is specified, pass the filter
        if not include_sizes and not exclude_sizes:
            return True, "No breast size filters specified."
        if 'any' in include_sizes:
            return True, "Breast size filter set to 'any'."

        for measurements in measurements_list:
            if not measurements or not isinstance(measurements, dict):
                continue
            
            cup_size = str(measurements.get('cup_size', '')).lower().strip()
            if not cup_size:
                cup_size = 'null' # Treat empty as 'null' for matching purposes

            # Check exclude sizes first
            if any(size in cup_size for size in exclude_sizes):
                return False, f"Performer has excluded breast size: '{cup_size}'"

            # Check include sizes
            if include_sizes:
                if any(size in cup_size for size in include_sizes):
                    return True, f"Performer has included breast size: '{cup_size}'"
        
        # If we have an include list and no performer matched, fail the filter
        if include_sizes:
            return False, "No performer matched the required breast sizes."

        return True, "Breast size filters passed"

    def _check_performer_filters(self, performers: list) -> tuple[bool, str]:
        if not self.controls.get('enable_performer_filters', False):
            return True, "Performer filters disabled"
        if not performers:
            return False, "Scene has no performers to check"

        performer_names = []
        ethnicities = []
        measurements_list = []
        
        for p_data in performers:
            performer = p_data.get('performer', {})
            name = performer.get('name', '')
            ethnicity = performer.get('ethnicity', '')
            measurements = performer.get('measurements', {})
            gender = performer.get('gender', '')
            
            if name:
                performer_names.append(name.lower())
            if ethnicity:
                ethnicities.append(ethnicity.upper())
            if gender and gender.lower() == 'female':
                measurements_list.append(measurements)

        result, reason = self._check_performer_whitelist_blacklist(performer_names)
        if result is not None:
            return result, reason

        passed, reason = self._check_ethnicity_filters(ethnicities)
        if not passed:
            return False, reason

        passed, reason = self._check_breast_size_filters(measurements_list)
        if not passed:
            return False, reason

        return True, "All performer filters passed"

    def should_add_scene(self, scene: dict) -> tuple[bool, str]:
        logging.debug("Filtering scene: %s", scene.get('title'))
        
        passed, reason = self._check_title_filters(scene.get('title'))
        if not passed:
            return False, reason
        
        passed, reason = self._check_studio_filters(scene.get('studio'))
        if not passed:
            return False, reason
        
        passed, reason = self._check_tag_filters(scene.get('tags', []))
        if not passed:
            return False, reason
        
        passed, reason = self._check_performer_filters(scene.get('performers', []))
        if not passed:
            return False, reason
        
        return True, "Scene passed all enabled filters"
