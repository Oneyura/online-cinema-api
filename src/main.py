from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes.accounts import accounts_router
from src.routes.cart import router as cart_router
from src.routes.order import router as order_router

app = FastAPI(
    title="Online Cinema API",
    description="API for online cinema service",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)


# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(cart_router, prefix="/api")
app.include_router(order_router, prefix="/api")

app.include_router(accounts_router, prefix="/api/accounts", tags=["Authentication"])
