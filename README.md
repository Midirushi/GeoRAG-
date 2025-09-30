# GeoRAG: 地理实体增强的检索式问答系统



![GitHub Stars](https://img.shields.io/github/stars/your-username/georag?style=social)



![GitHub License](https://img.shields.io/github/license/your-username/georag)



![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)



![React Version](https://img.shields.io/badge/react-18%2B-blue)

A **Geospatial-Enhanced RAG System** that enables storage, retrieval, and Q\&A for geographic entities (e.g., locations, regions, spatial-temporal events). It combines vector search with spatial databases to answer location-aware questions, such as "What historical buildings are within 5km of the Forbidden City?" or "List rivers in the Yangtze River Delta built before 1950".

## 🌟 Core Features

### 1. Geographic Entity Management



* **Spatial Data Storage**: Store geographic entities (points, polygons, regions) with coordinates (WGS84) and metadata (address, admin division, time period).

* **Spatial Indexing**: Leverage PostGIS (PostgreSQL extension) for spatial queries (e.g., distance filtering, range selection).

### 2. Location-Aware RAG



* **Hybrid Retrieval**: Combine **vector semantic search** (Qdrant) with **spatial filtering** (PostGIS) to retrieve context relevant to both content and location.

* **Temporal-Spatial Q\&A**: Support time-range filters (e.g., "ancient China", "19th century") alongside geographic filters for precise results.

### 3. Intuitive Frontend



* **Interactive Map**: Visualize geographic entities, select search ranges (radius/area) via Leaflet/Mapbox.

* **Timeline Filter**: Quickly filter content by historical periods (e.g., Ming Dynasty, Qing Dynasty) or custom time ranges.

* **Streaming Q\&A**: Get real-time, chunked responses with source attribution (location + time + relevance score).

### 4. Easy Deployment



* **Dockerized**: All services (backend, database, vector store, frontend) packaged with Docker Compose for one-click startup.

* **Extensible**: Add new geographic data sources (e.g., CSV, GeoJSON, PDF) via the admin upload interface.

## 🛠️ Tech Stack



| Layer         | Tools & Frameworks                                           |
| ------------- | ------------------------------------------------------------ |
| **Backend**   | Python 3.11+, FastAPI, PostGIS (PostgreSQL), Qdrant (Vector DB), Redis (Cache) |
| **Frontend**  | React 18+, TypeScript, Leaflet (Map), Material UI, React-Vis-Timeline |
| **LLM & RAG** | OpenAI Embeddings (text-embedding-3-large), Anthropic Claude (Q\&A Generation) |
| **DevOps**    | Docker, Docker Compose, Nginx (Frontend Hosting)             |

## ⚡ Quick Start

### Prerequisites



* Docker & Docker Compose (v2.0+)

* Git

* API Keys (OpenAI/Anthropic, optional for local LLM replacement)

### Step 1: Clone the Repository



```
git clone https://github.com/your-username/georag.git

cd georag
```

### Step 2: Configure Environment Variables

Create a `.env` file in the root directory to set API keys and database credentials:



```
\# LLM API Keys (required for Q\&A)

OPENAI\_API\_KEY=sk-your-openai-key

ANTHROPIC\_API\_KEY=sk-ant-your-anthropic-key

\# Database Credentials (customize as needed)

POSTGRES\_USER=georag\_user

POSTGRES\_PASSWORD=georag\_password

POSTGRES\_DB=georag\_db

\# CORS (allow frontend access)

CORS\_ORIGINS=http://localhost
```

### Step 3: Start All Services



```
\# Build and start containers (first run may take 5-10 minutes)

docker-compose up -d --build

\# Verify services are running (all status should be "Up")

docker-compose ps
```

### Step 4: Access the System



* **Frontend**: Open `http://localhost` in your browser (interactive Q\&A + map).

* **Backend API Docs**: Visit `http://localhost:8000/api/v1/docs` (Swagger UI for testing APIs).

* **Admin Interface**: Go to `http://localhost/admin` (upload geographic documents).

## 📖 Usage Examples

### Example 1: Geographic Q\&A

**Question**: "What historical buildings are within 3km of the Forbidden City (Beijing) and built during the Ming Dynasty?"

**How to Use**:



1. On the map, center on the Forbidden City (lat: 39.917, lon: 116.397) and set radius to 3km.

2. On the timeline, select "Ming Dynasty (1368-1644)".

3. Enter the question and click "Send" — get streaming responses with sources.

### Example 2: Upload Geographic Data



1. Go to `http://localhost/admin` → "Document Upload".

2. Upload a CSV/GeoJSON file with columns like `title`, `content`, `latitude`, `longitude`, `start_year`, `end_year`.

3. Wait for processing (takes 1-2 minutes for small files).

4. Query the data (e.g., "Show all locations from my uploaded file").

### Example 3: Spatial Retrieval API

Use the backend API to retrieve geographic entities directly:



```
\# Request (get entities within 2km of Shanghai, 1900-2000)

curl -X GET "http://localhost:8000/api/v1/search?lat=31.2304\&lon=121.4737\&radius\_km=2\&start\_time=1900\&end\_time=2000" -H "Content-Type: application/json"
```

## 🗂️ Project Structure



```
georag/

├── backend/          # FastAPI backend

│   ├── app/          # Core logic (RAG, spatial DB, LLM)

│   ├── Dockerfile    # Backend container config

│   └── requirements.txt # Python dependencies

├── frontend/         # React frontend

│   ├── src/          # UI components (chat, map, timeline)

│   ├── Dockerfile    # Frontend container config

│   └── nginx.conf    # Nginx config for static hosting

├── docker-compose.yml # One-click deployment config

└── README.md         # Project docs (you're here!)
```

## 🚀 Extensions & Customization

### 1. Replace LLM with Local Models

To use open-source LLMs (e.g., Llama 3, Mistral) instead of cloud APIs:



1. Add a local LLM service (e.g., Ollama) to `docker-compose.yml`.

2. Modify `backend/app/services/``generator.py` to call the local LLM endpoint.

### 2. Add New Geographic Data Sources



* **GeoJSON/PDF/CSV**: Use the admin upload interface (supports spatial metadata extraction).

* **External APIs**: Integrate with OpenStreetMap/GeoNames by adding a data crawler in `backend/app/services/``data_loader.py`.

### 3. Customize Map Styles

Change the map base layer in `frontend/src/components/map/GeoMap.tsx` (supports Mapbox, Google Maps, or custom tiles).

## 🐛 Troubleshooting



* **Services not starting**: Check logs with `docker-compose logs -f backend` or `docker-compose logs -f postgres`.

* **LLM API errors**: Ensure API keys in `.env` are valid and have sufficient credits.

* **Map not loading**: Verify Leaflet/Mapbox tokens (add to `frontend/public/mapbox-token.js` if using Mapbox).

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Here's how to help:



1. Fork the repository.

2. Create a feature branch (`git checkout -b feature/spatial-filter`).

3. Commit your changes (`git commit -m "Add polygon spatial search"`).

4. Push to the branch (`git push origin feature/spatial-filter`).

5. Open a Pull Request.

Feel free to open issues for bugs, feature requests, or questions!

> （注：文档部分内容可能由 AI 生成）
