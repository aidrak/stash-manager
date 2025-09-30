"""
Unified Stash API interface for backward compatibility
This maintains the same interface as the original StashAPI class
"""

from typing import Dict, List, Optional, Union

from src.api.local_stash_client import LocalStashClient
from src.api.stashdb_client import StashDBClient


class StashAPI:
    """Unified Stash API client that wraps StashDB and Local Stash clients"""

    def __init__(self, url: str, api_key: str):
        """Initialize the appropriate client based on URL

        Args:
            url: Base URL for the Stash API
            api_key: API key for authentication
        """
        self.url = url
        self.api_key = api_key

        # Determine client type based on URL
        if "stashdb.org" in url.lower():
            self._client: Union[StashDBClient, LocalStashClient] = StashDBClient(url, api_key)
            self._is_stashdb = True
        else:
            self._client = LocalStashClient(url, api_key)
            self._is_stashdb = False

    def execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute a GraphQL query"""
        return self._client.execute_query(query, variables)

    def get_job_status(self, job_id: str) -> Dict:
        """Get job status (local Stash only)"""
        if self._is_stashdb:
            raise NotImplementedError("Job status not available for StashDB")
        return self._client.get_job_status(job_id)

    def wait_for_job_completion(self, job_id: str) -> bool:
        """Wait for job completion (local Stash only)"""
        if self._is_stashdb:
            raise NotImplementedError("Job waiting not available for StashDB")
        if isinstance(self._client, LocalStashClient):
            return self._client.wait_for_job_completion(job_id)
        raise NotImplementedError("Job waiting not available for this client type")

    def trigger_scan(self) -> str:
        """Trigger metadata scan (local Stash only)"""
        if self._is_stashdb:
            raise NotImplementedError("Scan not available for StashDB")
        if isinstance(self._client, LocalStashClient):
            return self._client.trigger_scan()
        raise NotImplementedError("Scan not available for this client type")

    def trigger_generate(self) -> str:
        """Trigger metadata generation (local Stash only)"""
        if self._is_stashdb:
            raise NotImplementedError("Generate not available for StashDB")
        if isinstance(self._client, LocalStashClient):
            return self._client.trigger_generate()
        raise NotImplementedError("Generate not available for this client type")

    def trigger_identify(self) -> str:
        """Trigger scene identification (local Stash only)"""
        if self._is_stashdb:
            raise NotImplementedError("Identify not available for StashDB")
        if isinstance(self._client, LocalStashClient):
            return self._client.trigger_identify()
        raise NotImplementedError("Identify not available for this client type")

    def trigger_clean(self) -> str:
        """Trigger clean operation (local Stash only)"""
        if self._is_stashdb:
            raise NotImplementedError("Clean not available for StashDB")
        if isinstance(self._client, LocalStashClient):
            return self._client.trigger_clean()
        raise NotImplementedError("Clean not available for this client type")

    def get_all_scenes(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        direction: str = "ASC",
    ) -> List[Dict]:
        """Get all scenes - behavior depends on client type"""
        if self._is_stashdb and isinstance(self._client, StashDBClient):
            return self._client.get_all_scenes(limit, start_date, end_date, direction)
        elif isinstance(self._client, LocalStashClient):
            return self._client.get_all_scenes(limit, start_date, end_date)
        else:
            raise NotImplementedError("Scene listing not available for this client type")

    def get_performers(self) -> List[Dict]:
        """Get performers (local Stash only)"""
        if self._is_stashdb:
            raise NotImplementedError("Performers not available for StashDB")
        if isinstance(self._client, LocalStashClient):
            return self._client.get_performers()
        raise NotImplementedError("Performers not available for this client type")

    def delete_scene(self, scene_id: str, delete_file: bool = True) -> bool:
        """Delete scene (local Stash only)"""
        if self._is_stashdb:
            raise NotImplementedError("Scene deletion not available for StashDB")
        if isinstance(self._client, LocalStashClient):
            return self._client.delete_scene(scene_id, delete_file)
        raise NotImplementedError("Scene deletion not available for this client type")
