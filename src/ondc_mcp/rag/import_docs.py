import os
import json
import logging
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "rag" / "docs"
INDEX_PATH = DOCS_DIR / "schema_index.faiss"
METADATA_PATH = DOCS_DIR / "schema_metadata.json"

def parse_csvs(docs_dir: Path) -> list[dict]:
    """Parse CSV files from docs directory into structured chunks."""
    chunks = []
    
    if not docs_dir.exists():
        logger.warning(f"Docs dir {docs_dir} does not exist.")
        return chunks

    for csv_file in docs_dir.glob("open_data_prod_docs_*.csv"):
        logger.info(f"Parsing {csv_file.name}")
        try:
            # We must be careful as some CSVs might have different columns if empty or weirdly formatted
            df = pd.read_csv(csv_file, dtype=str).fillna("")
        except Exception as e:
            logger.error(f"Failed to read {csv_file}: {e}")
            continue

        current_table = None
        current_columns = []
        
        def commit_table():
            if current_table:
                # Build markdown representation
                content = f"Table: {current_table['full_name']}\n"
                content += f"Type: {current_table['type']}\n"
                if current_table['ddl']:
                    content += f"DDL/View Logic: {current_table['ddl']}\n"
                content += "\nColumns:\n"
                for col in current_columns:
                    desc = col['desc']
                    logic = f" (Formula: {col['logic']})" if col['logic'] else ""
                    content += f"- {col['name']}: {desc}{logic}\n"
                
                chunks.append({
                    "table_name": current_table['full_name'],
                    "schema": current_table['schema'],
                    "content": content,
                })

        for _, row in df.iterrows():
            col1 = str(row.iloc[0]).strip()
            
            if col1.startswith("▼"):
                commit_table()
                
                # Parse table header
                # '▼ table_name   (type, X cols)'
                tname_part = col1[1:].split("(")[0].strip()
                type_part = col1.split("(")[1].split(",")[0].strip() if "(" in col1 else "table"
                full_name = str(row.iloc[3]).strip() if len(row) > 3 else tname_part
                schema = full_name.split(".")[0] if "." in full_name else "public"
                
                ddl = str(row.iloc[4]).strip() if len(row) > 4 else ""
                
                current_table = {
                    "name": tname_part,
                    "full_name": full_name,
                    "schema": schema,
                    "type": type_part,
                    "ddl": ddl
                }
                current_columns = []
            elif current_table and col1 and col1 != "Column Name":
                # Parse column
                desc = str(row.iloc[1]).strip() if len(row) > 1 else ""
                logic = str(row.iloc[2]).strip() if len(row) > 2 else ""
                current_columns.append({
                    "name": col1,
                    "desc": desc,
                    "logic": logic
                })
        
        commit_table() # commit last table
        
    return chunks

def build_index():
    logger.info("Starting schema ingestion...")
    chunks = parse_csvs(DOCS_DIR)
    if not chunks:
        logger.error("No chunks parsed. Aborting index build.")
        return

    logger.info(f"Loaded {len(chunks)} tables. Initializing model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    texts = [c["content"] for c in chunks]
    logger.info("Encoding texts...")
    embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)
    
    logger.info(f"Saving index to {INDEX_PATH}...")
    faiss.write_index(index, str(INDEX_PATH))
    
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)
        
    logger.info("Ingestion complete.")

if __name__ == "__main__":
    build_index()
