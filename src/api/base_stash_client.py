"""
Base GraphQL client for Stash API operations
"""

import logging
from typing import Dict, Optional

import requests

logger = logging.getLogger("stash_manager.api")


class BaseStashClient:
    """Base client for GraphQL operations with Stash API"""

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

    def get_job_status(self, job_id: str) -> Dict:
        """Get the status of a job

        Args:
            job_id: Job ID to check

        Returns:
            Job status information
        """
        query = """
        query FindJob($input: FindJobInput!) {
            findJob(input: $input) {
                id
                status
                subTasks {
                    status
                    description
                }
                description
                progress
                error
            }
        }
        """

        variables = {"input": {"id": job_id}}

        try:
            result = self.execute_query(query, variables)
            job_data = result["data"]["findJob"]

            if not job_data:
                logger.warning(f"Job {job_id} not found")
                return {"status": "NOT_FOUND"}

            return job_data

        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return {"status": "ERROR", "error": str(e)}
