import requests
import logging

class WhisparrApi:
    """A class to interact with the Whisparr API."""

    def __init__(self, config):
        self.url = config.get('url')
        self.api_key = config.get('api_key')
        self.root_folder = config.get('root_folder')

    def _call_api(self, endpoint, method='GET', params=None, json=None):
        """A helper function to call the Whisparr API."""
        headers = {'X-Api-Key': self.api_key}
        full_url = f"{self.url}/api/v3/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(full_url, headers=headers, params=params)
            elif method == 'POST':
                response = requests.post(full_url, headers=headers, json=json)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error calling Whisparr API: {e}")
            return None

    def add_series(self, title, tvdb_id=None):
        """Adds a new series to Whisparr."""
        # First, lookup the series to get the TVDB ID if not provided
        if not tvdb_id:
            lookup_result = self._call_api('series/lookup', params={'term': title})
            if not lookup_result:
                logging.error(f"Could not find series '{title}' on TVDB.")
                return None
            
            # For simplicity, we'll take the first result.
            # In a real application, you might want to handle multiple results.
            if lookup_result:
                tvdb_id = lookup_result[0].get('tvdbId')
        
        if not tvdb_id:
            logging.error(f"Could not determine TVDB ID for '{title}'.")
            return None

        # Now, add the series
        series_data = {
            "title": title,
            "tvdbId": tvdb_id,
            "qualityProfileId": 1,  # This should be configured
            "rootFolderPath": self.root_folder,
            "addOptions": {
                "searchForMissingEpisodes": True
            }
        }
        
        return self._call_api('series', method='POST', json=series_data)
