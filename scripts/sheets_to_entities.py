#!/usr/bin/env python3
"""
Google Sheets to Entity Files Conversion Script

Converts Google Sheets CSV export to schema-compliant entity markdown files.
Preserves the field mappings and JSON transformations from your Airtable design.

Usage:
    python scripts/sheets_to_entities.py input.csv
"""

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
import yaml


def create_slug(title):
    """Convert title to slug-style ID (matches your Airtable formula)"""
    if not title:
        return "untitled"
    
    # Remove punctuation, convert to lowercase, replace spaces with hyphens
    slug = re.sub(r'[^a-zA-Z0-9\s]', '', title.lower())
    slug = re.sub(r'\s+', '-', slug.strip())
    return slug


def parse_key_value_pairs(text):
    """Convert 'key:value, key:value' format to JSON object"""
    if not text or text.strip() == "":
        return "{}"
    
    # Simple parsing of key:value pairs
    pairs = {}
    for item in text.split(','):
        item = item.strip()
        if ':' in item:
            key, value = item.split(':', 1)
            pairs[key.strip()] = value.strip()
    
    return json.dumps(pairs) if pairs else "{}"


def convert_to_json_field(raw_text):
    """Convert raw text to {"raw": "..."} format like your Airtable formulas"""
    if not raw_text or raw_text.strip() == "":
        return "{}"
    
    return json.dumps({"raw": raw_text.strip()})


def process_row(row):
    """Process a single CSV row into entity data"""
    # Map CSV columns to entity fields (adjust column names as needed)
    title = row.get('Title', '').strip()
    content_kind = row.get('Content Kind', 'note').strip()
    status = row.get('Status', 'draft').strip()
    visibility = row.get('Visibility', 'private').strip()  
    provenance = row.get('Provenance', '1p').strip()
    description = row.get('Description', '').strip()
    version = row.get('Version', '1.0').strip()
    
    # Process JSON fields using your Airtable approach
    attribution_raw = row.get('Attribution', '')
    metadata_raw = row.get('Metadata', '')
    file_links_raw = row.get('File Links', '')
    notes = row.get('Notes', '')
    
    # Generate timestamps
    now = datetime.utcnow().isoformat() + 'Z'
    published_at = now if status == 'published' else None
    
    entity_data = {
        'id': create_slug(title),
        'content_kind': content_kind,
        'title': title,
        'version': version,
        'visibility': visibility,
        'status': status,
        'provenance': provenance,
        'filespec': convert_to_json_field(file_links_raw),
        'attribution': convert_to_json_field(attribution_raw),
        'metadata': convert_to_json_field(metadata_raw),
        'created_at': now,
        'updated_at': now,
    }
    
    if published_at:
        entity_data['published_at'] = published_at
    
    # Build markdown content
    content_sections = []
    
    if description:
        content_sections.extend([
            "## Description",
            "",
            description,
            ""
        ])
    
    if notes:
        content_sections.extend([
            "## Notes", 
            "",
            notes,
            ""
        ])
    
    content = "\n".join(content_sections) if content_sections else f"# {title}\n\n*Content to be added*"
    
    return entity_data, content


def create_entity_file(entity_data, content, output_dir):
    """Create markdown file with YAML frontmatter"""
    filename = f"{entity_data['id']}.md"
    filepath = output_dir / filename
    
    # Create YAML frontmatter (remove None values)
    frontmatter = {k: v for k, v in entity_data.items() if v is not None}
    
    # Build file content
    file_content = "---\n"
    file_content += yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    file_content += "---\n\n"
    file_content += content
    
    # Write file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(file_content)
    
    return filepath


def main():
    if len(sys.argv) != 2:
        print("Usage: python sheets_to_entities.py input.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_dir = Path("entities")
    output_dir.mkdir(exist_ok=True)
    
    print(f"Converting {input_file} to entity files...")
    
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            converted = 0
            for row in reader:
                # Skip empty rows
                if not any(row.values()):
                    continue
                
                try:
                    entity_data, content = process_row(row)
                    filepath = create_entity_file(entity_data, content, output_dir)
                    print(f"Created: {filepath}")
                    converted += 1
                    
                except Exception as e:
                    print(f"Error processing row {reader.line_num}: {e}")
                    continue
            
            print(f"\nConversion complete! Created {converted} entity files in {output_dir}/")
            print("\nNext steps:")
            print("1. Review generated files")
            print("2. Edit content as needed")  
            print("3. git add entities/ && git commit")
            
    except FileNotFoundError:
        print(f"Error: File {input_file} not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()