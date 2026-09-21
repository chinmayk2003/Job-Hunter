import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jobhunter-backend")

# Initialize FastAPI app with API metadata
app = FastAPI(
    title="JobHunter AI API",
    description="Production-grade API for job search, matching, and resume parsing.",
    version="1.0.0",
)

# CORS Configuration
# Allowed origins can be configured in production via environment variables
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:80",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/v1/health")
async def health_check():
    logger.info("Health check endpoint hit")
    return {
        "status": "healthy",
        "service": "JobHunter AI API",
        "message": "FastAPI backend is up and running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
