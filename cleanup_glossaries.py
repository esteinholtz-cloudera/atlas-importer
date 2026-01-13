#!/usr/bin/env python3
"""
Clean up business glossaries from Atlas

This script deletes all glossaries and their associated categories, terms, and relationships.
Use this to reset your Atlas instance before re-importing.
"""

import sys
import logging
import click
from config import Config
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

@click.command()
@click.option(
    "--config",
    type=click.Path(exists=True),
    default="config.yaml",
    help="Path to configuration file",
)
@click.option(
    "--atlas-url",
    help="Atlas base URL (overrides config)",
)
@click.option(
    "--atlas-username",
    help="Atlas username (overrides config)",
)
@click.option(
    "--atlas-password",
    help="Atlas password (overrides config)",
)
@click.option(
    "--glossary-name",
    multiple=True,
    help="Specific glossaries to delete (can be used multiple times). If not specified, deletes all.",
)
@click.option(
    "--force",
    is_flag=True,
    help="Skip confirmation prompt",
)
def cleanup_glossaries(config, atlas_url, atlas_username, atlas_password, glossary_name, force):
    """Delete business glossaries from Atlas"""
    try:
        # Load configuration
        cfg = Config.from_file(config)
        
        # Override with CLI options
        if atlas_url:
            cfg.atlas.base_url = atlas_url
        if atlas_username:
            cfg.atlas.username = atlas_username
        if atlas_password:
            cfg.atlas.password = atlas_password
        
        click.echo("=" * 80)
        click.echo("CLEANUP: Business Glossary Deletion")
        click.echo("=" * 80)
        click.echo(f"Atlas URL: {cfg.atlas.base_url}")
        
        # Initialize session
        session = requests.Session()
        session.auth = HTTPBasicAuth(cfg.atlas.username, cfg.atlas.password)
        session.verify = cfg.atlas.verify_ssl
        session.timeout = cfg.atlas.timeout
        session.headers.update({"Content-Type": "application/json"})
        
        # Test connection
        click.echo("\nTesting connection to Atlas...")
        test_url = f"{cfg.atlas.base_url}/api/atlas/v2/types/typedefs"
        test_response = session.get(test_url)
        if test_response.status_code != 200:
            raise Exception(f"Failed to connect to Atlas: HTTP {test_response.status_code}")
        click.echo("✓ Connected to Atlas")
        
        # Get list of glossaries
        click.echo("\nFetching glossaries from Atlas...")
        glossaries_url = f"{cfg.atlas.base_url}/api/atlas/v2/search/basic"
        
        # Search for all glossaries
        search_payload = {
            "typeName": "AtlasGlossary",
            "limit": 1000
        }
        
        response = session.post(glossaries_url, json=search_payload)
        
        if response.status_code != 200:
            click.echo(f"Warning: Initial endpoint failed (HTTP {response.status_code}), trying alternative...")
            # Try alternative endpoint
            glossaries_url = f"{cfg.atlas.base_url}/api/atlas/v2/glossaries"
            response = session.get(glossaries_url)
        
        if response.status_code != 200:
            raise Exception(f"Failed to fetch glossaries: HTTP {response.status_code}")
        
        glossaries_data = response.json()
        glossaries = []
        
        # Handle different response formats
        if isinstance(glossaries_data, dict):
            if "entities" in glossaries_data:
                glossaries = glossaries_data["entities"]
            elif "value" in glossaries_data:
                glossaries = glossaries_data["value"]
            elif "results" in glossaries_data:
                glossaries = glossaries_data["results"]
        elif isinstance(glossaries_data, list):
            glossaries = glossaries_data
        
        if not glossaries:
            click.echo("✓ No glossaries found")
            return
        
        # Filter glossaries if specified
        if glossary_name:
            glossary_names_set = set(glossary_name)
            glossaries = [g for g in glossaries if g.get("name") in glossary_names_set]
        
        if not glossaries:
            click.echo("✓ No matching glossaries found")
            return
        
        # Display glossaries to delete
        click.echo(f"\nFound {len(glossaries)} glossar{'y' if len(glossaries) == 1 else 'ies'} to delete:\n")
        for gloss in glossaries:
            gloss_name = gloss.get("name", "Unknown")
            gloss_guid = gloss.get("guid", gloss.get("id", "Unknown"))
            click.echo(f"  • {gloss_name} (GUID: {gloss_guid})")
        
        # Confirm deletion
        if not force:
            click.echo()
            if not click.confirm("Are you sure you want to delete these glossaries? This cannot be undone."):
                click.echo("✗ Cancelled")
                return
        
        # Delete glossaries
        click.echo()
        for gloss in glossaries:
            gloss_name = gloss.get("name", "Unknown")
            gloss_guid = gloss.get("guid", gloss.get("id"))
            
            if not gloss_guid:
                click.echo(f"✗ Cannot delete '{gloss_name}': No GUID found")
                continue
            
            try:
                delete_url = f"{cfg.atlas.base_url}/api/atlas/v2/glossary/{gloss_guid}"
                
                click.echo(f"Deleting '{gloss_name}'...")
                logger.info(f"DELETE {delete_url}")
                
                delete_response = session.delete(delete_url)
                
                if delete_response.status_code in [200, 204]:
                    click.echo(click.style(f"✓ Deleted '{gloss_name}'", fg='green'))
                elif delete_response.status_code == 404:
                    click.echo(f"✓ '{gloss_name}' not found (already deleted?)")
                else:
                    try:
                        error_data = delete_response.json()
                        error_msg = error_data.get("errorMessage", delete_response.text)
                    except:
                        error_msg = delete_response.text
                    click.echo(click.style(f"✗ Failed to delete '{gloss_name}': {error_msg}", fg='red'))
            except Exception as e:
                click.echo(click.style(f"✗ Error deleting '{gloss_name}': {str(e)}", fg='red'))
        
        click.echo()
        click.echo("=" * 80)
        click.echo("✓ Cleanup completed")
        click.echo("=" * 80)
        
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
        click.echo(click.style(f"\n✗ Cleanup failed: {str(e)}", fg='red', bold=True))
        sys.exit(1)

if __name__ == "__main__":
    cleanup_glossaries()
