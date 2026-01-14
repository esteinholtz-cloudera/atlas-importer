# Cloudera Atlas Business Glossary CSV Importer

A Python utility for importing business glossary definitions (glossaries, categories, and terms) from CSV files into Cloudera Atlas. Supports hierarchical category structures, bidirectional term relationships, and cross-glossary references with comprehensive dry-run validation.

## Features

- **CSV-based glossary import**: Define complete business glossaries in CSV format
- **Hierarchical structures**: Create nested categories and organize terms into multiple categories
- **Term relationships**: Create bidirectional and unidirectional relationships (synonyms, antonyms, related terms, preferred terms, replacement terms, see also, is-a, classifies)
- **Cross-glossary references**: Link terms across different glossaries
- **Relationship rows**: Define relationships as separate rows using `type=relationship`, supporting multiple relationships per term
- **Dry-run mode**: Validate CSV structure and preview changes before uploading to Atlas
- **Comprehensive validation**: Check for missing references, duplicate names, and invalid configurations
- **Detailed logging**: Track all operations with informative logs
- **Selective bidirectional relationships**: Automatically create both directions for specific relationship types (synonym, antonym, relatedTerm, seeAlso)

## Installation

### Prerequisites

- Python 3.10 or later
- Cloudera Atlas instance (7.3.1+)
- Network access to Atlas API endpoint

### Setup

1. Clone or download the repository
2. Install dependencies using `uv` (recommended):

```bash
pip install uv
uv sync
```

**Alternative installation methods:**

Using pip directly:

```bash
pip install requests pydantic click pyyaml pandas
```

Or with project file:

```bash
cd atlas-importer
pip install -e .
```

## Usage

### Basic Command

```bash
python main.py import-glossary \
  --csv glossary.csv \
  --atlas-url https://atlas-host:21000 \
  --atlas-username admin \
  --atlas-password secret
```

### Dry-Run Mode (Validation Only)

Preview all changes without uploading to Atlas:

```bash
python main.py import-glossary \
  --csv glossary.csv \
  --atlas-url https://atlas-host:21000 \
  --atlas-username admin \
  --atlas-password secret \
  --dry-run
```

### Options

- `--csv` (required): Path to CSV file containing glossary definitions
- `--atlas-url` (required): Cloudera Atlas base URL (e.g., `https://atlas-host:21000`)
- `--atlas-username` (required): Atlas username for authentication
- `--atlas-password` (required): Atlas password for authentication
- `--verify-ssl`: Enable SSL certificate verification (default: enabled)
- `--dry-run`: Run in validation-only mode without uploading
- `--config`: Path to configuration file (default: config.yaml)
- `--filter-glossary`: Only import specified glossaries (can be used multiple times)
- `--filter-term`: Only import specified terms (can be used multiple times)
- `--exclude-relationships`: Skip relationship creation
- `--validate-only`: Validate CSV without creating anything

## CSV Format

The CSV file contains four types of rows distinguished by the `type` column:

### Entity Rows

These rows define glossaries, categories, and terms.

#### Glossary Rows

```csv
type,glossary_name,short_description
glossary,My Business Glossary,Primary business data definitions
```

**Fields:**
- `type`: Must be `glossary`
- `glossary_name`: Name of the glossary
- `short_description`: Optional brief description

#### Category Rows

```csv
type,glossary_name,name,parent_category_name,short_description
category,My Business Glossary,Dimension Entities,,Entities used in dimensional modeling
category,My Business Glossary,Product Dimensions,Dimension Entities,Product-related dimensions
```

**Fields:**
- `type`: Must be `category`
- `glossary_name`: Parent glossary name (must be defined)
- `name`: Category name
- `parent_category_name`: Optional parent category (for nested structures)
- `short_description`: Optional description

#### Term Rows

```csv
type,glossary_name,name,category_names,short_description,long_description,status,steward,abbreviation,examples
term,My Business Glossary,Customer ID,"Dimension Entities,Customer Dimensions",Unique customer identifier,System-assigned unique identifier,Active,Customer Team,CID,"CUST-001, CUST-002"
```

**Fields:**
- `type`: Must be `term`
- `glossary_name`: Parent glossary name (must be defined)
- `name`: Term name
- `category_names`: Comma-separated list of categories (optional, must exist)
- `short_description`: Optional brief description
- `long_description`: Optional detailed description
- `status`: Optional status (default: `Active`)
- `steward`: Optional term owner/steward name
- `abbreviation`: Optional short form
- `examples`: Optional comma-separated examples

#### Relationship Rows

These rows define relationships between terms. Each row creates one relationship; multiple relationships for the same term use multiple rows.

```csv
type,glossary_name,name,linked_glossary_name,linked_entity_name,relationship_type
relationship,My Business Glossary,Customer ID,My Business Glossary,Customer Name,synonym
relationship,My Business Glossary,Product ID,My Business Glossary,Product Code,related_term
relationship,Sales Glossary,Revenue,Finance Glossary,Total Income,preferred_term
```

**Fields:**
- `type`: Must be `relationship`
- `glossary_name`: Source glossary
- `name`: Source term name
- `linked_glossary_name`: Target glossary (can be different)
- `linked_entity_name`: Target term name
- `relationship_type`: Type of relationship (see below)

**Relationship Types:**

| Type | Bidirectional | Description |
|------|---------------|-------------|
| `synonym` | ✓ Yes | Terms with identical or very similar meaning |
| `antonym` | ✓ Yes | Terms with opposite meaning |
| `related_term` | ✓ Yes | Generally related terms |
| `see_also` | ✓ Yes | See also references |
| `preferred_term` | ✗ No | Recommended term to use instead |
| `replacement_term` | ✗ No | Term that replaces another |
| `is_a` | ✗ No | Type/inheritance relationship |
| `classifies` | ✗ No | Classification relationship |

**Note on Bidirectionality:**
- For bidirectional types (synonym, antonym, related_term, see_also), the importer automatically creates the reverse relationship
- For unidirectional types, only the specified direction is created

## Example

See `example_glossary.csv` for a complete example with:
- 2 glossaries (Sales Dictionary, Customer Master)
- Multiple nested categories with parent-child relationships
- 15+ terms with descriptions and assignments
- Various relationship types demonstrating bidirectional and unidirectional links

Run with dry-run to preview:

```bash
python main.py import-glossary \
  --csv example_glossary.csv \
  --atlas-url https://atlas-host:21000 \
  --atlas-username admin \
  --atlas-password secret \
  --dry-run
```

## Import Process

The importer executes a 5-pass workflow:

### Pass 0: CSV Parsing and Validation
- Reads CSV file
- Validates structure (required fields, valid enums)
- Checks for duplicate names within glossary scope
- Validates all references exist (parent categories, source/target terms)
- Reports validation errors before proceeding

### Pass 1: Dry-Run Summary
- Displays all entities that would be created
- Shows relationship graph with bidirectional markers
- Allows review before live upload (useful for `--dry-run` mode)

### Pass 2: Create Glossaries
- Creates all glossary objects via `POST /v2/glossary`
- Stores GUID mappings for later reference

### Pass 3: Create Categories
- Processes categories in dependency order (parents before children)
- Creates all categories via `POST /v2/glossary/categories`
- Handles parent-child relationships via `parentCategory` field

### Pass 4: Create Terms
- Batches terms by glossary
- Creates all terms via `POST /v2/glossary/terms`
- Associates terms with categories
- Stores GUID mappings for relationship creation

### Pass 5: Apply Relationships
- Groups relationships by term and relationship type
- Merges bidirectional relationships (creates reverse for applicable types)
- Updates term objects with relationship arrays
- Uses `PUT /v2/glossary/term/{guid}` for relationship creation

## Error Handling

The importer provides detailed error reporting:

1. **CSV Validation Errors**: Detailed error messages for CSV parsing issues
2. **Reference Errors**: Reports missing glossaries, categories, or terms
3. **API Errors**: Catches and reports Atlas API failures with HTTP status codes
4. **Duplicate Detection**: Checks for duplicate `qualifiedName` values
5. **Dry-Run Safe**: Dry-run mode validates without risking data

## Logging

The importer logs all operations to stdout with timestamps:

```
2024-01-13 10:30:45,123 - __main__ - INFO - Parsed glossary: Sales Dictionary
2024-01-13 10:30:45,456 - __main__ - INFO - Created glossary 'Sales Dictionary' with GUID: abc-123-def
2024-01-13 10:30:46,789 - __main__ - INFO - Created term 'Customer ID' in glossary 'Sales Dictionary' with GUID: term-guid-123
```

Set logging level via environment variable:

```bash
LOGLEVEL=DEBUG python main.py ...
```

## Advanced Features

### Cross-Glossary Term Relationships

You can link terms across different glossaries using the `linked_glossary_name` field in relationship rows:

```csv
type,glossary_name,name,linked_glossary_name,linked_entity_name,relationship_type
relationship,Sales Glossary,Revenue,Finance Glossary,Total Income,synonym
```

### Hierarchical Categories

Create nested category structures by specifying `parent_category_name`:

```csv
category,My Glossary,Parent Category,
category,My Glossary,Child Category,Parent Category
category,My Glossary,Grandchild Category,Child Category
```

The importer automatically processes parents before children.

### Term Multi-Category Assignment

Assign terms to multiple categories using comma-separated values:

```csv
term,My Glossary,Customer ID,,"Unique identifier","System ID","Finance,Operations,Sales",ACTIVE,Team Lead,CID,
```

### Multiple Relationships

Create multiple relationships for a single term by using multiple relationship rows:

```csv
relationship,My Glossary,Term A,My Glossary,Term B,synonym
relationship,My Glossary,Term A,My Glossary,Term C,related_term
relationship,My Glossary,Term A,My Glossary,Term D,see_also
```

## Troubleshooting

### "Connection refused" error
- Verify Atlas URL is correct and accessible
- Check network connectivity to Atlas host
- Ensure port 21000 (or your Atlas port) is open

### "Duplicate qualifiedName" error
- `qualifiedName` must be unique within Atlas
- Check for existing glossaries/terms with same names
- Atlas auto-generates qualifiedName from name, so ensure names don't conflict

### "Category not found" error
- Verify parent category is defined before child category in CSV
- Use exact category names in `parent_category_name` field

### "Authentication failed" error
- Verify username and password are correct
- Check if user has proper Atlas permissions

### CSV parsing errors
- Ensure `type` column is present in header
- Verify enum values are exact (e.g., `ACTIVE` not `Active`)
- Check that comma-separated fields don't have unquoted commas within values

## API Reference

The importer uses these Cloudera Atlas REST API endpoints:

- `POST /v2/glossary` - Create glossary
- `POST /v2/glossary/categories` - Bulk create categories
- `POST /v2/glossary/terms` - Bulk create terms
- `PUT /v2/glossary/term/{guid}` - Update term relationships

See [Cloudera Atlas REST API Reference](https://docs.cloudera.com/runtime/7.3.1/atlas-rest-api-reference/) for details.

## Performance Considerations

- **CSV Size**: Handles glossaries with hundreds of terms efficiently
- **Batch Size**: Currently uses single batch per entity type; monitor API rate limits
- **Network**: Ensure stable network connection for large imports
- **Dry-Run**: Dry-run mode is fast (CSV parsing only, no API calls)

## License

See LICENSE file for details.
