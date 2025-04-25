import os
import sys
import json
import time
from datetime import datetime as dt
from typing import Any, Dict

project_root = os.environ["PROJECT_ROOT"]
sys.path.append(f"{project_root}")
from logger import get_logger

logger = get_logger()

import time
import json
import logging
from typing import Dict, Any, List
from datetime import datetime as dt
from collections import defaultdict

logger = logging.getLogger(__name__)


class TargetProfile:
    """
    Represents a profile of a target domain, tracking API calls, navigation, pages, and cookies.

    Attributes:
        domain (str): The domain being tracked.
        interval (int): Interval for periodic saves.
        profile (dict): Stores tracked details like API calls, navigation, pages, and cookies.
        answer (str): Stores a generated answer related to the target profile.
        last_update_time (float): Timestamp of the last profile update.
    """

    def __init__(self, domain: str, interval: int = 60):
        self.domain = domain
        self.interval = interval
        self.profile = {
            "domain": domain,
            "api_calls": [],
            "pages_and_paths": [],
            "navigation": [],
            "cookies": [],
            "server_info": {},
        }
        self.answer = ""
        self.last_update_time = time.time()


    def get_summary(self) -> Dict[str, Any]:
        """
        Generates a summary of the tracked profile.

        Returns:
            dict: A summary containing page visits, API calls, navigation events, and cookies.
        """
        try:
            summary = {
                "domain": self.domain,
                "pages_visited": len(self.profile.get("pages_and_paths", [])),
                "api_calls": len(self.profile.get("api_calls", [])),
                "navigation_events": len(self.profile.get("navigation", [])),
                "cookies": len(self.profile.get("cookies", {})),
            }

            # Recent pages (last 5 visited)
            if self.profile.get("pages_and_paths"):
                summary["recent_pages"] = [
                    page["url"] for page in self.profile["pages_and_paths"][-5:]
                ]

            # API Call Summary
            if self.profile.get("api_calls"):
                api_summary = defaultdict(lambda: {"count": 0, "methods": set()})
                for call in self.profile["api_calls"]:
                    endpoint = call.get("endpoint", "Unknown")
                    method = call.get("method", "Unknown")
                    api_summary[endpoint]["count"] += 1
                    api_summary[endpoint]["methods"].add(method)

                summary["api_summary"] = [
                    {"endpoint": k, "count": v["count"], "methods": list(v["methods"])}
                    for k, v in api_summary.items()
                ]

            # Server Info
            if self.profile.get("server_info"):
                summary["server_info"] = self.profile["server_info"]

            logger.info(f"Profile summary generated: {summary}")
            return summary

        except Exception as e:
            logger.error(f"Error in get_summary: {e}", exc_info=True)
            return {}


    def __str__(self) -> str:
        return f"TargetProfile(domain={self.domain}, profile={self.profile})"


    def to_dict(self, session_id: str) -> Dict[str, Any]:
        """
        Converts the profile to a dictionary format.

        Args:
            session_id (str): Unique identifier for the session.

        Returns:
            dict: A dictionary representation of the profile.
        """
        try:
            return {
                "session_id": session_id,
                "domain": self.domain,
                "api_calls": self.profile.get("api_calls", []),
                "pages_and_paths": self.profile.get("pages_and_paths", []),
                "navigation": self.profile.get("navigation", []),
                "cookies": self.profile.get("cookies", {}),
                "server_info": self.profile.get("server_info", {}),
                "last_update_time": dt.fromtimestamp(self.last_update_time).isoformat(),
            }
        except Exception as e:
            logger.error(f"Error in to_dict: {e}", exc_info=True)
            return {}


    def add_api_call(
        self,
        endpoint: str,
        method: str,
        request_headers: dict,
        request_body: str,
        response_headers: dict,
        response_body: str,
        status_code: int,
    ):
        """
        Logs an API call in the profile.

        Args:
            endpoint (str): API endpoint.
            method (str): HTTP method used.
            request_headers (dict): Request headers.
            request_body (str): Request payload.
            response_headers (dict): Response headers.
            response_body (str): Response content.
            status_code (int): HTTP status code.
        """
        try:
            api_call = {
                "timestamp": time.time(),
                "endpoint": endpoint,
                "method": method,
                "request_headers": request_headers,
                "request_body": request_body,
                "response_headers": response_headers,
                "response_body": response_body,
                "status_code": status_code,
            }

            if "api_calls" not in self.profile:
                self.profile["api_calls"] = []

            self.profile["api_calls"].append(api_call)
            logger.info(f"API call added: {endpoint} [{method}] | Status: {status_code}")
            self._maybe_save()

        except Exception as e:
            logger.error(f"Error in add_api_call: {e}", exc_info=True)



    def add_page(
        self,
        url: str,
        title: str,
        description: str,
        purpose: str,
        user_inputs: List[Any],
        credentials: List[Any],
    ):
        """
        Adds a visited page to the profile.

        Args:
            url (str): Page URL.
            title (str): Page title.
            description (str): Page description.
            purpose (str): Purpose of the page.
            user_inputs (list): User interactions with the page.
            credentials (list): Credentials associated with the page.
        """
        try:
            if "pages_and_paths" not in self.profile:
                self.profile["pages_and_paths"] = []

            page = {
                "url": url,
                "page_summary": {
                    "title": title,
                    "description": description,
                    "purpose": purpose,
                    "user_inputs": user_inputs or [],
                },
                "credentials": credentials or [],
            }

            self.profile["pages_and_paths"].append(page)
            logger.info(f"Page added: {url} | Title: {title}")
            self._maybe_save()

        except Exception as e:
            logger.error(f"Error in add_page: {e}", exc_info=True)


    def add_cookies(self, cookies: Dict[str, Any]):
        """
        Adds cookies to the profile.

        Args:
            cookies (dict): Cookie data.
        """
        try:
            if not isinstance(cookies, dict):
                logger.error("Invalid cookie format. Expected a dictionary.")
                return

            self.profile["cookies"] = cookies
            logger.info(f"Cookies added: {list(cookies.keys())}")
            self._maybe_save()

        except Exception as e:
            logger.error(f"Error in add_cookies: {e}", exc_info=True)


    def add_server_info(self, server_info: Dict[str, Any]):
        """
        Adds server information to the profile.

        Args:
            server_info (dict): Server-related metadata.
        """
        try:
            if not isinstance(server_info, dict):
                logger.error("Invalid server info format. Expected a dictionary.")
                return

            self.profile["server_info"] = server_info
            logger.info("Server information updated.")
            self._maybe_save()

        except Exception as e:
            logger.error(f"Error in add_server_info: {e}", exc_info=True)


    def add_navigation(self, url: str, navigation_type: str):
        """
        Logs navigation events.

        Args:
            url (str): Navigated URL.
            navigation_type (str): Type of navigation (e.g., click, redirect).
        """
        try:
            if "navigation" not in self.profile:
                self.profile["navigation"] = []

            navigation = {
                "url": url,
                "navigation_type": navigation_type,
                "timestamp": time.time(),
            }

            self.profile["navigation"].append(navigation)
            logger.info(f"Navigation logged: {navigation}")
            self._maybe_save()

        except Exception as e:
            logger.error(f"Error in add_navigation: {e}", exc_info=True)



    def update_api_call(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_headers: dict,
        response_body: str,
        request_body: str,
        request_headers: dict,
    ):
        """
        Updates an existing API call or adds a new one if not found.

        Args:
            endpoint (str): API endpoint.
            method (str): HTTP method.
            status_code (int): HTTP status code.
            response_headers (dict): Response headers.
            response_body (str): Response payload.
            request_body (str): Request payload.
            request_headers (dict): Request headers.
        """
        try:
            if "api_calls" not in self.profile:
                self.profile["api_calls"] = []

            for api_call in self.profile["api_calls"]:
                if api_call["endpoint"] == endpoint and api_call["method"] == method:
                    api_call.update({
                        "status_code": status_code,
                        "response_headers": response_headers or {},
                        "response_body": response_body or "",
                        "request_body": request_body or "",
                        "request_headers": request_headers or {},
                    })
                    logger.info(f"Updated existing API call: {endpoint} [{method}]")
                    self._maybe_save()
                    return

            # If no existing API call matches, add a new one
            self.add_api_call(endpoint, method, request_headers, request_body, response_headers, response_body, status_code)
            logger.info(f"Added new API call: {endpoint} [{method}]")

        except Exception as e:
            logger.error(f"Error in update_api_call: {e}", exc_info=True)


    def set_answer(self, answer: str):
        """
        Stores an answer related to the profile.

        Args:
            answer (str): The generated answer.
        """
        try:
            if not isinstance(answer, str):
                logger.error("Invalid answer type: Expected string.")
                return

            self.answer = answer
            logger.info(f"Answer set successfully: {answer[:50]}...")  # Log only first 50 chars to avoid long logs
            self._maybe_save()
        
        except Exception as e:
            logger.error(f"Error in set_answer: {e}", exc_info=True)


    def _maybe_save(self):
        """
        Saves the profile if the update interval has passed.
        """
        try:
            current_time = time.time()
            if not hasattr(self, "last_update_time"):
                self.last_update_time = 0  # Initialize if not set

            if current_time - self.last_update_time >= getattr(self, "interval", 60):  # Default interval = 60s
                self.save()
                self.last_update_time = current_time
                logger.info("Profile saved due to update interval.")

        except Exception as e:
            logger.error(f"Error in _maybe_save: {e}", exc_info=True)

    def save(self):
        """
        Saves the profile data to a JSON file safely.
        """
        try:
            if not hasattr(self, "profile") or not isinstance(self.profile, dict):
                logger.error("Profile data is missing or invalid.")
                return

            filename = f"{self.domain}_profile.json"

            # Ensure the directory exists
            os.makedirs(os.path.dirname(filename), exist_ok=True)

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.profile, f, indent=4)

            logger.info(f"Profile successfully saved to {filename}")

        except FileNotFoundError as e:
            logger.error(f"FileNotFoundError: {e}", exc_info=True)
        except PermissionError as e:
            logger.error(f"PermissionError: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in save: {e}", exc_info=True)

    def add_request_headers(self, headers: Dict[str, Any]):
        """
        Logs request headers safely.

        Args:
            headers (dict): HTTP request headers.
        """
        try:
            if not isinstance(headers, dict):
                logger.error(f"Invalid headers type: expected dict, got {type(headers)}")
                return

            if "request_headers" not in self.profile:
                self.profile["request_headers"] = []

            self.profile["request_headers"].append(headers)
            self._maybe_save()

            logger.debug(f"Added request headers: {headers}")

        except AttributeError as e:
            logger.error(f"AttributeError in add_request_headers: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error in add_request_headers: {e}", exc_info=True)

