import logging
import urllib.parse

import requests


class WhisparrApi:
    """A class to interact with the Whisparr API."""

    def __init__(self, config):
        self.url = config.get("url")
        self.api_key = config.get("api_key")
        self.root_folder = config.get("root_folder", "/data")

    def _call_api(self, endpoint, method="GET", params=None, json=None):
        """A helper function to call the Whisparr API."""
        headers = {"X-Api-Key": self.api_key, "Content-Type": "application/json"}
        full_url = f"{self.url}/api/v3/{endpoint}"

        try:
            if method == "GET":
                response = requests.get(full_url, headers=headers, params=params)
            elif method == "POST":
                response = requests.post(full_url, headers=headers, json=json)

            response.raise_for_status()

            # Check if response has content and is JSON
            if response.content:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json()
                else:
                    logging.error(f"Whisparr API returned non-JSON response: {content_type}")
                    logging.error(f"Response content: {response.text[:500]}")
                    return None
            else:
                logging.warning("Whisparr API returned empty response")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error calling Whisparr API ({full_url}): {e}")
            return None
        except ValueError as e:
            logging.error(f"Error parsing JSON response from Whisparr API: {e}")
            logging.error(f"Response content: {response.text[:500]}")
            return None

    def search_scene(self, title):
        """Search for a scene in Whisparr's database."""
        encoded_title = urllib.parse.quote(title)
        search_url = f"lookup/scene?term={encoded_title}"

        result = self._call_api(search_url)

        if result and len(result) > 0:
            return result[0]  # Return first match
        else:
            return None

    def check_scene_exists(self, foreign_id):
        """Check if a scene already exists in Whisparr."""
        movies = self._call_api("movie")
        if movies:
            for movie in movies:
                if movie.get("foreignId") == foreign_id:
                    logging.info(f"Scene already exists in Whisparr: {movie.get('title')}")
                    return True
        return False

    def add_series(self, title):
        """Find scene in Whisparr database, check if exists, add if not, then search."""

        logging.info(f"Processing scene: {title}")

        # 1. Search Whisparr's database for the scene
        search_result = self.search_scene(title)

        if not search_result:
            logging.error(f"Scene '{title}' not found in Whisparr database")
            return None

        # 2. Extract scene data
        scene_data = search_result.get("movie", {})
        scene_title = scene_data.get("title")
        title_slug = scene_data.get("titleSlug")
        foreign_id = scene_data.get("foreignId")

        if not all([scene_title, foreign_id]):
            logging.error(f"Missing required data for scene '{title}'")
            return None

        # 3. Check if scene already exists
        if self.check_scene_exists(foreign_id):
            logging.info(f"Scene '{title}' already exists in Whisparr")
            return {"status": "already_exists", "title": scene_title}

        # 4. Add scene to Whisparr
        movie_payload = {
            "title": scene_title,
            "titleSlug": title_slug,
            "foreignId": foreign_id,
            "qualityProfileId": 1,
            "rootFolderPath": self.root_folder,
            "monitored": True,
            "addOptions": {
                "searchForMovie": True  # This triggers the search automatically
            },
        }

        result = self._call_api("movie", method="POST", json=movie_payload)

        if result and "id" in result:
            logging.info(f"Successfully added and searched for scene: {scene_title}")
            return {"status": "added", "title": scene_title, "id": result["id"]}
        else:
            logging.error(f"Failed to add scene '{title}' to Whisparr")
            return None
