from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import brands, cities, malls, stores
from .routers import overview, districts, compare

settings = get_settings()

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


app.include_router(cities.router, prefix=settings.api_prefix)
app.include_router(malls.router, prefix=settings.api_prefix)
app.include_router(brands.router, prefix=settings.api_prefix)
app.include_router(stores.router, prefix=settings.api_prefix)
app.include_router(overview.router, prefix=settings.api_prefix)
app.include_router(districts.router, prefix=settings.api_prefix)
app.include_router(compare.router, prefix=settings.api_prefix)
