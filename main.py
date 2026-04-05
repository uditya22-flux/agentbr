"""
AgentBridge v6 — Full B2B SaaS Platform
Multi-tenant AI compliance monitoring & enforcement.
"""
from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(
    title="AgentBridge B2B SaaS",
    version="6.0.0",
    description="RBI FREE-AI Compliance Platform for Multi-tenant AI Monitoring",
)

# CORS config
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth context and middleware
from gateway.security import auth_middleware
app.middleware("http")(auth_middleware)

# --- ROUTERS ---
from routes.auth_routes import router as auth_router
from routes.agent_management import router as agent_router
from routes.dashboard_stats import router as dashboard_router
from routes.gateway_routes import router as sdk_gateway_router
from routes.intelligence import router as intelligence_router
from routes.settings_routes import router as settings_router
from routes.manual_log import router as manual_router
from routes.report_routes import router as report_router

app.include_router(auth_router)
app.include_router(agent_router)
app.include_router(dashboard_router)
app.include_router(sdk_gateway_router)
app.include_router(intelligence_router)
app.include_router(settings_router)
app.include_router(manual_router)
app.include_router(report_router)

# Serve Frontend
@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse("dashboard.html")

@app.get("/{page}.html", include_in_schema=False)
async def serve_static_page(page: str):
    path = f"{page}.html"
    if os.path.exists(path):
        return FileResponse(path)
    return JSONResponse(status_code=404, content={"detail": "Page not found"})

@app.get("/health")
def health():
    return {
        "status": "online",
        "platform": "AgentBridge v6",
        "tenancy": "multi-tenant enabled"
    }

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
