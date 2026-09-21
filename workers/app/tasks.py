import os
import time
import logging
from celery import Celery

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobhunter-worker")

# Read Celery configurations from environment variables
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

# Initialize Celery app
celery_app = Celery(
    "tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND
)

# Standard configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="app.tasks.parse_resume_task")
def parse_resume_task(resume_id: str, file_path: str):
    """
    Dummy background task simulating AI resume parsing.
    """
    logger.info(f"Starting resume parsing task for ID: {resume_id}")
    time.sleep(3) # Simulate parsing latency
    logger.info(f"Resume parsing completed for ID: {resume_id}")
    return {
        "status": "success",
        "resume_id": resume_id,
        "parsed_skills": ["Python", "FastAPI", "React", "Next.js", "Docker"],
        "experience_years": 5
    }

@celery_app.task(name="app.tasks.scrape_job_task")
def scrape_job_task(search_query: str, locations: list):
    """
    Dummy background task simulating web scraping of job descriptions.
    """
    logger.info(f"Starting job scraping task for query: '{search_query}' in {locations}")
    time.sleep(5) # Simulate scraping delay
    logger.info(f"Job scraping finished for query: '{search_query}'")
    return {
        "status": "success",
        "jobs_found": 12,
        "query": search_query
    }
