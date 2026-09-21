# JobHunter AI

JobHunter AI is a production-grade AI-powered job hunting platform designed to automate and optimize the process of finding, matching, and applying to jobs. The system uses a monorepo architecture leveraging Next.js on the frontend, FastAPI on the backend, PostgreSQL for data storage, and Celery with Redis for background task automation.

---

## 🛠 Tech Stack

- **Frontend**: Next.js 14 (App Router), Tailwind CSS, ShadCN UI, Zustand, TanStack Query
- **Backend API**: FastAPI (Python 3.11), SQLAlchemy ORM, Alembic Migrations
- **Workers**: Celery task runner for AI resume parsing, Web scraping, and job matching jobs
- **Storage**: PostgreSQL (Relational Database), Redis (Caching & Celery Broker), Cloudflare R2 (S3-compatible Object Storage for resumes/media)
- **Authentication**: Clerk (User identity and session management)
- **Infrastructure**: Nginx (Reverse proxy & load balancer), Docker Compose (Containerization)

---

## 📂 Project Structure

```text
JobHunter/
├── .env.example              # Environment variables template
├── .gitignore                # Root gitignore ignoring node & python temp files
├── README.md                 # Project setup and documentation
├── docker-compose.yml        # Multi-container orchestrator config
├── frontend/                 # Next.js frontend application
│   ├── src/                  # Next.js App Router code
│   ├── Dockerfile            # Multi-stage Docker config for Next.js
│   ├── package.json          # Node dependencies & scripts
│   └── tailwind.config.ts    # Tailwind/ShadCN layout styling
├── backend/                  # FastAPI Python backend application
│   ├── app/                  # FastAPI routes, schemas, models, and core logic
│   │   └── main.py           # Application entry point & health checks
│   ├── Dockerfile            # Multi-stage Docker config for FastAPI
│   └── requirements.txt      # Python dependencies list
├── workers/                  # Celery background worker application
│   ├── app/                  # Celery application configuration & tasks
│   │   └── tasks.py          # Celery background tasks (scrapers, parsers)
│   ├── Dockerfile            # Docker configuration for worker execution
│   └── requirements.txt      # Workers dependencies list
└── infra/                    # DevOps and infrastructure files
    └── nginx/                # Reverse proxy
        ├── Dockerfile        # Custom Nginx image
        └── nginx.conf        # Proxy routing rules
```

---

## 🚀 Getting Started

### 📋 Prerequisites

Ensure you have the following installed on your machine:
- [Docker](https://www.docker.com/products/docker-desktop/) (and Docker Compose V2)
- [Node.js 20+](https://nodejs.org/) (for local development without Docker)
- [Python 3.11+](https://www.python.org/) (for local development without Docker)

---

### ⚙️ Step 1: Environment Variables

Clone this template repository and copy the environment template to create your `.env` configuration:

```bash
cp .env.example .env
```

Open `.env` and supply placeholders or actual values. For local Docker Compose setup, default values are pre-filled for PostgreSQL and Redis connection settings. You must replace Clerk and Cloudflare R2 keys with your personal developer credentials.

---

### 🐳 Step 2: Spin Up Containers

Run the following command in the root folder to build and start all microservices:

```bash
docker compose up --build
```

To run the containers in detached (background) mode, use:

```bash
docker compose up --build -d
```

---

### 🔍 Step 3: Verify Port Access

Once the containers start, Nginx will reverse-proxy incoming traffic on standard port `80`. Access the services via these URLs:

| Service | Host URL | Container Port | Description |
| :--- | :--- | :--- | :--- |
| **Frontend Web App** | [http://localhost](http://localhost) | `3000` | Next.js landing and search page |
| **Backend FastAPI** | [http://localhost/api/v1/health](http://localhost/api/v1/health) | `8000` | FastAPI health status API check |
| **FastAPI Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | `8000` | OpenAPI Swagger Documentation |
| **Flower Dashboard** | [http://localhost/flower](http://localhost/flower) | `5555` | Celery task monitoring dashboard |

---

## 🧑‍💻 Local Development Guidelines

### Development Volumes
The `docker-compose.yml` mounts code directories (`./frontend`, `./backend`, `./workers`) directly into their respective containers. Any file edits you make on your host system will immediately trigger hot reloading:
- Next.js (Fast Refresh) will update the web interface in the browser.
- FastAPI (Uvicorn reload) will reboot the API endpoints instantly.
- Celery worker processes will require a service reboot (`docker compose restart worker`) to detect changes in tasks.

### Stopping the Services

To shut down all services, preserve databases, and stop containers, run:

```bash
docker compose down
```

To completely delete stored Docker volumes (re-initialize database and cache), run:
```bash
docker compose down -v
```
