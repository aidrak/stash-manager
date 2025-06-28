import requests
import logging

class StashDB:
    """A class to interact with the StashDB GraphQL API."""

    def __init__(self, config):
        self.url = config.get('url', 'https://stashdb.org/graphql')
        self.api_key = config.get('api_key')
        self.headers = {
            "Content-Type": "application/json",
            "ApiKey": self.api_key
        }

    def _call_graphql(self, query, variables=None):
        """A helper function to call the GraphQL API."""
        json_data = {'query': query}
        if variables:
            json_data['variables'] = variables
        
        try:
            response = requests.post(self.url, json=json_data, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error calling StashDB API: {e}")
            return None

    def find_scene_by_id(self, scene_id):
        """Finds a scene by its StashDB ID."""
        query = """
            query FindScene($id: ID!) {
                findScene(id: $id) {
                    id
                    title
                    details
                    url
                    date
                    studio {
                        id
                        name
                    }
                    performers {
                        id
                        name
                    }
                    tags {
                        id
                        name
                    }
                }
            }
        """
        variables = {"id": scene_id}
        result = self._call_graphql(query, variables)
        if result and 'data' in result and 'findScene' in result['data']:
            return result['data']['findScene']
        return None
