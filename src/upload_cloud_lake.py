import logging
import os
import sys
import time 
from pathlib import Path 
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("upload_cloud")

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

def upload_to_adls():

    AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_CONTAINER_NAME = os.getenv("AZURE_CONTAINER_NAME", "moi-crime-datalake")

    if AZURE_STORAGE_CONNECTION_STRING:
        logger.info("Azure Storage connection string found")
    else:
        logger.error("Azure Storage connection not found")
        sys.exit(1) 

    service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)

    files_to_upload = [
    (PROJECT_ROOT / "data" / "bronze_crime_news.json", "bronze/bronze_crime_news.json"),
    (PROJECT_ROOT / "data" / "silver_crime_news.parquet", "silver/silver_crime_news.parquet"),
    ]

    try:
        for local_path, blob_name in files_to_upload:
            if not local_path.exists():
                logger.error(f"Local file not found: {local_path}")
                sys.exit(1)

            logger.info(f"Uploading {local_path.name} -> {blob_name}...")

            blob_client = service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=blob_name)
            with open(local_path, "rb") as f:
                blob_client.upload_blob(f, overwrite=True)

            logger.info(f"Done uploading {blob_name}")
            
    except Exception as e:
        logger.error(f"Failed to upload to Azure Data Lake: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    upload_to_adls()
