# REST API Call Logging

The importer now logs all REST API calls to stderr so you can see exactly what's being sent to Atlas.

## Dry-Run Mode (Debug Output Only)

Shows what would be executed **without making actual API calls**:

```bash
uv run python main.py import-glossary --csv example_glossary.csv --dry-run
```

**Output includes:**
- ✓ All REST API endpoints
- ✓ All JSON payloads
- ✓ Proper parent-first ordering for categories
- ✓ Qualified name placeholders for cross-glossary references
- ✗ No actual API execution

**Example:**
```
================================================================================
PASS 2: CREATE GLOSSARIES
================================================================================

POST https://atlas.example.com/api/atlas/v2/glossary
{
  "name": "Sales Dictionary",
  "shortDescription": "Glossary: Sales Dictionary"
}

================================================================================
PASS 3: CREATE CATEGORIES (parent-first order)
================================================================================

Glossary: Sales Dictionary
  POST https://atlas.example.com/api/atlas/v2/glossary/categories
  {
      "name": "Product Classifications",
      "anchor": {
          "glossaryGuid": "<glossary_guid:Sales Dictionary>"
      },
      "shortDescription": "Parent category for all product-related classifications"
  }
  POST https://atlas.example.com/api/atlas/v2/glossary/categories
  {
      "name": "Product Details",
      "anchor": {
          "glossaryGuid": "<glossary_guid:Sales Dictionary>"
      },
      "parentCategory": {
          "categoryGuid": "<category_guid:Sales Dictionary.Product Classifications>"
      }
  }
```

## Live Execution Mode (Actual API Calls)

Shows REST API calls **as they are executed** against a real Atlas instance:

```bash
uv run python main.py import-glossary --csv example_glossary.csv \
  --atlas-url https://atlas.example.com \
  --atlas-username admin \
  --atlas-password secret
```

Or disable dry-run in `config.yaml`:
```yaml
import:
  dry_run: false
```

Then run:
```bash
uv run python main.py import-glossary --csv example_glossary.csv
```

**Output includes:**
- → POST/PUT endpoint and payload
- ← Response GUID or status
- ✓ All actual API calls executed
- ✓ Real response GUIDs logged

**Example:**
```
→ POST https://atlas.example.com/api/atlas/v2/glossary
  {"name": "Sales Dictionary", "shortDescription": "Glossary: Sales Dictionary"}
← Response: g-123456

→ POST https://atlas.example.com/api/atlas/v2/glossary/categories
  {
      "name": "Product Classifications",
      "anchor": {"glossaryGuid": "g-123456"},
      "shortDescription": "Parent category for all product-related classifications"
  }
← Response: c-001

→ POST https://atlas.example.com/api/atlas/v2/glossary/categories
  {
      "name": "Product Details",
      "anchor": {"glossaryGuid": "g-123456"},
      "parentCategory": {"categoryGuid": "c-001"},
      "shortDescription": "Specific product information"
  }
← Response: c-002

→ POST https://atlas.example.com/api/atlas/v2/glossary/terms (batch: 4 terms)
  [
      {
          "name": "Product ID",
          "anchor": {"glossaryGuid": "g-123456"},
          "status": "Active",
          "shortDescription": "Unique product identifier",
          ...
      },
      ...
  ]
← Response: Product ID = t-001
← Response: Product Name = t-002
← Response: Product Category = t-003
← Response: Discount Amount = t-004

→ PUT https://atlas.example.com/api/atlas/v2/glossary/term/t-001
  {
      "relatedTerms": [{"termGuid": "t-002"}]
  }
← Response: Updated
```

## Interpreting the Logs

### Glossary Creation (Pass 2)
```
→ POST /v2/glossary
  {"name": "Sales Dictionary"}
← Response: g-123456
```
Creates a new glossary, returns GUID for use in subsequent passes.

### Category Creation (Pass 3)
```
→ POST /v2/glossary/categories
  {"name": "Product Details", "parentCategory": {"categoryGuid": "c-001"}}
← Response: c-002
```
Creates categories in parent-first order. Parent GUID is resolved from earlier in Pass 3.

### Term Creation (Pass 4)
```
→ POST /v2/glossary/terms (batch: 15 terms)
  [{"name": "Product ID", "anchor": {...}, "categories": [...]}, ...]
← Response: Product ID = t-001
← Response: Product Name = t-002
```
Batch creates terms with category associations. Returns individual GUIDs.

### Relationship Creation (Pass 5)
```
→ PUT /v2/glossary/term/t-001
  {"synonyms": [{"termGuid": "t-002"}]}
← Response: Updated
```
Updates terms with relationship links. GUIDs resolved from term_guid_map created in Pass 4.

## Comparison: Dry-Run vs Live

| Feature | Dry-Run | Live |
|---------|---------|------|
| API Calls | Shown as debug (not executed) | Actually executed |
| GUIDs | Placeholders `<guid:name>` | Real GUIDs from responses |
| Response Tracking | Simulated in output | From actual API responses |
| Validation | ✓ Full validation | ✓ Full validation |
| Safety | Very safe (no changes) | Makes real changes |
| Time | Fast (no network) | Depends on Atlas response time |

## Best Practices

1. **Always test with dry-run first:**
   ```bash
   uv run python main.py import-glossary --csv my_glossary.csv --dry-run
   ```

2. **Review the debug output** to verify:
   - ✓ Correct glossary names
   - ✓ Correct category hierarchy (parents before children)
   - ✓ Correct term attributes
   - ✓ Correct relationships

3. **Then execute against a test Atlas instance:**
   ```bash
   uv run python main.py import-glossary --csv my_glossary.csv \
     --atlas-url https://test-atlas.example.com \
     --atlas-username admin \
     --atlas-password secret
   ```

4. **Watch the REST call logs** to verify:
   - ✓ Correct HTTP status codes
   - ✓ Valid GUIDs returned
   - ✓ Proper order of execution (glossary → category → term → relationship)

5. **Only then run against production:**
   ```bash
   uv run python main.py import-glossary --csv my_glossary.csv \
     --atlas-url https://prod-atlas.example.com \
     --atlas-username admin \
     --atlas-password secret
   ```

## Troubleshooting

### No API calls in dry-run
This is expected! Dry-run shows theoretical calls. They are not executed.

### No API logs in live mode
Make sure `dry_run: false` in config.yaml or use without `--dry-run` flag.

### Logging to file instead of console
Logs are sent to stderr (console). If redirected:
```bash
# See logs
uv run python main.py import-glossary --csv my_glossary.csv 2>&1 | tee output.log

# Just capture logs
uv run python main.py import-glossary --csv my_glossary.csv 2>api_calls.log
```

### Enable debug logging
```bash
uv run python main.py import-glossary --csv my_glossary.csv --log-level DEBUG
```
