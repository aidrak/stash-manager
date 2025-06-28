import requests
import logging

class StashApi:
    """A class to interact with the Stash GraphQL API."""

    def __init__(self, config):
        self.url = config.get('url')
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
            logging.error(f"Error calling Stash API: {e}")
            return None

    def find_scenes(self, limit=100, page=1):
        """Finds scenes in Stash."""
        query = """
            query FindScenes($filter: FindFilter, $scene_filter: SceneFilter, $scene_ids: [Int!]) {
                findScenes(filter: $filter, scene_filter: $scene_filter, scene_ids: $scene_ids) {
                    count
                    scenes {
                        id
                        title
                        details
                        url
                        date
                        rating
                        o_counter
                        organized
                        path
                        file {
                            size
                            duration
                            video_codec
                            audio_codec
                            width
                            height
                            framerate
                            bitrate
                        }
                        paths {
                            screenshot
                            preview
                            stream
                            webp
                            vtt
                            chapters_vtt
                            sprite
                        }
                        studio {
                            id
                            name
                            url
                            image_path
                            parent_studio {
                                id
                                name
                            }
                        }
                        galleries {
                            id
                            path
                            title
                        }
                        performers {
                            id
                            name
                            url
                            gender
                            twitter
                            instagram
                            birthdate
                            ethnicity
                            country
                            eye_color
                            height
                            measurements
                            fake_tits
                            career_length
                            tattoos
                            piercings
                            aliases
                            favorite
                            image_path
                        }
                        tags {
                            id
                            name
                        }
                    }
                }
            }
        """
        variables = {
            "filter": {
                "q": "",
                "page": page,
                "per_page": limit,
                "sort": "date",
                "direction": "DESC"
            }
        }
        
        result = self._call_graphql(query, variables)
        if result and 'data' in result and 'findScenes' in result['data']:
            return result['data']['findScenes']['scenes']
        return []
