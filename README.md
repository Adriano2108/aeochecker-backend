# AEO Checker Backend

A FastAPI backend for analyzing websites AEO. This API provides endpoints for website analysis report generation and user management.

## Getting Started

### Prerequisites

- Python 3.8+
- Firebase project with Admin SDK credentials

### Installation

1. Clone the repository
2. Create and activate a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Set up your environment variables:
   Create a `.env` file with:
   ```
   FIREBASE_SERVICE_ACCOUNT_KEY_PATH=/path/to/your/firebase-adminsdk.json
   ```

### Running the API

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at http://localhost:8000

API docs are available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Building and Running the container:

# Build and run the container with your .env file (better, can view the logs)
- docker compose up --build
# Run in detached mode (no logs, in the background)
- docker compose up -d --build
# Stop the container
- docker compose down

## To push the docker container to google cloud run:
1. gcloud run deploy aeochecker-backend --source . --region us-east4 --allow-unauthenticated

## API Endpoints

### Website Analysis
- `POST /api/v1/analysis/analyze` - Submit a URL for analysis
- `GET /api/v1/analysis/status/{job_id}` - Get analysis job status
- `GET /api/v1/analysis/reports/{job_id}` - Get completed analysis report

### User Data
- `GET /api/v1/users/me` - Get current user data
- `GET /api/v1/users/me/reports` - Get current user's analysis reports# aeochecker-backend
