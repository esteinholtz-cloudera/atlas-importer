#!/usr/bin/env python3
"""
Cloudera Atlas Business Glossary CSV Importer

Imports business glossaries, categories, and terms from CSV files into Cloudera Atlas.
Supports relationship definition as separate rows with bidirectional linking and dry-run validation.
"""

import logging
import sys
import click
from pathlib import Path
from config import Config
from csv_parser import CSVParser
from relationship_graph import RelationshipGraphBuilder
from atlas_client import AtlasClient


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """Cloudera Atlas Business Glossary CSV Importer"""
    pass


@cli.command()
@click.option(
    "--config",
    type=click.Path(exists=True),
    default="config.yaml",
    help="Path to configuration file",
)
@click.option(
    "--csv",
    type=click.Path(exists=True),
    help="Path to CSV file (overrides config)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=None,
    help="Run in dry-run mode (validation only, no API calls)",
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
    "--verify-ssl",
    type=bool,
    help="Verify SSL certificates (overrides config)",
)
@click.option(
    "--timeout",
    type=int,
    help="Request timeout in seconds (overrides config)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    help="Logging level (overrides config)",
)
@click.option(
    "--log-file",
    type=click.Path(),
    help="Log file path (overrides config)",
)
@click.option(
    "--filter-glossary",
    multiple=True,
    help="Only import specified glossaries (can be used multiple times)",
)
@click.option(
    "--filter-term",
    multiple=True,
    help="Only import specified terms (can be used multiple times)",
)
@click.option(
    "--exclude-relationships",
    is_flag=True,
    help="Skip relationship creation",
)
@click.option(
    "--validate-only",
    is_flag=True,
    help="Validate CSV without creating anything",
)
def import_glossary(
    config,
    csv,
    dry_run,
    atlas_url,
    atlas_username,
    atlas_password,
    verify_ssl,
    timeout,
    log_level,
    log_file,
    filter_glossary,
    filter_term,
    exclude_relationships,
    validate_only,
):
    """Import business glossary from CSV file to Atlas"""
    try:
        # Load configuration
        cfg = Config.from_file(config)
        
        # Override with CLI options
        if csv:
            cfg.import_config.csv_file = csv
        if dry_run is not None:
            cfg.import_config.dry_run = dry_run
        if validate_only:
            cfg.import_config.dry_run = True
        if log_level:
            cfg.import_config.log_level = log_level
        if log_file:
            cfg.import_config.log_file = log_file
        if atlas_url:
            cfg.atlas.base_url = atlas_url
        if atlas_username:
            cfg.atlas.username = atlas_username
        if atlas_password:
            cfg.atlas.password = atlas_password
        if verify_ssl is not None:
            cfg.atlas.verify_ssl = verify_ssl
        if timeout is not None:
            cfg.atlas.timeout = timeout
        
        # Set up logging
        log_level_obj = getattr(logging, cfg.import_config.log_level)
        logger.setLevel(log_level_obj)
        file_handler = logging.FileHandler(cfg.import_config.log_file)
        file_handler.setLevel(log_level_obj)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        logger.info("=" * 80)
        logger.info("ATLAS BUSINESS GLOSSARY IMPORTER")
        logger.info("=" * 80)
        logger.info(f"Configuration file: {config}")
        logger.info(f"CSV file: {cfg.import_config.csv_file}")
        logger.info(f"Dry-run mode: {cfg.import_config.dry_run}")
        logger.info(f"Validate only: {validate_only}")
        logger.info(f"Exclude relationships: {exclude_relationships}")
        if filter_glossary:
            logger.info(f"Filter glossaries: {', '.join(filter_glossary)}")
        if filter_term:
            logger.info(f"Filter terms: {', '.join(filter_term)}")
        logger.info(f"Atlas URL: {cfg.atlas.base_url}")
        logger.info(f"SSL verification: {cfg.atlas.verify_ssl}")
        logger.info(f"Request timeout: {cfg.atlas.timeout}s")
        logger.info("=" * 80)
        
        # Parse CSV
        parser = CSVParser(cfg)
        glossaries, categories, terms, relationships = parser.parse(
            cfg.import_config.csv_file
        )
        
        # Apply filters
        if filter_glossary:
            filter_glossary_set = set(filter_glossary)
            glossaries = {k: v for k, v in glossaries.items() if k in filter_glossary_set}
            categories = {k: v for k, v in categories.items() if k[0] in filter_glossary_set}
            terms = {k: v for k, v in terms.items() if k[0] in filter_glossary_set}
            relationships = [r for r in relationships if r.source_glossary in filter_glossary_set]
            logger.info(f"Applied glossary filter: {', '.join(filter_glossary)}")
        
        if filter_term:
            filter_term_set = set(filter_term)
            terms = {k: v for k, v in terms.items() if k[1] in filter_term_set}
            relationships = [
                r for r in relationships
                if r.source_name in filter_term_set or r.target_name in filter_term_set
            ]
            logger.info(f"Applied term filter: {', '.join(filter_term)}")
        
        # Build relationship graph
        graph_builder = RelationshipGraphBuilder(terms)
        
        if not exclude_relationships:
            graph_builder.apply_relationships(relationships)
        else:
            logger.info("Relationship creation disabled by --exclude-relationships flag")
            relationships = []
        
        # Validate relationships
        warnings = graph_builder.validate_all_relationships()
        if warnings:
            logger.warning(f"Found {len(warnings)} relationship validation warnings:")
            for warning in sorted(warnings):
                logger.warning(f"  - {warning}")
        
        # Display dry-run report
        _print_dry_run_report(
            glossaries,
            categories,
            terms,
            warnings,
            exclude_relationships,
        )
        
        if validate_only:
            click.echo("\n✓ Validation completed successfully")
            logger.info("Validation completed successfully (--validate-only)")
        elif cfg.import_config.dry_run:
            click.echo("\n" + "=" * 80)
            click.echo("DRY-RUN MODE: Showing REST API calls that would be executed")
            click.echo("=" * 80)
            
            _print_rest_api_calls(
                cfg,
                glossaries,
                categories,
                terms,
                exclude_relationships
            )
            
            click.echo("\n✓ Dry-run validation completed successfully")
            logger.info("Dry-run completed successfully")
        else:
            # Perform actual import
            click.echo("\n" + "=" * 80)
            click.echo("EXECUTING IMPORT TO ATLAS")
            click.echo("=" * 80)
            
            _execute_import(
                cfg,
                glossaries,
                categories,
                terms,
                exclude_relationships
            )
            
            click.echo(click.style("\n✓ Glossary import completed successfully!", fg='green', bold=True))
            logger.info("Import completed successfully")
        
        logger.info("=" * 80)
        logger.info("PROCESS COMPLETED")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Import failed: {str(e)}", exc_info=True)
        click.echo(click.style(f"\n✗ Import failed: {str(e)}", fg='red', bold=True))
        sys.exit(1)


def _execute_import(cfg, glossaries, categories, terms, exclude_relationships):
    """Execute actual import to Atlas (Passes 2-5)"""
    
    # Initialize client
    client = AtlasClient(
        cfg.atlas.base_url,
        cfg.atlas.username,
        cfg.atlas.password,
        cfg.atlas.verify_ssl,
        cfg.atlas.timeout
    )
    
    # Test connection
    click.echo("\nTesting connection to Atlas...")
    if not client.test_connection():
        raise Exception("Failed to connect to Atlas server")
    
    # Pass 2: Create glossaries
    click.echo("\nPass 2: Creating glossaries...")
    glossary_guid_map = client.create_glossaries(glossaries)
    click.echo(click.style(f"✓ Created {len(glossary_guid_map)} glossary/glossaries", fg='green'))
    
    # Pass 3: Create categories (handles dependency ordering)
    click.echo("\nPass 3: Creating categories...")
    category_guid_map = client.create_categories(categories, glossary_guid_map)
    click.echo(click.style(f"✓ Created {len(category_guid_map)} categor{'ies' if len(category_guid_map) != 1 else 'y'}", fg='green'))
    
    # Pass 4: Create terms
    click.echo("\nPass 4: Creating terms...")
    term_guid_map = client.create_terms(terms, glossary_guid_map, category_guid_map)
    click.echo(click.style(f"✓ Created {len(term_guid_map)} term{'s' if len(term_guid_map) != 1 else ''}", fg='green'))
    
    # Pass 5: Create relationships
    if not exclude_relationships:
        click.echo("\nPass 5: Creating term relationships...")
        client.update_term_relationships(term_guid_map, terms)
        
        # Count relationships
        rel_count = sum(
            len(term.synonyms) + len(term.antonyms) + len(term.related_terms) +
            len(term.preferred_terms) + len(term.replacement_terms) + len(term.see_also) +
            len(term.is_a) + len(term.classifies)
            for term in terms.values()
        )
        click.echo(click.style(f"✓ Created {rel_count} relationship{'s' if rel_count != 1 else ''}", fg='green'))
    else:
        click.echo("\nPass 5: Skipped relationship creation (--exclude-relationships)")
    
    click.echo("\n" + "=" * 80)


def _print_rest_api_calls(cfg, glossaries, categories, terms, exclude_relationships):
    """Print REST API calls that would be executed (debug mode for dry-run)"""
    import json
    
    click.echo("\n" + "=" * 80)
    click.echo("PASS 2: CREATE GLOSSARIES")
    click.echo("=" * 80)
    
    for name in sorted(glossaries.keys()):
        payload = {
            "name": name,
            "shortDescription": f"Glossary: {name}"
        }
        click.echo(f"\nPOST {cfg.atlas.base_url}v2/glossary")
        click.echo(json.dumps(payload, indent=2))
    
    click.echo("\n" + "=" * 80)
    click.echo("PASS 3: CREATE CATEGORIES (parent-first order)")
    click.echo("=" * 80)
    
    # Group categories by glossary
    categories_by_glossary = {}
    for (glossary, name), cat in sorted(categories.items()):
        if glossary not in categories_by_glossary:
            categories_by_glossary[glossary] = []
        categories_by_glossary[glossary].append((name, cat))
    
    for glossary in sorted(categories_by_glossary.keys()):
        click.echo(f"\nGlossary: {glossary}")
        for name, cat in sorted(categories_by_glossary[glossary]):
            payload = {
                "name": name,
                "anchor": {
                    "glossaryGuid": f"<glossary_guid:{glossary}>"
                },
                "shortDescription": cat.short_description or f"Category: {name}"
            }
            if cat.parent_category_name:
                payload["parentCategory"] = {
                    "categoryGuid": f"<category_guid:{glossary}.{cat.parent_category_name}>"
                }
            
            click.echo(f"  POST {cfg.atlas.base_url}v2/glossary/categories")
            click.echo("  " + json.dumps(payload, indent=4).replace("\n", "\n  "))
    
    click.echo("\n" + "=" * 80)
    click.echo("PASS 4: CREATE TERMS")
    click.echo("=" * 80)
    
    # Group terms by glossary
    terms_by_glossary = {}
    for (glossary, name), term in sorted(terms.items()):
        if glossary not in terms_by_glossary:
            terms_by_glossary[glossary] = []
        terms_by_glossary[glossary].append((name, term))
    
    for glossary in sorted(terms_by_glossary.keys()):
        click.echo(f"\nGlossary: {glossary} (batch create)")
        
        batch_payload = []
        for name, term in sorted(terms_by_glossary[glossary]):
            term_payload = {
                "name": name,
                "anchor": {
                    "glossaryGuid": f"<glossary_guid:{glossary}>"
                },
                "shortDescription": term.short_description or f"Term: {name}"
            }
            
            if term.long_description:
                term_payload["longDescription"] = term.long_description
            if term.abbreviation:
                term_payload["abbreviation"] = term.abbreviation
            if term.steward:
                term_payload["steward"] = term.steward
            if term.status:
                term_payload["status"] = term.status
            if term.examples:
                term_payload["examples"] = term.examples
            
            if term.category_names:
                term_payload["categories"] = [
                    {
                        "categoryGuid": f"<category_guid:{glossary}.{cat_name}>"
                    }
                    for cat_name in term.category_names
                ]
            
            batch_payload.append(term_payload)
        
        click.echo(f"  POST {cfg.atlas.base_url}v2/glossary/terms")
        click.echo("  " + json.dumps(batch_payload, indent=4).replace("\n", "\n  "))
    
    if not exclude_relationships:
        click.echo("\n" + "=" * 80)
        click.echo("PASS 5: CREATE TERM RELATIONSHIPS")
        click.echo("=" * 80)
        
        for (glossary, name), term in sorted(terms.items()):
            if any([
                term.synonyms, term.antonyms, term.related_terms,
                term.preferred_terms, term.replacement_terms, term.see_also,
                term.is_a, term.classifies
            ]):
                click.echo(f"\nTerm: {glossary}.{name}")
                
                payload = {
                    "guid": f"<term_guid:{glossary}.{name}>"
                }
                
                if term.synonyms:
                    payload["synonyms"] = [
                        {"termGuid": f"<term_guid:{target}>"}
                        for target in term.synonyms
                    ]
                
                if term.antonyms:
                    payload["antonyms"] = [
                        {"termGuid": f"<term_guid:{target}>"}
                        for target in term.antonyms
                    ]
                
                if term.related_terms:
                    payload["relatedTerms"] = [
                        {"termGuid": f"<term_guid:{target}>"}
                        for target in term.related_terms
                    ]
                
                if term.preferred_terms:
                    payload["preferredTerms"] = [
                        {"termGuid": f"<term_guid:{target}>"}
                        for target in term.preferred_terms
                    ]
                
                if term.replacement_terms:
                    payload["replacementTerms"] = [
                        {"termGuid": f"<term_guid:{target}>"}
                        for target in term.replacement_terms
                    ]
                
                if term.see_also:
                    payload["seeAlso"] = [
                        {"termGuid": f"<term_guid:{target}>"}
                        for target in term.see_also
                    ]
                
                if term.is_a:
                    payload["isA"] = [
                        {"termGuid": f"<term_guid:{target}>"}
                        for target in term.is_a
                    ]
                
                if term.classifies:
                    payload["classifies"] = [
                        {"termGuid": f"<term_guid:{target}>"}
                        for target in term.classifies
                    ]
                
                click.echo(f"  PUT {cfg.atlas.base_url}v2/glossary/term/<term_guid>")
                click.echo("  " + json.dumps(payload, indent=4).replace("\n", "\n  "))
    
    click.echo("\n" + "=" * 80)
    click.echo("END OF REST API CALLS (DEBUG OUTPUT)")
    click.echo("=" * 80)
    
    # Print summary
    total_relationships = sum(
        len(term.synonyms) + len(term.antonyms) + len(term.related_terms) +
        len(term.preferred_terms) + len(term.replacement_terms) + len(term.see_also) +
        len(term.is_a) + len(term.classifies)
        for term in terms.values()
    )
    
    click.echo(f"\n📊 API CALL SUMMARY:")
    click.echo(f"  • Glossary Creation Calls: {len(glossaries)}")
    click.echo(f"  • Category Creation Calls: {len(categories)}")
    click.echo(f"  • Term Batch Creation Calls: {len(terms_by_glossary)}")
    if not exclude_relationships:
        click.echo(f"  • Relationship Update Calls: {sum(1 for t in terms.values() if any([t.synonyms, t.antonyms, t.related_terms, t.preferred_terms, t.replacement_terms, t.see_also, t.is_a, t.classifies]))}")
        click.echo(f"  • Total Relationship Records: {total_relationships}")
    
    click.echo()


def _print_dry_run_report(glossaries, categories, terms, warnings, exclude_relationships):
    """Print dry-run validation report"""
    click.echo("\n" + "=" * 80)
    click.echo("DRY-RUN VALIDATION REPORT")
    click.echo("=" * 80)
    
    # Glossaries
    click.echo(f"\n📚 GLOSSARIES ({len(glossaries)}):")
    for name in sorted(glossaries.keys()):
        click.echo(f"  ✓ {name}")
    
    # Categories
    click.echo(f"\n📁 CATEGORIES ({len(categories)}):")
    for (glossary, name), cat in sorted(categories.items()):
        parent_str = f" (parent: {cat.parent_category_name})" if cat.parent_category_name else ""
        click.echo(f"  ✓ {glossary}.{name}{parent_str}")
        if cat.short_description:
            click.echo(f"    └─ {cat.short_description}")
    
    # Terms with detailed information
    click.echo(f"\n📝 TERMS ({len(terms)}):")
    for (glossary, name), term in sorted(terms.items()):
        click.echo(f"  ✓ {glossary}.{name}")
        
        # Basic information
        if term.abbreviation:
            click.echo(f"    ├─ Abbreviation: {term.abbreviation}")
        if term.short_description:
            click.echo(f"    ├─ Description: {term.short_description}")
        if term.long_description:
            click.echo(f"    ├─ Details: {term.long_description}")
        if term.steward:
            click.echo(f"    ├─ Steward: {term.steward}")
        if term.status:
            click.echo(f"    ├─ Status: {term.status}")
        if term.examples:
            click.echo(f"    ├─ Examples: {term.examples}")
        if term.category_names:
            click.echo(f"    ├─ Categories: {', '.join(term.category_names)}")
        
        # Show relationships
        if not exclude_relationships:
            all_rels = [
                ("Synonyms", term.synonyms),
                ("Antonyms", term.antonyms),
                ("Related Terms", term.related_terms),
                ("Preferred Terms", term.preferred_terms),
                ("Replacement Terms", term.replacement_terms),
                ("See Also", term.see_also),
                ("Is A", term.is_a),
                ("Classifies", term.classifies),
            ]
            
            has_relationships = any(rel_list for _, rel_list in all_rels)
            if has_relationships:
                click.echo(f"    └─ Relationships:")
                for rel_type, rel_list in all_rels:
                    if rel_list:
                        for i, rel_target in enumerate(rel_list):
                            is_last = (i == len(rel_list) - 1) and all(
                                not rel_list2 for _, rel_list2 in all_rels[all_rels.index((rel_type, rel_list))+1:]
                            )
                            prefix = "       └─ " if is_last else "       ├─ "
                            click.echo(f"{prefix}{rel_type}: {rel_target}")
    
    # Summary statistics
    total_relationships = sum(
        len(term.synonyms) + len(term.antonyms) + len(term.related_terms) +
        len(term.preferred_terms) + len(term.replacement_terms) + len(term.see_also) +
        len(term.is_a) + len(term.classifies)
        for term in terms.values()
    )
    
    click.echo(f"\n📊 SUMMARY:")
    click.echo(f"  • Glossaries: {len(glossaries)}")
    click.echo(f"  • Categories: {len(categories)}")
    click.echo(f"  • Terms: {len(terms)}")
    if not exclude_relationships:
        click.echo(f"  • Relationships: {total_relationships}")
    else:
        click.echo(f"  • Relationships: 0 (excluded)")
    
    # Validation warnings
    if warnings:
        click.echo(f"\n⚠️  VALIDATION WARNINGS ({len(warnings)}):")
        for warning in sorted(warnings):
            click.echo(f"  ⚠️  {warning}")
    else:
        click.echo(f"\n✅ All validations passed!")
    
    click.echo("\n" + "=" * 80)


if __name__ == "__main__":
    cli()
