from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from auth import require_role
from database import get_db
from models.user import User, UserRole
from models.client_profile import ClientProfile, CycleStage
from models.intake import IntakeResponse

router = APIRouter(prefix="/planner")
templates = Jinja2Templates(directory="templates")

STAGE_LABELS = {
    CycleStage.INTAKE: "Intake",
    CycleStage.GOALS: "Goals",
    CycleStage.ANALYSIS: "Analysis",
    CycleStage.PLAN_DRAFTING: "Plan Drafting",
    CycleStage.PLAN_DELIVERY: "Plan Delivery",
    CycleStage.MONITORING: "Monitoring",
}

INTAKE_SECTION_COUNT = 6


@router.get("/pipeline", response_class=HTMLResponse)
async def pipeline(
    request: Request,
    user: User = Depends(require_role(UserRole.PLANNER)),
    db: Session = Depends(get_db),
):
    clients = (
        db.query(ClientProfile)
        .filter(ClientProfile.planner_id == user.id)
        .all()
    )

    pipeline = {}
    for stage in CycleStage:
        pipeline[stage] = {
            "label": STAGE_LABELS[stage],
            "clients": [],
        }

    for client in clients:
        responses = db.query(IntakeResponse).filter(
            IntakeResponse.client_id == client.id,
            IntakeResponse.is_complete == True,
        ).count()
        client._intake_progress = int(responses / INTAKE_SECTION_COUNT * 100)
        pipeline[client.cycle_stage]["clients"].append(client)

    return templates.TemplateResponse("planner/pipeline.html", {
        "request": request,
        "user": user,
        "pipeline": pipeline,
    })


@router.get("/client/{client_id}", response_class=HTMLResponse)
async def client_detail(
    client_id: int,
    request: Request,
    user: User = Depends(require_role(UserRole.PLANNER)),
    db: Session = Depends(get_db),
):
    client = db.query(ClientProfile).filter(
        ClientProfile.id == client_id,
        ClientProfile.planner_id == user.id,
    ).first()

    if not client:
        return HTMLResponse("Client not found", status_code=404)

    responses = db.query(IntakeResponse).filter(IntakeResponse.client_id == client.id).all()
    completed = {r.section_key for r in responses if r.is_complete}
    missing = [s for s in ["personal", "income", "assets", "liabilities", "protection", "tax"] if s not in completed]

    return templates.TemplateResponse("planner/client_detail.html", {
        "request": request,
        "user": user,
        "client": client,
        "completed_sections": completed,
        "missing_sections": missing,
    })
