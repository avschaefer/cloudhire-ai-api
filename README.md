# Cloudhire AI API

An automated exam grading service using Google Gemini AI, built with FastAPI.

## Features

- **Async Grading**: Uses Google Cloud Tasks for reliable background processing
- **AI-Powered**: Leverages Gemini 2.0 Flash for intelligent grading
- **Cost Tracking**: Monitors API usage and costs in real-time
- **Robust Error Handling**: Graceful fallbacks when AI grading fails
- **PDF Generation**: Creates professional reports using WeasyPrint
- **Supabase Integration**: Database and file storage via Supabase

## Quick Start

### 1. Environment Setup

```bash
# Copy the example environment file
cp env.example .env

# Edit .env with your actual values
# See env.example for detailed configuration
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

## API Endpoints

- `GET /health` - Health check
- `POST /v1/grade_jobs/submit` - Submit grading job (requires Bearer token)
- `POST /internal/tasks/grade` - Internal grading endpoint (Cloud Tasks target)

## Environment Variables

See `env.example` for complete configuration. Required variables include:

- **Supabase**: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **GCP**: `GCP_PROJECT`, `GCP_LOCATION`, `WORKER_URL`
- **AI**: `GEMINI_API_KEY`, `GEMINI_MODEL`
- **Security**: `SUBMIT_BEARER_TOKEN`
- **Webhook Signing (recommended)**: `AI_WEBHOOK_SECRET` (shared with Rails)

## Architecture

1. **Rails App** submits grading job via API
2. **FastAPI** queues job in Google Cloud Tasks
3. **Cloud Tasks** triggers background grading
4. **Gemini AI** evaluates each answer
5. **PDF Report** generated and stored in Supabase
6. **Optional webhook** notifies Rails of completion

## Development

### Running Tests
```bash
# Coming soon - unit tests for core functionality
```

### Local Development
- Set `GRADER_MODE=dummy` for testing without AI calls
- Use `LOG_LEVEL=DEBUG` for detailed logging
- All dependencies included in `requirements.txt`
