"""Relationship graph builder for Atlas glossary terms"""

import logging
from typing import Dict, Tuple, Set
from models import Term, Relationship, RelationshipType

logger = logging.getLogger(__name__)


class RelationshipGraphBuilder:
    """Build and manage relationships between terms"""
    
    def __init__(self, terms: Dict[Tuple[str, str], Term]):
        self.terms = terms
    
    def apply_relationships(self, relationships: list) -> None:
        """Apply relationships to terms"""
        logger.info(f"Applying {len(relationships)} relationships to terms")
        
        for rel in relationships:
            try:
                self._apply_relationship(rel)
            except Exception as e:
                logger.error(f"Failed to apply relationship: {str(e)}")
                raise
    
    def _apply_relationship(self, rel: Relationship) -> None:
        """Apply a single relationship"""
        # Find source term
        source_key = (rel.source_glossary, rel.source_name)
        if source_key not in self.terms:
            raise ValueError(
                f"Source term not found: {rel.source_glossary}.{rel.source_name}"
            )
        
        source_term = self.terms[source_key]
        
        # Create target term reference (qualified name)
        target_ref = f"{rel.target_glossary}.{rel.target_name}@glossary"
        
        # Add relationship to source term based on type
        if rel.relationship_type == RelationshipType.SYNONYM:
            if target_ref not in source_term.synonyms:
                source_term.synonyms.append(target_ref)
        elif rel.relationship_type == RelationshipType.ANTONYM:
            if target_ref not in source_term.antonyms:
                source_term.antonyms.append(target_ref)
        elif rel.relationship_type == RelationshipType.RELATED_TERM:
            if target_ref not in source_term.related_terms:
                source_term.related_terms.append(target_ref)
        elif rel.relationship_type == RelationshipType.PREFERRED_TERM:
            if target_ref not in source_term.preferred_terms:
                source_term.preferred_terms.append(target_ref)
        elif rel.relationship_type == RelationshipType.REPLACEMENT_TERM:
            if target_ref not in source_term.replacement_terms:
                source_term.replacement_terms.append(target_ref)
        elif rel.relationship_type == RelationshipType.SEE_ALSO:
            if target_ref not in source_term.see_also:
                source_term.see_also.append(target_ref)
        elif rel.relationship_type == RelationshipType.IS_A:
            if target_ref not in source_term.is_a:
                source_term.is_a.append(target_ref)
        elif rel.relationship_type == RelationshipType.CLASSIFIES:
            if target_ref not in source_term.classifies:
                source_term.classifies.append(target_ref)
        
        logger.debug(
            f"Applied {rel.relationship_type.value} from "
            f"{source_key} to {target_ref}"
        )
    
    def validate_all_relationships(self) -> Set[str]:
        """Validate all relationships and return warnings"""
        warnings = set()
        
        for (glossary, name), term in self.terms.items():
            all_refs = (
                term.synonyms + term.antonyms + term.related_terms +
                term.preferred_terms + term.replacement_terms + term.see_also +
                term.is_a + term.classifies
            )
            
            for ref in all_refs:
                # Extract glossary and term name from qualified name
                parts = ref.split("@")
                if len(parts) != 2 or parts[1] != "glossary":
                    warnings.add(f"Invalid qualified name: {ref}")
                    continue
                
                qualified = parts[0]
                glossary_term_parts = qualified.split(".")
                if len(glossary_term_parts) < 2:
                    warnings.add(f"Invalid qualified name format: {ref}")
                    continue
                
                ref_glossary = glossary_term_parts[0]
                ref_name = glossary_term_parts[-1]
                
                target_key = (ref_glossary, ref_name)
                if target_key not in self.terms:
                    warnings.add(
                        f"Relationship target not found: {glossary}.{name} "
                        f"-> {ref}"
                    )
        
        return warnings
