# Atlas Importer: Dependency-First Execution

## Overview

The Atlas Importer executes a **5-pass workflow** that ensures all dependencies are created before dependent resources. Here's how each pass handles dependencies:

## Execution Flow

### Pass 0: CSV Parsing & Validation
- Parse CSV into glossaries, categories, terms, and relationships
- Validate all references exist
- Build relationship graph with bidirectional links
- **No API calls** - validation only

### Pass 1: Dry-Run Report
- Display what will be created
- Show relationship graph
- Check for validation warnings
- **No API calls** - reporting only
- User can review before actual import

### Pass 2: Create Glossaries ✓ DEPENDENCY-FIRST
```
No dependencies - created first
Glossary 1
Glossary 2
...
```

**GUID Mapping Created:**
```
glossary_name → GUID
"Sales Dictionary" → "abc-123-def"
"Customer Master" → "xyz-789-uvw"
```

### Pass 3: Create Categories ✓ DEPENDENCY-FIRST (Parent-First Order)
```
Categories are created in parent-first order
using recursive dependency resolution:

1. Process "Financial Metrics" 
   → No parent → Create immediately
   → Store GUID

2. Process "Product Classifications"
   → No parent → Create immediately
   → Store GUID

3. Process "Product Details"
   → Parent: "Product Classifications"
   → Call process_category("Product Classifications") first
   → Parent already created, has GUID
   → Include parentCategory GUID in payload
   → Create "Product Details"
   → Store GUID

4. Process "Product Categories"
   → Parent: "Product Classifications"
   → Parent already processed (cached in guid_map)
   → Use stored parent GUID
   → Create immediately
```

**Dependency Ordering Algorithm:**
```python
def process_category(gloss_name, cat_name):
    if already_processed(key):
        return guid_map[key]
    
    category = categories[key]
    parent_guid = None
    
    if category.parent_category_name:
        # RECURSIVE: Process parent first
        parent_guid = process_category(gloss_name, category.parent_category_name)
    
    # Now create this category with parent GUID
    payload = {
        "name": category.name,
        "anchor": {"glossaryGuid": glossary_guid},
        "parentCategory": {"categoryGuid": parent_guid}  # if has parent
    }
    create_category(payload)
```

**GUID Mapping Created:**
```
(glossary_name, category_name) → GUID
("Sales Dictionary", "Financial Metrics") → "cat-001"
("Sales Dictionary", "Product Classifications") → "cat-002"
("Sales Dictionary", "Product Details") → "cat-003"
("Sales Dictionary", "Product Categories") → "cat-004"
```

### Pass 4: Create Terms ✓ DEPENDENCY-FIRST
```
Terms depend on:
1. Glossary GUID (from Pass 2)
2. Category GUIDs (from Pass 3)

Terms are grouped by glossary for bulk creation:

Sales Dictionary terms:
  - Revenue (categories: [cat-001])
  - Product ID (categories: [cat-003])
  - Product Name (categories: [cat-003])
  - ... (batched together)

Customer Master terms:
  - Customer Identifier (categories: [cat-010])
  - ... (batched together)

Each term payload includes:
{
  "name": "Revenue",
  "anchor": {"glossaryGuid": "abc-123-def"},     # from Pass 2
  "categories": [{"categoryGuid": "cat-001"}]    # from Pass 3
}
```

**GUID Mapping Created:**
```
(glossary_name, term_name) → GUID
("Sales Dictionary", "Revenue") → "term-001"
("Sales Dictionary", "Product ID") → "term-002"
```

### Pass 5: Apply Relationships ✓ DEPENDENCY-FIRST
```
Relationships depend on:
1. Source term GUID (from Pass 4)
2. Target term GUID (from Pass 4)
3. Proper relationship arrays

Relationship payload for each term:
{
  "synonyms": [
    {"termGuid": "term-002"},  # Reference by GUID from Pass 4
  ],
  "relatedTerms": [
    {"termGuid": "term-003"},
  ],
  ...
}

Example: Revenue term with relationships
PUT /v2/glossary/term/term-001
{
  "synonyms": [
    {"termGuid": "term-005"}  # Sales Amount
  ],
  "preferredTerms": [
    {"termGuid": "term-005"}  # Sales Amount
  ]
}

Bidirectional relationships auto-created:
- Reverse for: synonym, antonym, related_term, see_also
- NOT reversed for: preferred_term, replacement_term, is_a, classifies
```

## Key Dependency Handling Features

### 1. Recursive Parent-First Ordering (Pass 3)
- **Problem:** Child categories need parent GUID to be created
- **Solution:** Recursive `process_category()` function
- **Process:**
  1. Check if category already processed → return cached GUID
  2. If has parent, recursively call `process_category()` on parent
  3. Parent guaranteed to be created and have GUID
  4. Create child with parent GUID
  5. Cache result

### 2. GUID Mapping Between Passes
```
Pass 2 → glossary_guid_map
  {"Sales Dictionary": "abc-123-def"}
  ↓ passed to Pass 3

Pass 3 → category_guid_map
  {("Sales Dictionary", "Financial Metrics"): "cat-001"}
  ↓ passed to Pass 4

Pass 4 → term_guid_map
  {("Sales Dictionary", "Revenue"): "term-001"}
  ↓ passed to Pass 5
```

### 3. Qualified Name Resolution (Pass 5)
```
Relationship stored as qualified name:
"Sales Dictionary.Sales Amount@glossary"

At execution time:
1. Parse qualified name to extract glossary and term names
2. Look up (glossary, term) in term_guid_map
3. Use returned GUID in relationship payload
4. If GUID not found → validation warning (caught in Pass 1)
```

## Error Handling

### Circular Dependencies
- Detected in Pass 1 validation (would cause infinite recursion)
- Reported before any API calls

### Missing Parent Categories
- Pass 0 validates all parents exist
- Pass 1 reports validation errors

### Missing Target Terms in Relationships
- Pass 1 validates target terms exist
- Pass 5 only executes if all GUIDs resolved

### API Failures
- Caught and logged per operation
- Entire process fails if any pass fails (no partial imports)

## Performance Characteristics

| Pass | Operation | Dependencies | Time |
|------|-----------|--------------|------|
| 0 | CSV parse | None | O(n) |
| 1 | Dry-run | None | O(n) |
| 2 | Create glossaries | None | O(g) API calls |
| 3 | Create categories | Pass 2 + internal graph | O(c) API calls |
| 4 | Create terms | Pass 2, 3 | O(t) API calls |
| 5 | Apply relationships | Pass 4 | O(r) API calls |

Where: g=glossaries, c=categories, t=terms, r=relationships

## Example Execution Trace

```
EXECUTION PLAN:
├─ Pass 2: Create 2 glossaries
│  ├─ Create "Sales Dictionary" → GUID: g-1
│  └─ Create "Customer Master" → GUID: g-2
│
├─ Pass 3: Create 9 categories (parent-first)
│  ├─ Create "Financial Metrics" (no parent) → GUID: c-1
│  ├─ Create "Product Classifications" (no parent) → GUID: c-2
│  ├─ Create "Product Details" (parent: c-2) → GUID: c-3
│  ├─ Create "Product Categories" (parent: c-2) → GUID: c-4
│  ├─ Create "Time Dimensions" (no parent) → GUID: c-5
│  ├─ Create "Geographic Dimensions" (no parent) → GUID: c-6
│  ├─ Create "Customer Dimensions" (no parent) → GUID: c-7
│  ├─ Create "Customer Attributes" (no parent) → GUID: c-8
│  └─ Create "Customer Classification" (no parent) → GUID: c-9
│
├─ Pass 4: Create 15 terms (by glossary)
│  ├─ Sales Dictionary (10 terms, batch create)
│  │  ├─ "Revenue" (category: c-1) → GUID: t-1
│  │  ├─ "Sales Amount" (category: c-1) → GUID: t-2
│  │  ├─ "Discount Amount" (category: c-1) → GUID: t-3
│  │  ├─ "Product ID" (category: c-3) → GUID: t-4
│  │  └─ ... (6 more)
│  └─ Customer Master (5 terms, batch create)
│     ├─ "Customer Identifier" (category: c-8) → GUID: t-11
│     └─ ... (4 more)
│
└─ Pass 5: Create relationships (uses all GUIDs from Pass 4)
   ├─ Update t-1 (Revenue): synonym=[t-2], preferred=[t-2]
   ├─ Update t-2 (Sales Amount): synonym=[t-1] (bidirectional)
   ├─ Update t-4 (Product ID): relatedTerm=[t-5]
   ├─ Update t-5 (Product Name): relatedTerm=[t-4] (bidirectional)
   └─ ... (more relationships)

All operations complete with zero missing dependencies.
```

## Conclusion

The Atlas Importer implements **strict dependency-first execution**:

✅ **Glossaries created first** (no dependencies)
✅ **Categories in parent-first order** (recursive dependency resolution)
✅ **Terms created after glossaries & categories** (GUID mapping)
✅ **Relationships created last** (all term GUIDs available)
✅ **Bidirectional relationships auto-created** (for applicable types)
✅ **All dependencies validated before execution** (Pass 0)
✅ **Circular dependencies detected** (in validation)
✅ **GUID mappings maintained** (between passes)

This ensures that **no resource is created before its dependencies**, eliminating errors from missing references.
