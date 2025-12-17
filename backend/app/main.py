from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.api import quotes, settings, clients, projects, materials, project_config, users, financial, blocked_domains, financial_v2, batch_quotes, debug_serpapi, vehicle_prices
from app.core.database import engine, Base
from app.core.logging import setup_logging
import logging
import time
import os

# Configurar logging estruturado
setup_logging(level="INFO", json_logs=True)
logger = logging.getLogger(__name__)

# Configurar rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

app = FastAPI(
    title="Sistema de Cotação de Preços",
    description="API para cotação de produtos com OCR, visão computacional e busca automatizada",
    version="1.0.0"
)

# Adicionar limiter ao app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configurar CORS - permitir todas as origens para Railway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info("CORS configured: allow all origins")

# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    duration_ms = (time.time() - start_time) * 1000

    logger.info(
        "HTTP Request",
        extra={
            'http': {
                'method': request.method,
                'path': request.url.path,
                'status_code': response.status_code,
                'duration_ms': round(duration_ms, 2)
            },
            'ip_address': request.client.host if request.client else None
        }
    )

    return response


app.include_router(quotes.router)
app.include_router(settings.router)
app.include_router(clients.router)
app.include_router(projects.router)
app.include_router(materials.router)
app.include_router(project_config.router)
app.include_router(users.router)
app.include_router(financial.router)
app.include_router(financial_v2.router)
app.include_router(blocked_domains.router)
app.include_router(batch_quotes.router)
app.include_router(debug_serpapi.router)
app.include_router(vehicle_prices.router)


@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up", extra={'event': 'startup'})


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down", extra={'event': 'shutdown'})


@app.get("/")
def root():
    return {
        "message": "Sistema de Cotação de Preços API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    logger.debug("Health check performed")
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
