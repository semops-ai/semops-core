# Scripts Directory

Shared tooling for SemOps platform and connected projects. These scripts will be `python` or `bash` scripts to perform common tasks related to data transformation, schema validation, updating repo dependencies, environment setup, and other operations.

## Environment Setup Scripts

### start.py
**Feature-rich startup script with health checks**

```bash
# Start all services with health checks
python scripts/start.py

# Start services AND initialize schema
python scripts/start.py --init-schema
```

**Features:**
- ✅ Docker health checks
- ✅ Service availability verification
- ✅ Port connectivity testing
- ✅ Optional schema initialization
- ✅ Detailed status reporting
- ✅ Comprehensive next steps guide

### setup_supabase.py
**Clone and prepare the Supabase repository**

```bash
python scripts/setup_supabase.py
```

**What it does:**
- Clones Supabase repo using sparse checkout (docker/ folder only)
- Copies .env to supabase/docker/.env
- Updates existing clone if already present

### init_schema.py
**Initialize the Phase 1 database schema**

```bash
python scripts/init_schema.py
```

**What it does:**
- Waits for PostgreSQL to be ready
- Executes schemas/phase1-schema.sql
- Creates: entity, edge, surface, surface_address, delivery tables
- Shows verification queries
- Displays next steps

## Root-Level Start Script

The repository also includes **`../start_services.py`** (borrowed from local-ai-packaged) at the root level:

```bash
# Simple all-in-one startup
python start_services.py

# Skip Supabase clone if already done
python start_services.py --skip-clone
```

**Use this for:** Quick daily startup with minimal output

**Use scripts/start.py for:** Detailed health checks and troubleshooting

## Data Transformation Scripts

### Example:
## sheets_to_entities.py

Converts Google Sheets CSV export to schema-compliant entity markdown files.

**Usage:**
```bash
# Export your Google Sheet as CSV, then:
python scripts/sheets_to_entities.py capture_data.csv
```

**Features:**
- Preserves Airtable field mappings and JSON transformations
- Generates slug-style IDs from titles  
- Converts key:value pairs to `{"raw": "..."}` JSON format
- Creates proper YAML frontmatter matching schema
- Handles all content types (notes, concepts, research, etc.)

**Expected CSV columns:**
- Title (required)
- Content Kind (article, video, document, note, concept, research, etc.)
- Status (draft, published, archived)
- Visibility (public, private)
- Provenance (1p, 2p, 3p)
- Description
- Version
- Attribution (key:value pairs)
- Metadata (key:value pairs)  
- File Links (raw text)
- Notes

**Output:**
- Creates files in `entities/` directory
- Filename matches slug-style ID
- YAML frontmatter + markdown content
- Ready for git commit
