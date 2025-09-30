"""
Simplified Stash API client for Stash Manager
"""

import logging
import time
from typing import Dict, List, Optional

import requests

from src.config.config import (
    get_job_timeout,
    get_performer_limit,
    get_poll_interval,
    get_scene_limit,
)

logger = logging.getLogger("stash_manager.api")


class StashAPI:
    """Simple client for interacting with the Stash API"""

    def __init__(self, url: str, api_key: str):
        """Initialize the Stash API client

        Args:
            url: Base URL for the Stash API
            api_key: API key for authentication
        """
        self.url = url
        self.graphql_url = f"{url}/graphql"
        self.api_key = api_key
        self.headers = {"Content-Type": "application/json", "ApiKey": api_key}
        logger.info(f"Initialized Stash API client for {url}")

    def execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute a GraphQL query against the Stash API"""
        if variables is None:
            variables = {}

        payload = {"query": query, "variables": variables}

        try:
            logger.info(f"Sending GraphQL request to {self.graphql_url}")
            logger.debug(f"Payload: {payload}")

            response = requests.post(self.graphql_url, headers=self.headers, json=payload)

            logger.info(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")
            logger.debug(f"Response text (first 500 chars): {response.text[:500]}")

            response.raise_for_status()
            result = response.json()

            # Check for GraphQL errors
            if "errors" in result:
                errors = result["errors"]
                error_msg = "; ".join([error.get("message", "Unknown error") for error in errors])
                logger.error(f"GraphQL errors: {error_msg}")
                raise Exception(f"GraphQL errors: {error_msg}")

            return result
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            logger.error(
                f"Response text: {response.text if 'response' in locals() else 'No response'}"
            )
            raise Exception(f"API request failed: {str(e)}")
        except ValueError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(
                f"Response text: {response.text if 'response' in locals() else 'No response'}"
            )
            raise Exception(f"API request failed: {str(e)}")

    def trigger_scan(self) -> str:
        """Trigger a metadata scan in Stash

        Returns:
            Job ID for the scan task
        """
        query = """
        mutation MetadataScan($input: ScanMetadataInput!) {
            metadataScan(input: $input)
        }
        """

        variables = {
            "input": {
                "rescan": False,
                "scanGenerateClipPreviews": True,
                "scanGenerateCovers": True,
                "scanGenerateImagePreviews": False,
                "scanGeneratePhashes": True,
                "scanGeneratePreviews": True,
                "scanGenerateSprites": True,
                "scanGenerateThumbnails": True,
            }
        }

        try:
            result = self.execute_query(query, variables)
            job_id = result["data"]["metadataScan"]
            logger.info(f"Triggered scan with job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger scan: {str(e)}")
            raise

    def trigger_generate(self) -> str:
        """Trigger a metadata generation in Stash

        Returns:
            Job ID for the generate task
        """
        query = """
        mutation MetadataGenerate($input: GenerateMetadataInput!) {
            metadataGenerate(input: $input)
        }
        """

        variables = {
            "input": {
                "clipPreviews": False,
                "covers": True,
                "imagePreviews": True,
                "markers": False,
                "phashes": True,
                "previewOptions": {
                    "previewExcludeEnd": "0",
                    "previewExcludeStart": "0",
                    "previewPreset": "slow",
                    "previewSegmentDuration": "0.75",
                    "previewSegments": "12",
                },
                "previews": True,
                "sprites": False,
            }
        }

        try:
            result = self.execute_query(query, variables)
            job_id = result["data"]["metadataGenerate"]
            logger.info(f"Triggered generate with job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger generate: {str(e)}")
            raise

    def get_job_status(self, job_id: str) -> Dict:
        """Get the status of a job

        Args:
            job_id: ID of the job to check

        Returns:
            Dictionary with job status information
        """
        query = """
        query JobQueue {
            jobQueue {
                id
                status
                progress
                startTime
                endTime
            }
        }
        """

        try:
            result = self.execute_query(query)

            # Check if result contains expected data
            if result and "data" in result:
                if "jobQueue" in result["data"] and result["data"]["jobQueue"] is not None:
                    jobs = result["data"]["jobQueue"]

                    # Find the specific job
                    for job in jobs:
                        if job["id"] == job_id:
                            return job

            # Job not found in queue (might have finished)
            return {"id": job_id, "status": "FINISHED", "progress": 1.0}
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            return {"id": job_id, "status": "ERROR", "error": str(e), "progress": 0.0}

    def wait_for_job_completion(self, job_id: str) -> bool:
        """Wait for a job to complete

        Args:
            job_id: ID of the job to wait for

        Returns:
            True if job completed successfully, False otherwise
        """
        timeout = get_job_timeout()
        poll_interval = get_poll_interval()
        logger.info(f"Waiting for job {job_id} to complete (timeout: {timeout}s)")
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                status = self.get_job_status(job_id)
                job_status = status.get("status", "UNKNOWN")
                progress = status.get("progress", 0.0)

                # Check if job is done
                if job_status in ["FINISHED", "CANCELLED", "ERROR"]:
                    logger.info(f"Job {job_id} completed with status: {job_status}")
                    return job_status == "FINISHED"

                # Log progress every few checks
                if int(time.time()) % 30 < poll_interval:
                    logger.info(
                        f"Job {job_id} status: {job_status}, progress: {progress * 100:.1f}%"
                    )

            except Exception as e:
                logger.error(f"Error checking job status: {str(e)}")

            # Wait before next check
            time.sleep(poll_interval)

        logger.error(f"Timeout waiting for job {job_id}")
        return False

    def trigger_identify(self) -> str:
        """Trigger metadata identification in Stash

        Returns:
            Job ID for the identify task
        """
        query = """
        mutation MetadataIdentify($input: IdentifyMetadataInput!) {
            metadataIdentify(input: $input)
        }
        """

        variables = {
            "input": {
                "sources": [
                    {"source": {"stash_box_endpoint": "https://stashdb.org/graphql"}},
                    {"source": {"stash_box_endpoint": "https://theporndb.net/graphql"}},
                    {
                        "source": {"scraper_id": "builtin_autotag"},
                        "options": {
                            "fieldOptions": [],
                            "setCoverImage": None,
                            "setOrganized": False,
                            "includeMalePerformers": None,
                            "skipMultipleMatches": True,
                            "skipMultipleMatchTag": None,
                            "skipSingleNamePerformers": True,
                            "skipSingleNamePerformerTag": None,
                        },
                    },
                ],
                "options": {
                    "fieldOptions": [
                        {
                            "field": "title",
                            "strategy": "OVERWRITE",
                            "createMissing": None,
                        },
                        {"field": "studio", "strategy": "MERGE", "createMissing": True},
                        {
                            "field": "performers",
                            "strategy": "MERGE",
                            "createMissing": True,
                        },
                        {"field": "tags", "strategy": "MERGE", "createMissing": True},
                    ],
                    "setCoverImage": True,
                    "setOrganized": True,
                    "includeMalePerformers": True,
                    "skipMultipleMatches": False,
                    "skipMultipleMatchTag": None,
                    "skipSingleNamePerformers": False,
                    "skipSingleNamePerformerTag": None,
                },
                "paths": [],
            }
        }

        try:
            result = self.execute_query(query, variables)
            job_id = result["data"]["metadataIdentify"]
            logger.info(f"Triggered identify with job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger identify: {str(e)}")
            raise

    def trigger_clean(self) -> str:
        """Trigger metadata clean in Stash

        Returns:
            Job ID for the clean task
        """
        query = """
        mutation MetadataClean($input: CleanMetadataInput!) {
            metadataClean(input: $input)
        }
        """

        variables = {"input": {"dryRun": False}}

        try:
            result = self.execute_query(query, variables)
            job_id = result["data"]["metadataClean"]
            logger.info(f"Triggered clean with job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger clean: {str(e)}")
            raise

    def get_all_scenes(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: str = "ASC",
    ) -> List[Dict]:
        """Get all scenes from Stash or StashDB

        Args:
            limit: Optional limit for the number of scenes to return
            start_date: Optional start date for the search (YYYY-MM-DD)
            end_date: Optional end date for the search (YYYY-MM-DD)
            direction: Optional sort direction for date-based queries ("ASC" or "DESC")

        Returns:
            List of scenes
        """
        # Check if this is StashDB based on the URL
        is_stashdb = "stashdb.org" in self.url.lower()

        if is_stashdb:
            return self._get_stashdb_scenes_paginated(limit, start_date, end_date, direction)
        else:
            return self._get_local_stash_scenes(limit, start_date, end_date)

    def _get_stashdb_scenes_paginated(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: str = "ASC",
    ) -> List[Dict]:
        """Get scenes from StashDB with pagination support"""
        # StashDB query structure - date filtering with range
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
        max_scenes = limit if limit else 10000  # Default reasonable limit

        while len(all_scenes) < max_scenes:
            variables = {
                "input": {
                    "page": page,
                    "per_page": per_page,
                    "sort": "DATE",
                    "direction": direction,  # Use the provided direction parameter
                }
            }

            # Handle date filtering for StashDB
            if start_date and end_date:
                logger.info(
                    f"Setting date range filter: {start_date} to {end_date} (inclusive) - Page {page}"  # noqa: E501
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

            try:
                logger.info(
                    f"Executing StashDB scene query page {page} with variables: {variables}"
                )
                result = self.execute_query(query, variables)

                # Extract scenes from StashDB response
                if "data" in result and "queryScenes" in result["data"]:
                    query_result = result["data"]["queryScenes"]
                    if "scenes" in query_result:
                        page_scenes = query_result["scenes"]
                        total_count = query_result.get("count", 0)

                        logger.info(
                            f"Page {page}: Retrieved {len(page_scenes)} scenes (Total available: {total_count})"  # noqa: E501
                        )

                        if not page_scenes:
                            # No more scenes
                            break

                        all_scenes.extend(page_scenes)

                        # Check if we've retrieved all available scenes
                        if len(page_scenes) < per_page:
                            logger.info("Reached end of available scenes")
                            break

                        page += 1
                    else:
                        logger.warning(f"No scenes in response: {result}")
                        break
                else:
                    logger.warning(f"Unexpected response structure: {result}")
                    break

            except Exception as e:
                logger.error(f"Failed to get scenes page {page}: {str(e)}")
                break

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
                    f"Filtered to {len(filtered_scenes)} scenes within date range {start_date} to {end_date}"  # noqa: E501
                )
                return filtered_scenes

            except ValueError as e:
                logger.error(f"Date parsing error in filter parameters: {e}")
                return all_scenes  # Return unfiltered if input date parsing fails

        return all_scenes

    def _get_local_stash_scenes(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """Get scenes from local Stash instance"""
        # Local Stash query structure
        query = """
        query FindScenes($filter: FindFilterType) {
            findScenes(filter: $filter) {
                count
                scenes {
                    id
                    title
                    organized
                    studio {
                        id
                        name
                    }
                    performers {
                        id
                        name
                        gender
                        ethnicity
                        measurements
                    }
                    tags {
                        id
                        name
                    }
                }
            }
        }
        """

        per_page = limit if limit else get_scene_limit()
        variables = {"filter": {"per_page": per_page}}

        # For local Stash, add date filtering if provided
        if start_date or end_date:
            # Local Stash uses different date filtering syntax
            if start_date and end_date:
                # Date range for local Stash (this may need adjustment based on your Stash version)
                variables["filter"]["created_at"] = {
                    "value": f"{start_date} - {end_date}",
                    "modifier": "BETWEEN",
                }
            elif start_date:
                variables["filter"]["created_at"] = {
                    "value": start_date,
                    "modifier": "GREATER_THAN",
                }
            elif end_date:
                variables["filter"]["created_at"] = {
                    "value": end_date,
                    "modifier": "LESS_THAN",
                }

        try:
            logger.info(f"Executing local Stash scene query with variables: {variables}")
            result = self.execute_query(query, variables)

            # Extract scenes from local Stash response
            if (
                "data" in result
                and "findScenes" in result["data"]
                and "scenes" in result["data"]["findScenes"]
            ):
                scenes = result["data"]["findScenes"]["scenes"]
                logger.info(f"Retrieved {len(scenes)} scenes from local Stash")
                return scenes

            logger.warning(f"Unexpected response structure: {result}")
            return []
        except Exception as e:
            logger.error(f"Failed to get scenes: {str(e)}")
            return []

    def get_performers(self) -> List[Dict]:
        """Get all performers from Stash

        Returns:
            List of performers
        """
        query = """
        query AllPerformers($filter: FindFilterType) {
            allPerformers(filter: $filter) {
                id
                name
                gender
                ethnicity
                measurements
            }
        }
        """

        limit = get_performer_limit()
        variables = {"filter": {"per_page": limit}}

        try:
            result = self.execute_query(query, variables)
            if "data" in result and "allPerformers" in result["data"]:
                return result["data"]["allPerformers"]
            else:
                logger.warning(f"Unexpected response structure for performers: {result}")
                return []
        except Exception as e:
            logger.error(f"Failed to get performers: {str(e)}")
            return []

    def delete_scene(self, scene_id: str, delete_file: bool = True) -> bool:
        """Delete a scene

        Args:
            scene_id: ID of the scene to delete
            delete_file: Whether to delete the associated file

        Returns:
            True if successful, False otherwise
        """
        query = """
        mutation ScenesDestroy($input: ScenesDestroyInput!) {
            scenesDestroy(input: $input)
        }
        """

        variables = {
            "input": {
                "ids": [scene_id],
                "delete_file": delete_file,
                "delete_generated": True,
            }
        }

        try:
            result = self.execute_query(query, variables)
            success = result["data"]["scenesDestroy"]

            if success:
                logger.info(f"Successfully deleted scene {scene_id}")
            else:
                logger.error(f"Failed to delete scene {scene_id}")

            return success
        except Exception as e:
            logger.error(f"Error deleting scene {scene_id}: {str(e)}")
            return False
