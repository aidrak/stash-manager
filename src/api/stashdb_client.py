"""
StashDB API client for external StashDB operations
"""

import logging
from typing import Dict, List, Optional

from src.api.base_stash_client import BaseStashClient
from src.config.config import get_scene_limit

logger = logging.getLogger("stash_manager.stashdb_api")


class StashDBClient(BaseStashClient):
    """Client for interacting with external StashDB API"""

    def get_all_scenes(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: str = "ASC",
    ) -> List[Dict]:
        """Get all scenes from StashDB with optional filtering

        Args:
            limit: Maximum number of scenes to retrieve
            start_date: Filter scenes created after this date (YYYY-MM-DD)
            end_date: Filter scenes created before this date (YYYY-MM-DD)
            direction: Sort direction ("ASC" or "DESC")

        Returns:
            List of scene data from StashDB
        """
        if limit is None:
            limit = get_scene_limit()

        query = """
        query QueryScenes($input: SceneQueryInput!) {
            queryScenes(input: $input) {
                count
                scenes {
                    id
                    title
                    details
                    date
                    studio {
                        id
                        name
                    }
                    performers {
                        performer {
                            id
                            name
                            gender
                            ethnicity
                            measurements {
                                band_size
                                cup_size
                                waist
                                hip
                            }
                        }
                    }
                    tags {
                        id
                        name
                    }
                }
            }
        }
        """

        all_scenes: List[Dict] = []
        page = 1
        per_page = 100  # StashDB seems to have lower limits, start conservative
        max_scenes = limit if limit else get_scene_limit()

        while len(all_scenes) < max_scenes:
            variables = {
                "input": {
                    "page": page,
                    "per_page": per_page,
                    "sort": "DATE",
                    "direction": direction,
                }
            }

            # Handle date filtering for StashDB
            if start_date and end_date:
                logger.info(
                    f"Setting date range filter: {start_date} to {end_date} "
                    f"(inclusive) - Page {page}"
                )
                variables["input"]["date"] = {
                    "value": start_date,
                    "modifier": "GREATER_THAN",
                }
            elif start_date:
                # Only start date provided - get scenes from this date onward (inclusive)
                variables["input"]["date"] = {
                    "value": start_date,
                    "modifier": "GREATER_THAN",
                }
            elif end_date:
                # Only end date provided - get scenes up to this date (inclusive)
                variables["input"]["date"] = {
                    "value": end_date,
                    "modifier": "LESS_THAN",
                }

            logger.info(
                f"Fetching page {page} from StashDB with limit={max_scenes}, "
                f"dates={start_date} to {end_date}"
            )

            try:
                result = self.execute_query(query, variables)
                if not result or "data" not in result or "queryScenes" not in result["data"]:
                    logger.warning("No data returned from StashDB query.")
                    break

                scenes_data = result["data"]["queryScenes"]
                scenes = scenes_data.get("scenes", [])

                if not scenes:
                    logger.info("No more scenes found on StashDB.")
                    break

                all_scenes.extend(scenes)
                logger.info(
                    f"Retrieved {len(scenes)} scenes from StashDB. Total: {len(all_scenes)}"
                )

                if len(scenes) < per_page:
                    break  # Last page
                page += 1

            except Exception as e:
                logger.error(f"Error fetching scenes from StashDB: {e}")
                break  # Exit loop on error

        logger.info(
            f"Retrieved total of {len(all_scenes)} scenes from StashDB before date filtering"
        )

        # Debug logging to see what dates we actually got
        logger.info("Sample scene dates from StashDB:")
        for i, scene in enumerate(all_scenes[:5]):  # Log first 5 scenes
            scene_date = scene.get("date", "No date")
            scene_title = scene.get("title", "No title")[:50]
            logger.info(f"  Scene {i + 1}: '{scene_title}' - Date: {scene_date}")

        # Post-process date filtering for StashDB when both start and end dates are provided
        if start_date and end_date:
            from datetime import datetime

            filtered_scenes = []

            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")

                for scene in all_scenes:
                    scene_date_str = scene.get("date")
                    if scene_date_str:
                        try:
                            # Handle various date formats from StashDB
                            if len(scene_date_str) == 10:  # YYYY-MM-DD
                                scene_dt = datetime.strptime(scene_date_str, "%Y-%m-%d")
                            elif len(scene_date_str) > 10:  # YYYY-MM-DD with time
                                scene_dt = datetime.strptime(scene_date_str[:10], "%Y-%m-%d")
                            else:
                                logger.warning(f"Unexpected date format: {scene_date_str}")
                                filtered_scenes.append(scene)  # Include if we can't parse
                                continue

                            # Inclusive range check: start_date <= scene_date <= end_date
                            if start_dt <= scene_dt <= end_dt:
                                filtered_scenes.append(scene)
                        except ValueError as e:
                            # If date parsing fails, include the scene to be safe
                            logger.warning(f"Could not parse scene date '{scene_date_str}': {e}")
                            filtered_scenes.append(scene)
                    else:
                        # If no date, exclude from date-filtered results
                        logger.debug("Scene has no date, excluding from date range filter")

                logger.info(
                    f"Filtered to {len(filtered_scenes)} scenes within date range "
                    f"{start_date} to {end_date}"
                )
                return filtered_scenes

            except ValueError as e:
                logger.error(f"Date parsing error in filter parameters: {e}")
                return all_scenes  # Return unfiltered if input date parsing fails

        return all_scenes[:max_scenes]
