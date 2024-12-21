from ghunt.objects.base import GHuntCreds
from ghunt.errors import *
import ghunt.globals as gb
from ghunt.objects.apis import GAPI
from ghunt.parsers.people import Person

import httpx

from typing import *
import inspect
import json
import asyncio

class PeoplePaHttp(GAPI):
    def __init__(self, creds: GHuntCreds, headers: Dict[str, str] = {}):
        super().__init__()
        
        if not headers:
            headers = gb.config.headers

        base_headers = {}

        headers = {**headers, **base_headers}

        self.hostname = "people-pa.clients6.google.com"
        self.scheme = "https"

        self.authentication_mode = "sapisidhash" # sapisidhash, cookies_only, oauth or None
        self.require_key = "photos" # key name, or None

        self._load_api(creds, headers)

    async def people_lookup(self, as_client: httpx.AsyncClient, email: str, params_template="just_gaia_id") -> Tuple[bool, Person]:
        endpoint_name = inspect.currentframe().f_code.co_name

        verb = "GET"
        base_url = "/v2/people/lookup"
        data_type = None # json, data or None
        params_templates = {
            "just_gaia_id": {
                "id": email,
                "type": "EMAIL",
                "match_type": "EXACT",
                "request_mask.include_field.paths": "person.metadata",
                "request_mask.include_container": [
                    "PROFILE",
                    "DOMAIN_PROFILE",
                ],
            },
            "just_name": {
                "id": email,
                "type": "EMAIL",
                "match_type": "EXACT",
                "request_mask.include_field.paths": "person.name",
                "request_mask.include_container": [
                    "PROFILE",
                    "DOMAIN_PROFILE",
                ],
                "core_id_params.enable_private_names": True
            },
            "max_details": {
                "id": email,
                "type": "EMAIL",
                "match_type": "EXACT",
                "extension_set.extension_names": [
                    "DYNAMITE_ADDITIONAL_DATA",
                    "DYNAMITE_ORGANIZATION_INFO",
                    # "GPLUS_ADDITIONAL_DATA"
                ],
                "request_mask.include_field.paths": [
                    "person.metadata.best_display_name",
                    "person.photo",
                    "person.cover_photo",
                    "person.interaction_settings",
                    "person.legacy_fields",
                    "person.metadata",
                    # "person.in_app_reachability",
                    "person.name",
                    "person.read_only_profile_info",
                    "person.sort_keys",
                    "person.email"
                ],
                "request_mask.include_container": [
                    "AFFINITY",
                    "PROFILE",
                    "DOMAIN_PROFILE",
                    "ACCOUNT",
                    "EXTERNAL_ACCOUNT",
                    "CIRCLE",
                    "DOMAIN_CONTACT",
                    "DEVICE_CONTACT",
                    "GOOGLE_GROUP",
                    "CONTACT"
                ],
                "core_id_params.enable_private_names": True
            }
        }

        if not params_templates.get(params_template):
            raise GHuntParamsTemplateError(f"The asked template {params_template} for the endpoint {endpoint_name} wasn't recognized by GHunt.")

        self._load_endpoint(endpoint_name)
        req = await self._query(as_client, verb, endpoint_name, base_url, params_templates[params_template], None, data_type)

        # Parsing
        data = json.loads(req.text)
        person = Person()
        if not data:
            return False, person
        
        person_data = list(data["people"].values())[0]
        await person._scrape(as_client, person_data)

        return True, person
    
    
    async def bulk_people_lookup(self, as_client: httpx.AsyncClient, emails: List[str], params_template="just_gaia_id") -> List[Tuple[bool, Person]]:
        """
        Perform bulk lookup for multiple email addresses.
        
        Args:
            as_client: The HTTP client
            emails: List of email addresses to look up
            params_template: Template for the request parameters
            
        Returns:
            List of tuples containing (success_bool, Person_object)
        """
        results = []
        
        # Reference to params_templates
        if not self.loaded_endpoints.get("people_lookup"):
            self._load_endpoint("people_lookup")

        # Validate params template
        params_templates = {
            "just_gaia_id": {
                "type": "EMAIL",
                "match_type": "EXACT",
                "request_mask.include_field.paths": "person.metadata",
                "request_mask.include_container": [
                    "PROFILE",
                    "DOMAIN_PROFILE",
                ],
            },
            "just_name": {
                "type": "EMAIL",
                "match_type": "EXACT",
                "request_mask.include_field.paths": "person.name",
                "request_mask.include_container": [
                    "PROFILE",
                    "DOMAIN_PROFILE",
                ],
                "core_id_params.enable_private_names": True
            },
            "max_details": {
                "type": "EMAIL",
                "match_type": "EXACT",
                "extension_set.extension_names": [
                    "DYNAMITE_ADDITIONAL_DATA",
                    "DYNAMITE_ORGANIZATION_INFO",
                ],
                "request_mask.include_field.paths": [
                    "person.metadata.best_display_name",
                    "person.photo",
                    "person.cover_photo",
                    "person.interaction_settings",
                    "person.legacy_fields",
                    "person.metadata",
                    "person.name",
                    "person.read_only_profile_info",
                    "person.sort_keys",
                    "person.email"
                ],
                "request_mask.include_container": [
                    "AFFINITY",
                    "PROFILE",
                    "DOMAIN_PROFILE",
                    "ACCOUNT",
                    "EXTERNAL_ACCOUNT",
                    "CIRCLE",
                    "DOMAIN_CONTACT",
                    "DEVICE_CONTACT",
                    "GOOGLE_GROUP",
                    "CONTACT"
                ],
                "core_id_params.enable_private_names": True
            }
        }

        if not params_templates.get(params_template):
            raise GHuntParamsTemplateError(f"The asked template {params_template} wasn't recognized by GHunt.")

        # Process emails in parallel....
        async def process_single_email(email: str):
            params = {**params_templates[params_template], "id": email}
            try:
                req = await self._query(as_client, "GET", "people_lookup", "/v2/people/lookup", params, None, None)
                data = json.loads(req.text)
                person = Person()
                if not data:
                    return False, person
                
                person_data = list(data["people"].values())[0]
                await person._scrape(as_client, person_data)
                return True, person
            except Exception:
                return False, Person()

        tasks = [process_single_email(email) for email in emails]
        results = await asyncio.gather(*tasks)
        return results


    async def people(self, as_client: httpx.AsyncClient, gaia_id: str, params_template="just_name") -> Tuple[bool, Person]:
        endpoint_name = inspect.currentframe().f_code.co_name

        verb = "GET"
        base_url = "/v2/people"
        data_type = None # json, data or None
        params_templates = {
            "just_name": {
                "person_id": gaia_id,
                "request_mask.include_field.paths": "person.name",
                "request_mask.include_container": [
                    "PROFILE",
                    "DOMAIN_PROFILE",
                ],
                "core_id_params.enable_private_names": True
            },
            "max_details": {
                "person_id": gaia_id,
                "extension_set.extension_names": [
                    "DYNAMITE_ADDITIONAL_DATA",
                    "DYNAMITE_ORGANIZATION_INFO",
                    # "GPLUS_ADDITIONAL_DATA"
                ],
                "request_mask.include_field.paths": [
                    "person.metadata.best_display_name",
                    "person.photo",
                    "person.cover_photo",
                    "person.interaction_settings",
                    "person.legacy_fields",
                    "person.metadata",
                    # "person.in_app_reachability",
                    "person.name",
                    "person.read_only_profile_info",
                    "person.sort_keys",
                    "person.email"
                ],
                "request_mask.include_container": [
                    "AFFINITY",
                    "PROFILE",
                    "DOMAIN_PROFILE",
                    "ACCOUNT",
                    "EXTERNAL_ACCOUNT",
                    "CIRCLE",
                    "DOMAIN_CONTACT",
                    "DEVICE_CONTACT",
                    "GOOGLE_GROUP",
                    "CONTACT"
                ],
                "core_id_params.enable_private_names": True
            }
        }

        if not params_templates.get(params_template):
            raise GHuntParamsTemplateError(f"The asked template {params_template} for the endpoint {endpoint_name} wasn't recognized by GHunt.")

        self._load_endpoint(endpoint_name)
        req = await self._query(as_client, verb, endpoint_name, base_url, params_templates[params_template], None, data_type)

        # Parsing
        data = json.loads(req.text)
        person = Person()
        if data["personResponse"][0]["status"] == "NOT_FOUND":
            return False, person
        
        person_data = data["personResponse"][0]["person"]
        await person._scrape(as_client, person_data)

        return True, person
    
    
    async def bulk_people(self, as_client: httpx.AsyncClient, gaia_ids: List[str], params_template="just_name") -> List[Tuple[bool, Person]]:
        """
        Perform bulk lookup for multiple Gaia IDs.
        
        Args:
            as_client: The HTTP client
            gaia_ids: List of Gaia IDs to look up
            params_template: Template for the request parameters
            
        Returns:
            List of tuples containing (success_bool, Person_object)
        """
        # Reference to params_templates
        if not self.loaded_endpoints.get("people"):
            self._load_endpoint("people")

        params_templates = {
            "just_name": {
                "request_mask.include_field.paths": "person.name",
                "request_mask.include_container": [
                    "PROFILE",
                    "DOMAIN_PROFILE",
                ],
                "core_id_params.enable_private_names": True
            },
            "max_details": {
                "extension_set.extension_names": [
                    "DYNAMITE_ADDITIONAL_DATA",
                    "DYNAMITE_ORGANIZATION_INFO",
                ],
                "request_mask.include_field.paths": [
                    "person.metadata.best_display_name",
                    "person.photo",
                    "person.cover_photo",
                    "person.interaction_settings",
                    "person.legacy_fields",
                    "person.metadata",
                    "person.name",
                    "person.read_only_profile_info",
                    "person.sort_keys",
                    "person.email"
                ],
                "request_mask.include_container": [
                    "AFFINITY",
                    "PROFILE",
                    "DOMAIN_PROFILE",
                    "ACCOUNT",
                    "EXTERNAL_ACCOUNT",
                    "CIRCLE",
                    "DOMAIN_CONTACT",
                    "DEVICE_CONTACT",
                    "GOOGLE_GROUP",
                    "CONTACT"
                ],
                "core_id_params.enable_private_names": True
            }
        }

        if not params_templates.get(params_template):
            raise GHuntParamsTemplateError(f"The asked template {params_template} wasn't recognized by GHunt.")

        # Process the gaia IDs in parallel
        async def process_single_gaia(gaia_id: str):
            params = {**params_templates[params_template], "person_id": gaia_id}
            try:
                req = await self._query(as_client, "GET", "people", "/v2/people", params, None, None)
                data = json.loads(req.text)
                person = Person()
                if data["personResponse"][0]["status"] == "NOT_FOUND":
                    return False, person
                
                person_data = data["personResponse"][0]["person"]
                await person._scrape(as_client, person_data)
                return True, person
            except Exception:
                return False, Person()

        tasks = [process_single_gaia(gaia_id) for gaia_id in gaia_ids]
        results = await asyncio.gather(*tasks)
        return results