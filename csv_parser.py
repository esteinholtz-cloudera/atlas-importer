"""CSV parser for Atlas glossary definitions"""

import csv
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from models import Glossary, Category, Term, Relationship, RelationshipType

logger = logging.getLogger(__name__)


class CSVParser:
    """Parse CSV file into entities and relationships"""
    
    REQUIRED_COLUMNS = {
        "type", "glossary_name"
    }
    
    GLOSSARY_COLUMNS = {"type", "glossary_name"}
    
    CATEGORY_COLUMNS = {
        "type", "glossary_name", "name", "parent_category_name",
        "short_description", "long_description", "status"
    }
    
    TERM_COLUMNS = {
        "type", "glossary_name", "name", "category_names",
        "short_description", "long_description", "status", "steward",
        "abbreviation", "examples"
    }
    
    RELATIONSHIP_COLUMNS = {
        "glossary_name", "name", "relationship_type",
        "linked_glossary_name", "linked_entity_name"
    }
    
    def __init__(self, config):
        self.config = config
        self.glossaries: Dict[str, Glossary] = {}
        self.categories: Dict[Tuple[str, str], Category] = {}  # (glossary, name)
        self.terms: Dict[Tuple[str, str], Term] = {}  # (glossary, name)
        self.relationships: List[Relationship] = []
    
    def parse(self, csv_path: str) -> Tuple[Dict, Dict, Dict, List[Relationship]]:
        """Parse CSV file and return entities and relationships"""
        if not Path(csv_path).exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        logger.info(f"Parsing CSV file: {csv_path}")
        
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            
            # Validate headers
            if not reader.fieldnames:
                raise ValueError("CSV file is empty")
            
            missing_cols = self.REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing_cols:
                raise ValueError(
                    f"CSV missing required columns: {', '.join(missing_cols)}"
                )
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
                try:
                    self._parse_row(row)
                except Exception as e:
                    logger.error(f"Error parsing row {row_num}: {str(e)}")
                    raise
        
        logger.info(
            f"Parsed {len(self.glossaries)} glossaries, "
            f"{len(self.categories)} categories, "
            f"{len(self.terms)} terms, "
            f"{len(self.relationships)} relationships"
        )
        
        return self.glossaries, self.categories, self.terms, self.relationships
    
    def _parse_row(self, row: Dict[str, str]) -> None:
        """Parse a single CSV row"""
        # Clean up row values
        row = {k: (v.strip() if v else "") for k, v in row.items()}
        
        entity_type = row.get("type", "").lower()
        
        if entity_type == "relationship":
            self._parse_relationship_row(row)
        elif entity_type == "glossary":
            self._parse_glossary_row(row)
        elif entity_type == "category":
            self._parse_category_row(row)
        elif entity_type == "term":
            self._parse_term_row(row)
        else:
            logger.warning(f"Unknown entity type: {entity_type}")
    
    def _parse_glossary_row(self, row: Dict[str, str]) -> None:
        """Parse a glossary row"""
        name = row.get("glossary_name", "").strip()
        
        if not name:
            raise ValueError("Glossary must have a glossary_name")
        
        if name not in self.glossaries:
            self.glossaries[name] = Glossary(name=name)
            logger.debug(f"Created glossary: {name}")
    
    def _parse_category_row(self, row: Dict[str, str]) -> None:
        """Parse a category row"""
        glossary_name = row.get("glossary_name", "").strip()
        name = row.get("name", "").strip()
        parent = row.get("parent_category_name", "").strip() or None
        short_desc = row.get("short_description", "").strip() or None
        long_desc = row.get("long_description", "").strip() or None
        status = row.get("status", "Active").strip() or "Active"
        
        if not glossary_name or not name:
            raise ValueError("Category must have glossary_name and name")
        
        # Ensure glossary exists
        if glossary_name not in self.glossaries:
            self.glossaries[glossary_name] = Glossary(name=glossary_name)
        
        key = (glossary_name, name)
        if key not in self.categories:
            category = Category(
                name=name,
                glossary_name=glossary_name,
                parent_category_name=parent,
                short_description=short_desc,
                long_description=long_desc,
                status=status,
            )
            self.categories[key] = category
            logger.debug(f"Created category: {glossary_name}.{name}")
    
    def _parse_term_row(self, row: Dict[str, str]) -> None:
        """Parse a term row"""
        glossary_name = row.get("glossary_name", "").strip()
        name = row.get("name", "").strip()
        category_names_str = row.get("category_names", "").strip()
        category_names = [c.strip() for c in category_names_str.split(",") if c.strip()]
        short_desc = row.get("short_description", "").strip() or None
        long_desc = row.get("long_description", "").strip() or None
        status = row.get("status", "Active").strip() or "Active"
        steward = row.get("steward", "").strip() or None
        abbreviation = row.get("abbreviation", "").strip() or None
        examples = row.get("examples", "").strip() or None
        
        if not glossary_name or not name:
            raise ValueError("Term must have glossary_name and name")
        
        # Ensure glossary exists
        if glossary_name not in self.glossaries:
            self.glossaries[glossary_name] = Glossary(name=glossary_name)
        
        key = (glossary_name, name)
        if key not in self.terms:
            term = Term(
                name=name,
                glossary_name=glossary_name,
                category_names=category_names,
                short_description=short_desc,
                long_description=long_desc,
                status=status,
                steward=steward,
                abbreviation=abbreviation,
                examples=examples,
            )
            self.terms[key] = term
            logger.debug(f"Created term: {glossary_name}.{name}")
    
    def _parse_relationship_row(self, row: Dict[str, str]) -> None:
        """Parse a relationship row"""
        source_glossary = row.get("glossary_name", "").strip()
        source_name = row.get("name", "").strip()
        target_glossary = row.get("linked_glossary_name", "").strip()
        target_name = row.get("linked_entity_name", "").strip()
        rel_type_str = row.get("relationship_type", "").strip().lower()
        
        if not all([source_glossary, source_name, target_glossary, target_name, rel_type_str]):
            raise ValueError(
                "Relationship must have glossary_name, name, linked_glossary_name, "
                "linked_entity_name, and relationship_type"
            )
        
        # Validate relationship type
        try:
            rel_type = RelationshipType(rel_type_str)
        except ValueError:
            raise ValueError(
                f"Unknown relationship type: {rel_type_str}. "
                f"Valid types: {', '.join([t.value for t in RelationshipType])}"
            )
        
        # Determine if bidirectional
        is_bidirectional = rel_type_str in self.config.relationships.bidirectional_types
        
        relationship = Relationship(
            source_glossary=source_glossary,
            source_name=source_name,
            target_glossary=target_glossary,
            target_name=target_name,
            relationship_type=rel_type,
            is_bidirectional=is_bidirectional,
        )
        
        self.relationships.append(relationship)
        
        # Add reverse relationship if bidirectional
        if is_bidirectional:
            reverse_relationship = Relationship(
                source_glossary=target_glossary,
                source_name=target_name,
                target_glossary=source_glossary,
                target_name=source_name,
                relationship_type=rel_type,
                is_bidirectional=True,
            )
            self.relationships.append(reverse_relationship)
        
        logger.debug(
            f"Created relationship: {source_glossary}.{source_name} "
            f"{rel_type_str} {target_glossary}.{target_name} "
            f"(bidirectional: {is_bidirectional})"
        )
