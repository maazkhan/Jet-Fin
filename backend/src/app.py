from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

from src.database.connection import DatabaseConnection
from src.api.routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FinOps Cost Intelligence Backend",
    description="Multi-tenant cost analytics platform",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
async def startup_event():
    DatabaseConnection.initialize()
    logger.info("Application started")

@app.on_event("shutdown")
async def shutdown_event():
    DatabaseConnection.close()
    logger.info("Application shutdown")

# Include API routes
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=True
    )
