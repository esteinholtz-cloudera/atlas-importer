"""Data models for Atlas business glossary entities"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class EntityType(str, Enum):
    """Atlas entity types for business glossary"""
    GLOSSARY = "AtlasGlossary"
    CATEGORY = "AtlasGlossaryCategory"
    TERM = "AtlasGlossaryTerm"


class RelationshipType(str, Enum):
    """Supported term relationship types"""
    SYNONYM = "synonym"
    ANTONYM = "antonym"
    RELATED_TERM = "related_term"
    PREFERRED_TERM = "preferred_term"
    REPLACEMENT_TERM = "replacement_term"
    SEE_ALSO = "see_also"
    IS_A = "is_a"
    CLASSIFIES = "classifies"


@dataclass
class Glossary:
    """Business glossary entity"""
    name: str
    guid: Optional[str] = None
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if isinstance(other, Glossary):
            return self.name == other.name
        return False


@dataclass
class Category:
    """Glossary category entity"""
    name: str
    glossary_name: str
    parent_category_name: Optional[str] = None
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    status: str = "Active"
    guid: Optional[str] = None
    
    def qualified_name(self) -> str:
        """Generate qualified name for category"""
        if self.parent_category_name:
            return f"{self.glossary_name}.{self.parent_category_name}.{self.name}@glossary"
        return f"{self.glossary_name}.{self.name}@glossary"
    
    def __hash__(self):
        return hash((self.glossary_name, self.name))
    
    def __eq__(self, other):
        if isinstance(other, Category):
            return self.glossary_name == other.glossary_name and self.name == other.name
        return False


@dataclass
class Term:
    """Glossary term entity"""
    name: str
    glossary_name: str
    category_names: List[str] = field(default_factory=list)
    short_description: Optional[str] = None
    long_description: Optional[str] = None
    status: str = "Active"
    steward: Optional[str] = None
    abbreviation: Optional[str] = None
    examples: Optional[str] = None
    guid: Optional[str] = None
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)
    related_terms: List[str] = field(default_factory=list)
    preferred_terms: List[str] = field(default_factory=list)
    replacement_terms: List[str] = field(default_factory=list)
    see_also: List[str] = field(default_factory=list)
    is_a: List[str] = field(default_factory=list)
    classifies: List[str] = field(default_factory=list)
    
    def qualified_name(self) -> str:
        """Generate qualified name for term"""
        return f"{self.glossary_name}.{self.name}@glossary"
    
    def __hash__(self):
        return hash((self.glossary_name, self.name))
    
    def __eq__(self, other):
        if isinstance(other, Term):
            return self.glossary_name == other.glossary_name and self.name == other.name
        return False


@dataclass
class Relationship:
    """Relationship between two terms"""
    source_glossary: str
    source_name: str
    target_glossary: str
    target_name: str
    relationship_type: RelationshipType
    is_bidirectional: bool = False
    
    def __hash__(self):
        return hash((
            self.source_glossary,
            self.source_name,
            self.target_glossary,
            self.target_name,
            self.relationship_type,
        ))
