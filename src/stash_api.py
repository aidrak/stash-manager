"""
Simplified Stash API client for Stash Manager
"""

import logging
import time
import requests
from typing import Dict, List

from src.config import (
    get_job_timeout, get_poll_interval, get_scene_limit, get_performer_limit
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
        self.headers = {
            "Content-Type": "application/json",
            "ApiKey": api_key
        }
        logger.info(f"Initialized Stash API client for {url}")
    
    def execute_query(self, query: str, variables: Dict = None) -> Dict:
        """Execute a GraphQL query against the Stash API"""
        if variables is None:
            variables = {}
        
        payload = {
            "query": query,
            "variables": variables
        }
        
        try:
            logger.info(f"Sending GraphQL request to {self.graphql_url}")
            logger.debug(f"Payload: {payload}")
            
            response = requests.post(
                self.graphql_url,
                headers=self.headers,
                json=payload
            )
            
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
            logger.error(f"Response text: {response.text if 'response' in locals() else 'No response'}")
            raise Exception(f"API request failed: {str(e)}")
        except ValueError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            logger.error(f"Response text: {response.text if 'response' in locals() else 'No response'}")
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
                "scanGenerateImagePreviews": True,
                "scanGeneratePhashes": True,
                "scanGeneratePreviews": True,
                "scanGenerateSprites": True,
                "scanGenerateThumbnails": True
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
                "previews": False,
                "sprites": False,
                "transcodes": False
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
                    logger.info(f"Job {job_id} status: {job_status}, progress: {progress*100:.1f}%")
                
            except Exception as e:
                logger.error(f"Error checking job status: {str(e)}")
            
            # Wait before next check
            time.sleep(poll_interval)
        
        logger.error(f"Timeout waiting for job {job_id}")
        return False
    
    def trigger_identify(self, sources: List[str]) -> str:
        """Trigger metadata identification in Stash

        Args:
            sources: A list of source names like ["stashdb", "tpdb"]

        Returns:
            Job ID for the identify task
        """
        query = """
        mutation MetadataIdentify($input: IdentifyMetadataInput!) {
            metadataIdentify(input: $input)
        }
        """

        # Map source names to their GraphQL endpoints
        source_map = {
            "stashdb": "https://stashdb.org/graphql",
            "tpdb": "https://theporndb.net/graphql"
        }

        # Build the sources list for the GraphQL query
        query_sources = []
        for source_name in sources:
            if source_name in source_map:
                query_sources.append({
                    "source": {
                        "stash_box_endpoint": source_map[source_name]
                    }
                })

        variables = {
            "input": {
                "sources": query_sources,
                "options": {
                    "fieldOptions": [
                        {
                            "field": "title",
                            "strategy": "OVERWRITE",
                            "createMissing": True
                        },
                        {
                            "field": "performers",
                            "strategy": "MERGE",
                            "createMissing": True
                        },
                        {
                            "field": "tags",
                            "strategy": "MERGE",
                            "createMissing": True
                        }
                    ],
                    "setCoverImage": True,
                    "setOrganized": True,
                    "includeMalePerformers": True,
                    "skipMultipleMatches": True,
                    "skipSingleNamePerformers": True
                },
                "paths": []
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
        
        variables = {
            "input": {
                "dryRun": False
            }
        }
        
        try:
            result = self.execute_query(query, variables)
            job_id = result["data"]["metadataClean"]
            logger.info(f"Triggered clean with job ID: {job_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to trigger clean: {str(e)}")
            raise
    
    def get_all_scenes(self, limit: int = None, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Get all scenes from Stash or StashDB
            
        Args:
            limit: Optional limit for the number of scenes to return
            start_date: Optional start date for the search
            end_date: Optional end date for the search
            
        Returns:
            List of scenes
        """
        # Check if this is StashDB based on the URL
        is_stashdb = "stashdb.org" in self.url.lower()
        
        if is_stashdb:
            # StashDB query structure - measurements needs subfields
            query = """
            query QueryScenes($input: SceneQueryInput!) {
                queryScenes(input: $input) {
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
            
            per_page = limit if limit else 1000
            variables = {
                "input": {
                    "page": 1,
                    "per_page": per_page,
                    "sort": "DATE",
                    "direction": "DESC"
                }
            }
            if start_date and end_date:
                variables["input"]["date"] = {
                    "value": start_date,
                    "modifier": "GREATER_THAN"
                }
                variables["input"]["date_end"] = {
                    "value": end_date,
                    "modifier": "LESS_THAN"
                }
        else:
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
            variables = {
                "filter": {
                    "per_page": per_page
                }
            }
        
        try:
            result = self.execute_query(query, variables)
            
            if is_stashdb:
                # Extract scenes from StashDB response
                if "data" in result and "queryScenes" in result["data"] and "scenes" in result["data"]["queryScenes"]:
                    return result["data"]["queryScenes"]["scenes"]
            else:
                # Extract scenes from local Stash response
                if "data" in result and "findScenes" in result["data"] and "scenes" in result["data"]["findScenes"]:
                    return result["data"]["findScenes"]["scenes"]
            
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
        variables = {
            "filter": {
                "per_page": limit
            }
        }
        
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
                "delete_generated": True
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
