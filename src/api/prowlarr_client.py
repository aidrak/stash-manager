"""
Prowlarr API client for torrent searching and downloading
"""

import logging
from typing import Dict, List, Optional

import requests

logger = logging.getLogger("stash_manager.prowlarr_client")


class ProwlarrClient:
    """Client for interacting with Prowlarr API for torrent searching"""

    def __init__(self, config):
        self.url = config.get("url")
        self.api_key = config.get("api_key")

        if not self.url or not self.api_key:
            raise ValueError("Prowlarr URL and API key are required")

        # Remove trailing slash from URL
        self.url = self.url.rstrip("/")

        # Default to adult content categories for scene searching
        self.default_categories = config.get(
            "categories", "6000,6010,6020,6030,6040,6050,6060,6070"
        )

    def _call_api(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make API call to Prowlarr"""
        headers = {"X-Api-Key": self.api_key}
        full_url = f"{self.url}/api/v1/{endpoint}"

        try:
            response = requests.get(full_url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling Prowlarr API: {e}")
            return None

    def _search_indexer(self, indexer_id: int, query: str, categories: str = None) -> List[Dict]:
        """Search a specific indexer using Newznab/Torznab format"""
        if not categories:
            categories = self.default_categories

        # Use Newznab/Torznab search endpoint for specific indexer
        params = {"t": "search", "q": query, "cat": categories, "apikey": self.api_key}

        search_url = f"{self.url}/{indexer_id}/api"

        try:
            response = requests.get(search_url, params=params, timeout=30)
            response.raise_for_status()

            # Parse XML response (Newznab/Torznab returns XML)
            from xml.etree import ElementTree as ET

            root = ET.fromstring(response.content)

            results = []
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                size_elem = item.find(
                    ".//{http://www.newznab.com/DTD/2010/feeds/attributes/}attr[@name='size']"
                )
                seeders_elem = item.find(
                    ".//{http://www.newznab.com/DTD/2010/feeds/attributes/}attr[@name='seeders']"
                )
                peers_elem = item.find(
                    ".//{http://www.newznab.com/DTD/2010/feeds/attributes/}attr[@name='peers']"
                )

                if title_elem is not None and link_elem is not None:
                    result = {
                        "title": title_elem.text,
                        "download_url": link_elem.text,
                        "indexer_id": indexer_id,
                        "size": (int(size_elem.get("value", 0)) if size_elem is not None else 0),
                        "seeders": (
                            int(seeders_elem.get("value", 0)) if seeders_elem is not None else 0
                        ),
                        "peers": (int(peers_elem.get("value", 0)) if peers_elem is not None else 0),
                    }
                    results.append(result)

            logger.debug(
                f"Found {len(results)} results from indexer {indexer_id} for query '{query}'"
            )
            return results

        except Exception as e:
            logger.error(f"Error searching indexer {indexer_id}: {e}")
            return []

    def get_indexers(self) -> List[Dict]:
        """Get list of available indexers"""
        indexers = self._call_api("indexer")
        if indexers:
            # Filter to only enabled torrent indexers
            torrent_indexers = [
                idx
                for idx in indexers
                if idx.get("enable", False) and idx.get("protocol") == "torrent"
            ]
            logger.info(f"Found {len(torrent_indexers)} enabled torrent indexers")
            return torrent_indexers
        return []

    def search_scene(self, scene_title: str, max_results_per_indexer: int = 5) -> List[Dict]:
        """
        Search for a scene across all enabled torrent indexers

        Args:
            scene_title: Title of the scene to search for
            max_results_per_indexer: Maximum results to return per indexer

        Returns:
            List of search results with torrent information
        """
        logger.info(f"Searching for scene: '{scene_title}'")

        # Get enabled torrent indexers
        indexers = self.get_indexers()
        if not indexers:
            logger.warning("No enabled torrent indexers found")
            return []

        all_results = []

        # Search each indexer
        for indexer in indexers:
            indexer_id = indexer.get("id")
            indexer_name = indexer.get("name", f"Indexer {indexer_id}")

            logger.debug(f"Searching indexer: {indexer_name} (ID: {indexer_id})")

            try:
                results = self._search_indexer(indexer_id, scene_title)

                # Add indexer info to results
                for result in results[:max_results_per_indexer]:
                    result["indexer_name"] = indexer_name
                    result["indexer_id"] = indexer_id
                    all_results.append(result)

                if results:
                    logger.info(f"Found {len(results)} results from {indexer_name}")

            except Exception as e:
                logger.error(f"Error searching {indexer_name}: {e}")
                continue

        # Sort by seeders (descending) and size (descending for quality)
        all_results.sort(key=lambda x: (x.get("seeders", 0), x.get("size", 0)), reverse=True)

        logger.info(f"Total search results for '{scene_title}': {len(all_results)}")
        return all_results

    def download_torrent(self, download_url: str, indexer_id: int) -> bool:
        """
        Download torrent via Prowlarr (which will send to configured download client)

        Args:
            download_url: URL to download the torrent
            indexer_id: ID of the indexer

        Returns:
            True if download was initiated successfully
        """
        try:
            # Use Prowlarr's download endpoint to send to configured download client
            data = {"indexerId": indexer_id, "downloadUrl": download_url}

            headers = {"X-Api-Key": self.api_key, "Content-Type": "application/json"}
            response = requests.post(
                f"{self.url}/api/v1/download",
                headers=headers,
                json=data,
                timeout=30,
            )

            if response.status_code == 200:
                logger.info(f"Successfully sent download to client: {download_url}")
                return True
            else:
                logger.error(
                    f"Failed to download torrent: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error downloading torrent: {e}")
            return False

    def test_connection(self) -> bool:
        """Test connection to Prowlarr"""
        try:
            result = self._call_api("system/status")
            if result:
                logger.info(
                    f"Successfully connected to Prowlarr: {result.get('appName', 'Unknown')} "
                    f"v{result.get('version', 'Unknown')}"
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Prowlarr: {e}")
            return False

    def get_best_result(
        self,
        results: List[Dict],
        min_seeders: int = 1,
        max_size_gb: float = 10.0,
    ) -> Optional[Dict]:
        """
        Get the best torrent result based on quality criteria

        Args:
            results: List of search results
            min_seeders: Minimum number of seeders required
            max_size_gb: Maximum file size in GB

        Returns:
            Best torrent result or None if no suitable result found
        """
        if not results:
            return None

        max_size_bytes = max_size_gb * 1024 * 1024 * 1024

        # Filter results by criteria
        filtered_results = [
            r
            for r in results
            if r.get("seeders", 0) >= min_seeders and r.get("size", 0) <= max_size_bytes
        ]

        if not filtered_results:
            logger.warning(
                f"No results meet criteria (min_seeders={min_seeders}, max_size_gb={max_size_gb})"
            )
            return None

        # Return the first result (already sorted by seeders/size)
        best = filtered_results[0]
        logger.info(
            f"Selected best result: '{best.get('title')}' from {best.get('indexer_name')} "
            f"({best.get('seeders')} seeders, "
            f"{best.get('size', 0) / (1024 * 1024 * 1024):.2f} GB)"
        )

        return best
