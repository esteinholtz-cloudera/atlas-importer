#!/usr/bin/env python3
"""Export glossaries from Cloudera Atlas"""

import sys
import logging
import click
import requests
from requests.auth import HTTPBasicAuth
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--config",
    type=click.Path(exists=True),
    default="config.yaml",
    help="Path to configuration file",
)
def export_glossaries(config):
    """Export all glossaries from Atlas"""
    try:
        cfg = Config.from_file(config)
        
        logger.info("=" * 80)
        logger.info("ATLAS GLOSSARY EXPORT")
        logger.info("=" * 80)
        logger.info(f"Atlas URL: {cfg.atlas.base_url}")
        
        # Search for all glossaries
        url = f"{cfg.atlas.base_url}/api/atlas/v2/search/basic"
        
        params = {
            "typeName": "AtlasGlossary",
            "limit": 1000,
        }
        
        headers = {
            "Content-Type": "application/json",
        }
        
        auth = HTTPBasicAuth(cfg.atlas.username, cfg.atlas.password)
        
        logger.info(f"Searching for glossaries at {url}")
        
        response = requests.get(
            url,
            params=params,
            headers=headers,
            auth=auth,
            verify=cfg.atlas.verify_ssl,
            timeout=cfg.atlas.timeout,
        )
        
        if response.status_code != 200:
            logger.error(f"Failed to search glossaries: {response.status_code}")
            logger.error(f"Response: {response.text}")
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        
        data = response.json()
        entities = data.get("entities", [])
        
        if not entities:
            click.echo("\n📚 No glossaries found in Atlas")
            return
        
        click.echo(f"\n📚 GLOSSARIES ({len(entities)}):")
        click.echo("=" * 80)
        
        for entity in entities:
            guid = entity.get("guid", "N/A")
            attributes = entity.get("attributes", {})
            name = attributes.get("name", "Unknown")
            display_name = attributes.get("displayName", name)
            short_desc = attributes.get("shortDescription", "")
            
            click.echo(f"\nGUID: {guid}")
            click.echo(f"Name: {name}")
            click.echo(f"Display Name: {display_name}")
            if short_desc:
                click.echo(f"Description: {short_desc}")
            
            # Get categories for this glossary
            category_url = f"{cfg.atlas.base_url}/api/atlas/v2/glossary/{guid}/categories"
            try:
                cat_response = requests.get(
                    category_url,
                    headers=headers,
                    auth=auth,
                    verify=cfg.atlas.verify_ssl,
                    timeout=cfg.atlas.timeout,
                )
                
                if cat_response.status_code == 200:
                    categories = cat_response.json()
                    if categories:
                        click.echo(f"  Categories ({len(categories)}):")
                        for cat in categories:
                            cat_name = cat.get("displayName", cat.get("name", "Unknown"))
                            click.echo(f"    - {cat_name}")
            except Exception as e:
                logger.debug(f"Failed to get categories: {str(e)}")
            
            # Get terms for this glossary
            terms_url = f"{cfg.atlas.base_url}/api/atlas/v2/glossary/{guid}/terms"
            try:
                terms_response = requests.get(
                    terms_url,
                    headers=headers,
                    auth=auth,
                    verify=cfg.atlas.verify_ssl,
                    timeout=cfg.atlas.timeout,
                )
                
                if terms_response.status_code == 200:
                    terms = terms_response.json()
                    if terms:
                        click.echo(f"  Terms ({len(terms)}):")
                        for term in terms:
                            term_name = term.get("displayName", term.get("name", "Unknown"))
                            click.echo(f"    - {term_name}")
            except Exception as e:
                logger.debug(f"Failed to get terms: {str(e)}")
        
        click.echo("\n" + "=" * 80)
        
    except Exception as e:
        logger.error(f"Export failed: {str(e)}", exc_info=True)
        click.echo(f"\n✗ Export failed: {str(e)}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    export_glossaries()
