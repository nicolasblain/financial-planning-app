from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from database import Base, engine
from routers import auth_routes, client_routes, planner_routes

# Create tables (use Alembic migrations in production)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Financial Planning Tool")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_routes.router)
app.include_router(client_routes.router)
app.include_router(planner_routes.router)


@app.get("/")
async def root(request: Request):
    return RedirectResponse(url="/login")
