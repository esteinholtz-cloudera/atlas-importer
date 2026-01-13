"""Cloudera Atlas REST API client for glossary operations"""

import logging
from typing import Dict, List, Tuple, Optional
import requests
from requests.auth import HTTPBasicAuth
from models import Glossary, Category, Term

logger = logging.getLogger(__name__)


class AtlasClient:
    """REST client for Cloudera Atlas Glossary API"""
    
    def __init__(self, base_url: str, username: str, password: str, verify_ssl: bool = True, timeout: int = 30):
        """Initialize Atlas client with connection details"""
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.session.verify = verify_ssl
        self.session.timeout = timeout
        self.session.headers.update({"Content-Type": "application/json"})
        
        logger.info(f"Initialized AtlasClient for {self.base_url}")
    
    def _handle_response(self, response: requests.Response, operation: str) -> Optional[Dict]:
        """Handle API response and raise exceptions for errors"""
        try:
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_msg = error_data.get("errorMessage", response.text)
                except:
                    error_msg = response.text
                
                raise Exception(
                    f"Atlas API error ({response.status_code}) during {operation}: {error_msg}"
                )
            
            if response.status_code == 204:  # No content
                return None
            
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error during {operation}: {str(e)}")
    
    def test_connection(self) -> bool:
        """Test connectivity to Atlas server"""
        try:
            url = f"{self.base_url}/api/atlas/v2/types/typedefs"
            response = self.session.get(url)
            if response.status_code == 200:
                logger.info("✓ Successfully connected to Atlas server")
                return True
            else:
                logger.error(f"Failed to connect to Atlas: HTTP {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to Atlas: {str(e)}")
            return False
    
    def create_glossaries(self, glossaries: Dict[str, Glossary]) -> Dict[str, str]:
        """Create glossaries and return mapping of name -> GUID"""
        import sys
        guid_map = {}
        
        for gloss_name, glossary in glossaries.items():
            try:
                url = f"{self.base_url}/api/atlas/v2/glossary"
                payload = {
                    "name": glossary.name,
                }
                
                # Log API call
                import json
                sys.stderr.write(f"\n→ POST {url}\n")
                sys.stderr.write(f"  {json.dumps(payload, indent=2)}\n")
                sys.stderr.flush()
                
                logger.debug(f"Creating glossary: {payload}")
                response = self.session.post(url, json=payload)
                
                # Handle 409 (glossary already exists)
                if response.status_code == 409:
                    logger.info(f"ℹ Glossary '{gloss_name}' already exists, fetching GUID...")
                    # Try to find the glossary by name
                    guid = self._get_glossary_guid_by_name(gloss_name)
                    if guid:
                        guid_map[gloss_name] = guid
                        glossary.guid = guid
                        logger.info(f"✓ Found existing glossary '{gloss_name}' with GUID: {guid}")
                        sys.stderr.write(f"  ← Found existing: {guid}\n")
                        sys.stderr.flush()
                        continue
                    else:
                        raise Exception(f"Glossary '{gloss_name}' exists but could not retrieve GUID")
                
                result = self._handle_response(response, f"create glossary '{gloss_name}'")
                
                if result:
                    guid = result.get("guid")
                    if guid:
                        guid_map[gloss_name] = guid
                        glossary.guid = guid
                        logger.info(f"✓ Created glossary '{gloss_name}' with GUID: {guid}")
                        sys.stderr.write(f"  ← Response: {guid}\n")
                        sys.stderr.flush()
                    else:
                        logger.error(f"No GUID returned for glossary '{gloss_name}'")
                        raise Exception(f"No GUID returned for glossary '{gloss_name}'")
            except Exception as e:
                logger.error(f"Failed to create glossary '{gloss_name}': {str(e)}")
                raise
        
        return guid_map
    
    def create_categories(
        self,
        categories: Dict[Tuple[str, str], Category],
        glossary_guid_map: Dict[str, str]
    ) -> Dict[Tuple[str, str], str]:
        """Create categories in dependency order (parents first) and return mapping of (glossary, name) -> GUID"""
        guid_map = {}
        processed = set()
        
        def process_category(gloss_name: str, cat_name: str) -> Optional[str]:
            """Process a category and its parent recursively"""
            key = (gloss_name, cat_name)
            
            # Already processed
            if key in processed:
                return guid_map.get(key)
            
            category = categories[key]
            parent_guid = None
            
            # Process parent category first if it exists
            if category.parent_category_name:
                parent_key = (gloss_name, category.parent_category_name)
                if parent_key in categories:
                    parent_guid = process_category(gloss_name, category.parent_category_name)
                else:
                    logger.error(f"Parent category not found: {gloss_name}.{category.parent_category_name}")
                    raise Exception(f"Parent category not found: {gloss_name}.{category.parent_category_name}")
            
            # Create this category
            try:
                import sys, json
                url = f"{self.base_url}/api/atlas/v2/glossary/category"
                glossary_guid = glossary_guid_map[gloss_name]
                
                payload = {
                    "name": category.name,
                    "anchor": {"glossaryGuid": glossary_guid}
                }
                
                if category.short_description:
                    payload["shortDescription"] = category.short_description
                if category.long_description:
                    payload["longDescription"] = category.long_description
                if parent_guid:
                    payload["parentCategory"] = {"categoryGuid": parent_guid}
                
                # Log API call
                sys.stderr.write(f"\n→ POST {url}\n")
                sys.stderr.write(f"  {json.dumps(payload, indent=2)}\n")
                sys.stderr.flush()
                
                logger.debug(f"Creating category: {payload}")
                response = self.session.post(url, json=payload)
                
                # Handle 409 (category already exists)
                if response.status_code == 409:
                    logger.info(f"ℹ Category '{gloss_name}.{cat_name}' already exists, fetching GUID...")
                    guid = self._get_category_guid_by_name(gloss_name, cat_name)
                    if guid:
                        guid_map[key] = guid
                        category.guid = guid
                        processed.add(key)
                        logger.info(f"✓ Found existing category '{gloss_name}.{cat_name}' with GUID: {guid}")
                        sys.stderr.write(f"  ← Found existing: {guid}\n")
                        sys.stderr.flush()
                        return guid
                    else:
                        raise Exception(f"Category '{gloss_name}.{cat_name}' exists but could not retrieve GUID")
                
                result = self._handle_response(response, f"create category '{gloss_name}.{cat_name}'")
                
                if result:
                    guid = result.get("guid")
                    if guid:
                        guid_map[key] = guid
                        category.guid = guid
                        processed.add(key)
                        logger.info(f"✓ Created category '{gloss_name}.{cat_name}' with GUID: {guid}")
                        sys.stderr.write(f"  ← Response: {guid}\n")
                        sys.stderr.flush()
                        return guid
                    else:
                        logger.error(f"No GUID returned for category '{gloss_name}.{cat_name}'")
                        raise Exception(f"No GUID returned for category '{gloss_name}.{cat_name}'")
            except Exception as e:
                logger.error(f"Failed to create category '{gloss_name}.{cat_name}': {str(e)}")
                raise
        
        # Process all categories in dependency order
        for (gloss_name, cat_name) in categories.keys():
            if (gloss_name, cat_name) not in processed:
                process_category(gloss_name, cat_name)
        
        return guid_map
    
    def create_terms(
        self,
        terms: Dict[Tuple[str, str], Term],
        glossary_guid_map: Dict[str, str],
        category_guid_map: Dict[Tuple[str, str], str]
    ) -> Dict[Tuple[str, str], str]:
        """Create terms and return mapping of (glossary, name) -> GUID"""
        guid_map = {}
        
        # Group terms by glossary for batch creation
        terms_by_glossary: Dict[str, List[Tuple[Tuple[str, str], Term]]] = {}
        for key, term in terms.items():
            gloss_name = term.glossary_name
            if gloss_name not in terms_by_glossary:
                terms_by_glossary[gloss_name] = []
            terms_by_glossary[gloss_name].append((key, term))
        
        # Create terms for each glossary
        for gloss_name, gloss_terms in terms_by_glossary.items():
            try:
                import sys, json
                url = f"{self.base_url}/api/atlas/v2/glossary/terms"
                glossary_guid = glossary_guid_map[gloss_name]
                
                payloads = []
                term_keys = []
                
                for key, term in gloss_terms:
                    payload = {
                        "name": term.name,
                        "anchor": {"glossaryGuid": glossary_guid},
                        "status": term.status
                    }
                    
                    if term.short_description:
                        payload["shortDescription"] = term.short_description
                    if term.long_description:
                        payload["longDescription"] = term.long_description
                    if term.abbreviation:
                        payload["abbreviation"] = term.abbreviation
                    if term.steward:
                        payload["steward"] = term.steward
                    if term.examples:
                        payload["examples"] = term.examples.split(",") if isinstance(term.examples, str) else term.examples
                    
                    # Add category associations
                    if term.category_names:
                        category_guids = []
                        for cat_name in term.category_names:
                            cat_key = (gloss_name, cat_name)
                            if cat_key in category_guid_map:
                                category_guids.append({"categoryGuid": category_guid_map[cat_key]})
                        if category_guids:
                            payload["categories"] = category_guids
                    
                    payloads.append(payload)
                    term_keys.append(key)
                
                if payloads:
                    # Log API call
                    sys.stderr.write(f"\n→ POST {url} (batch: {len(payloads)} terms)\n")
                    sys.stderr.write(f"  {json.dumps(payloads, indent=2)}\n")
                    sys.stderr.flush()
                    
                    logger.debug(f"Creating {len(payloads)} terms for glossary '{gloss_name}'")
                    response = self.session.post(url, json=payloads)
                    
                    # Handle 409 (terms already exist) - fetch existing GUIDs
                    if response.status_code == 409:
                        logger.info(f"ℹ Some terms in glossary '{gloss_name}' already exist, fetching GUIDs...")
                        for key, term in zip(term_keys, payloads):
                            guid = self._get_term_guid_by_name(gloss_name, term["name"])
                            if guid:
                                guid_map[key] = guid
                                terms[key].guid = guid
                                logger.info(f"✓ Found existing term '{key[0]}.{key[1]}' with GUID: {guid}")
                                sys.stderr.write(f"  ← Found existing: {key[0]}.{key[1]} = {guid}\n")
                                sys.stderr.flush()
                            else:
                                logger.warning(f"Could not fetch GUID for existing term '{key[0]}.{key[1]}'")
                    else:
                        results = self._handle_response(response, f"create terms for glossary '{gloss_name}'")
                        
                        if results:
                            for i, result in enumerate(results):
                                guid = result.get("guid")
                                if guid:
                                    key = term_keys[i]
                                    guid_map[key] = guid
                                    terms[key].guid = guid
                                    logger.info(f"✓ Created term '{key[0]}.{key[1]}' with GUID: {guid}")
                                    sys.stderr.write(f"  ← Response: {key[0]}.{key[1]} = {guid}\n")
                                    sys.stderr.flush()
                            else:
                                key = term_keys[i]
                                logger.error(f"No GUID returned for term '{key[0]}.{key[1]}'")
            except Exception as e:
                logger.error(f"Failed to create terms for glossary '{gloss_name}': {str(e)}")
                raise
        
        return guid_map
    
    def update_term_relationships(
        self,
        term_guid_map: Dict[Tuple[str, str], str],
        terms: Dict[Tuple[str, str], Term]
    ) -> None:
        """Update all term relationships"""
        for key, term in terms.items():
            if key not in term_guid_map:
                logger.warning(f"Term '{key[0]}.{key[1]}' not found in GUID map, skipping relationship update")
                continue
            
            term_guid = term_guid_map[key]
            
            # Build relationship payload
            payload = {}
            
            # Convert qualified names to GUIDs
            if term.synonyms:
                payload["synonyms"] = [{"termGuid": self._resolve_term_guid(syn, term_guid_map)} for syn in term.synonyms]
            if term.antonyms:
                payload["antonyms"] = [{"termGuid": self._resolve_term_guid(ant, term_guid_map)} for ant in term.antonyms]
            if term.related_terms:
                payload["relatedTerms"] = [{"termGuid": self._resolve_term_guid(rel, term_guid_map)} for rel in term.related_terms]
            if term.preferred_terms:
                payload["preferredTerms"] = [{"termGuid": self._resolve_term_guid(pref, term_guid_map)} for pref in term.preferred_terms]
            if term.replacement_terms:
                payload["replacementTerms"] = [{"termGuid": self._resolve_term_guid(repl, term_guid_map)} for repl in term.replacement_terms]
            if term.see_also:
                payload["seeAlso"] = [{"termGuid": self._resolve_term_guid(see, term_guid_map)} for see in term.see_also]
            if term.is_a:
                payload["isA"] = [{"termGuid": self._resolve_term_guid(isa, term_guid_map)} for isa in term.is_a]
            if term.classifies:
                payload["classifies"] = [{"termGuid": self._resolve_term_guid(cls, term_guid_map)} for cls in term.classifies]
            
            if payload:
                try:
                    import sys, json
                    url = f"{self.base_url}/api/atlas/v2/glossary/term/{term_guid}"
                    
                    # Log API call
                    sys.stderr.write(f"\n→ PATCH {url}\n")
                    sys.stderr.write(f"  {json.dumps(payload, indent=2)}\n")
                    sys.stderr.flush()
                    
                    logger.debug(f"Updating relationships for term {term_guid}")
                    response = self.session.patch(url, json=payload)
                    self._handle_response(response, f"update relationships for term '{key[0]}.{key[1]}'")
                    logger.info(f"✓ Updated relationships for term '{key[0]}.{key[1]}'")
                    
                    sys.stderr.write(f"  ← Response: Updated\n")
                    sys.stderr.flush()
                except Exception as e:
                    logger.error(f"Failed to update relationships for term '{key[0]}.{key[1]}': {str(e)}")
                    raise
    
    def _resolve_term_guid(self, qualified_name: str, term_guid_map: Dict[Tuple[str, str], str]) -> str:
        """Resolve a qualified name to its GUID"""
        # Parse qualified name: "glossary.termname@glossary"
        if "@" not in qualified_name:
            raise ValueError(f"Invalid qualified name format: {qualified_name}")
        
        qualified, realm = qualified_name.split("@")
        parts = qualified.split(".")
        
        if len(parts) < 2:
            raise ValueError(f"Invalid qualified name format: {qualified_name}")
        
        # The glossary is the first part, term name is the last part
        glossary_name = parts[0]
        term_name = parts[-1]
        
        key = (glossary_name, term_name)
        if key not in term_guid_map:
            raise ValueError(f"Term GUID not found for: {qualified_name} (key: {key})")
        
        return term_guid_map[key]
    
    def _extract_term_name(self, qualified_name: str) -> str:
        """Extract term name from qualified name"""
        # Parse qualified name: "glossary.termname@glossary"
        if "@" not in qualified_name:
            return qualified_name
        
        qualified, realm = qualified_name.split("@")
        parts = qualified.split(".")
        
        # The term name is the last part
        return parts[-1] if parts else qualified_name
    
    def _get_glossary_guid_by_name(self, glossary_name: str) -> Optional[str]:
        """Get GUID for an existing glossary by name"""
        try:
            url = f"{self.base_url}/api/atlas/v2/glossary"
            response = self.session.get(url)
            if response.status_code == 200:
                glossaries = response.json()
                if isinstance(glossaries, list):
                    for glossary in glossaries:
                        if glossary.get("name") == glossary_name:
                            return glossary.get("guid")
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch glossary GUID for '{glossary_name}': {str(e)}")
            return None
    
    def _get_category_guid_by_name(self, glossary_name: str, category_name: str) -> Optional[str]:
        """Get GUID for an existing category by glossary and category name"""
        try:
            # Try to get from glossary-specific endpoint
            url = f"{self.base_url}/api/atlas/v2/glossary/{glossary_name}/categories"
            logger.debug(f"Attempting to fetch category from: {url}")
            response = self.session.get(url)
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Response from glossary-specific endpoint: {data}")
                if isinstance(data, list):
                    for category in data:
                        if category.get("name") == category_name:
                            return category.get("guid")
                elif isinstance(data, dict):
                    if "categories" in data:
                        for category in data["categories"]:
                            if category.get("name") == category_name:
                                return category.get("guid")
                    elif "entities" in data:
                        for category in data["entities"]:
                            if category.get("name") == category_name:
                                return category.get("guid")
                    elif "value" in data:
                        categories = data["value"]
                        if isinstance(categories, list):
                            for category in categories:
                                if category.get("name") == category_name:
                                    return category.get("guid")
            return None
        except Exception as e:
            logger.debug(f"Failed to fetch category GUID for '{glossary_name}.{category_name}': {str(e)}")
            return None
    
    def _get_term_guid_by_name(self, glossary_name: str, term_name: str) -> Optional[str]:
        """Get GUID for an existing term by glossary and term name"""
        try:
            # Try to get from glossary-specific endpoint
            url = f"{self.base_url}/api/atlas/v2/glossary/{glossary_name}/terms"
            response = self.session.get(url)
            if response.status_code == 200:
                terms = response.json()
                if isinstance(terms, list):
                    for term in terms:
                        if term.get("name") == term_name:
                            return term.get("guid")
                elif isinstance(terms, dict) and "entities" in terms:
                    for term in terms["entities"]:
                        if term.get("name") == term_name:
                            return term.get("guid")
            
            # Fallback: try generic endpoint
            url = f"{self.base_url}/api/atlas/v2/glossary/terms"
            response = self.session.get(url)
            if response.status_code == 200:
                terms = response.json()
                if isinstance(terms, list):
                    for term in terms:
                        if (term.get("name") == term_name and 
                            term.get("anchor", {}).get("glossaryName") == glossary_name):
                            return term.get("guid")
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch term GUID for '{glossary_name}.{term_name}': {str(e)}")
            return None

