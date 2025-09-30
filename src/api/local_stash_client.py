"""
Local Stash API client for local instance operations
"""

import logging
import time
from typing import Dict, List, Optional

from src.api.base_stash_client import BaseStashClient
from src.config.config import (
    get_job_timeout,
    get_performer_limit,
    get_poll_interval,
    get_scene_limit,
)

logger = logging.getLogger("stash_manager.local_stash_api")


class LocalStashClient(BaseStashClient):
    """Client for interacting with local Stash API"""

    def trigger_scan(self) -> str:
        """Trigger a metadata scan in local Stash

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
            logger.info(f"Triggered metadata scan with job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger metadata scan: {e}")
            raise

    def trigger_generate(self) -> str:
        """Trigger metadata generation in local Stash

        Returns:
            Job ID for the generation task
        """
        query = """
        mutation MetadataGenerate($input: GenerateMetadataInput!) {
            metadataGenerate(input: $input)
        }
        """

        variables = {
            "input": {
                "sprites": True,
                "previews": True,
                "imagePreviews": False,
                "previewOptions": {
                    "previewSegments": 12,
                    "previewSegmentDuration": 0.75,
                    "previewExcludeStart": "0s",
                    "previewExcludeEnd": "0s",
                    "previewPreset": "SLOW",
                },
                "covers": True,
                "clips": False,
                "phashes": True,
                "thumbnails": True,
                "interactiveHeatmapsSpeeds": False,
                "imageThumbnails": False,
            }
        }

        try:
            result = self.execute_query(query, variables)
            job_id = result["data"]["metadataGenerate"]
            logger.info(f"Triggered metadata generation with job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger metadata generation: {e}")
            raise

    def wait_for_job_completion(self, job_id: str) -> bool:
        """Wait for a job to complete

        Args:
            job_id: Job ID to wait for

        Returns:
            True if job completed successfully, False otherwise
        """
        timeout = get_job_timeout()
        poll_interval = get_poll_interval()
        start_time = time.time()

        logger.info(f"Waiting for job {job_id} to complete (timeout: {timeout}s)")

        while time.time() - start_time < timeout:
            try:
                status = self.get_job_status(job_id)

                if status.get("status") in ["FINISHED", "CANCELLED", "FAILED"]:
                    success = status.get("status") == "FINISHED"
                    logger.info(f"Job {job_id} completed with status: {status.get('status')}")

                    if not success and status.get("error"):
                        logger.error(f"Job {job_id} error: {status.get('error')}")

                    return success

                logger.debug(
                    f"Job {job_id} status: {status.get('status')} "
                    f"(progress: {status.get('progress', 'unknown')})"
                )

                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error checking job {job_id} status: {e}")
                time.sleep(poll_interval)

        logger.error(f"Job {job_id} timed out after {timeout} seconds")
        return False

    def trigger_identify(self) -> str:
        """Trigger scene identification in local Stash

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
                "sources": [{"source": {"stash_box_index": 0}}],
                "options": {
                    "setCoverImage": True,
                    "setOrganizedFlag": True,
                    "includeMalePerformers": True,
                    "skipMultipleMatches": False,
                    "skipMultipleMatchTag": "",
                    "skipSingleNamePerformers": False,
                    "skipSingleNamePerformerTag": "",
                    "fieldOptions": [
                        {"field": "TITLE", "strategy": "OVERWRITE", "createMissing": True},
                        {"field": "STUDIO", "strategy": "OVERWRITE", "createMissing": True},
                        {"field": "PERFORMERS", "strategy": "OVERWRITE", "createMissing": True},
                        {"field": "TAGS", "strategy": "MERGE", "createMissing": True},
                    ],
                },
            }
        }

        try:
            result = self.execute_query(query, variables)
            job_id = result["data"]["metadataIdentify"]
            logger.info(f"Triggered metadata identify with job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger metadata identify: {e}")
            raise

    def trigger_clean(self) -> str:
        """Trigger clean/removal of scenes in local Stash

        Returns:
            Job ID for the clean task
        """
        query = """
        mutation MetadataClean($input: CleanMetadataInput!) {
            metadataClean(input: $input)
        }
        """

        variables = {"input": {"paths": [], "dryRun": False}}

        try:
            result = self.execute_query(query, variables)
            job_id = result["data"]["metadataClean"]
            logger.info(f"Triggered metadata clean with job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger metadata clean: {e}")
            raise

    def get_performers(self) -> List[Dict]:
        """Get all performers from local Stash

        Returns:
            List of performer data
        """
        limit = get_performer_limit()

        query = """
        query FindPerformers($filter: FindFilterType) {
            findPerformers(filter: $filter) {
                count
                performers {
                    id
                    name
                    disambiguation
                    gender
                    ethnicity
                    eye_color
                    hair_color
                    height
                    measurements {
                        cup_size
                        band_size
                        waist
                        hip
                    }
                    career_start_year
                    career_end_year
                    aliases
                    country
                    scene_count
                }
            }
        }
        """

        variables = {"filter": {"per_page": limit, "sort": "name", "direction": "ASC"}}

        try:
            result = self.execute_query(query, variables)
            performers_data = result["data"]["findPerformers"]
            performers = performers_data["performers"]

            logger.info(f"Retrieved {len(performers)} performers from local Stash")
            return performers

        except Exception as e:
            logger.error(f"Error fetching performers from local Stash: {e}")
            return []

    def get_all_scenes(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict]:
        """Get scenes from local Stash instance

        Args:
            limit: Optional limit for the number of scenes to return
            start_date: Optional start date for the search (YYYY-MM-DD)
            end_date: Optional end date for the search (YYYY-MM-DD)

        Returns:
            List of scenes
        """
        # Local Stash query structure
        query = """
        query FindScenes($filter: FindFilterType) {
            findScenes(filter: $filter) {
                count
                scenes {
                    id
                    title
                    organized
                    date
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
                # Date range for local Stash
                variables["filter"]["date"] = {
                    "value": f"{start_date} - {end_date}",
                    "modifier": "BETWEEN",
                }
            elif start_date:
                variables["filter"]["date"] = {
                    "value": start_date,
                    "modifier": "GREATER_THAN",
                }
            elif end_date:
                variables["filter"]["date"] = {
                    "value": end_date,
                    "modifier": "LESS_THAN",
                }

        try:
            result = self.execute_query(query, variables)
            scenes_data = result["data"]["findScenes"]
            scenes = scenes_data["scenes"]

            logger.info(f"Retrieved {len(scenes)} scenes from local Stash")
            return scenes

        except Exception as e:
            logger.error(f"Error fetching scenes from local Stash: {e}")
            return []

    def delete_scene(self, scene_id: str, delete_file: bool = True) -> bool:
        """Delete a scene from local Stash

        Args:
            scene_id: ID of the scene to delete
            delete_file: Whether to delete the file from disk

        Returns:
            True if deletion was successful
        """
        query = """
        mutation SceneDestroy($input: SceneDestroyInput!) {
            sceneDestroy(input: $input)
        }
        """

        variables = {
            "input": {"id": scene_id, "delete_file": delete_file, "delete_generated": True}
        }

        try:
            result = self.execute_query(query, variables)
            success = result["data"]["sceneDestroy"]

            if success:
                logger.info(f"Successfully deleted scene {scene_id}")
            else:
                logger.warning(f"Failed to delete scene {scene_id}")

            return success

        except Exception as e:
            logger.error(f"Error deleting scene {scene_id}: {e}")
            return False
