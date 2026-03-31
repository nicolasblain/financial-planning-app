import json

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from auth import require_role
from database import get_db
from models.user import User, UserRole
from models.client_profile import ClientProfile, CycleStage
from models.intake import IntakeSection, IntakeResponse
from models.goal import Goal

router = APIRouter(prefix="/client")
templates = Jinja2Templates(directory="templates")

INTAKE_SECTIONS = [
    {"key": "personal", "title": "Personal Information", "description": "Basic details about you and your household."},
    {"key": "income", "title": "Income", "description": "Your employment income, side income, and any other revenue sources."},
    {"key": "assets", "title": "Assets", "description": "Savings accounts, investments, RRSPs, TFSAs, property, and other assets you own."},
    {"key": "liabilities", "title": "Liabilities", "description": "Mortgages, loans, credit card balances, and other debts."},
    {"key": "protection", "title": "Protection & Insurance", "description": "Life insurance, disability, critical illness, and group benefits."},
    {"key": "tax", "title": "Tax Situation", "description": "Recent tax returns, contribution room, and any relevant tax considerations."},
]


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    user: User = Depends(require_role(UserRole.CLIENT)),
    db: Session = Depends(get_db),
):
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    if not profile:
        profile = ClientProfile(user_id=user.id)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    responses = db.query(IntakeResponse).filter(IntakeResponse.client_id == profile.id).all()
    completed_sections = {r.section_key for r in responses if r.is_complete}
    goals = db.query(Goal).filter(Goal.client_id == profile.id).all()

    return templates.TemplateResponse("client/dashboard.html", {
        "request": request,
        "user": user,
        "profile": profile,
        "sections": INTAKE_SECTIONS,
        "completed_sections": completed_sections,
        "goals": goals,
        "intake_progress": len(completed_sections) / len(INTAKE_SECTIONS) * 100,
    })


@router.get("/intake/{section_key}", response_class=HTMLResponse)
async def intake_section(
    section_key: str,
    request: Request,
    user: User = Depends(require_role(UserRole.CLIENT)),
    db: Session = Depends(get_db),
):
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    section = next((s for s in INTAKE_SECTIONS if s["key"] == section_key), None)
    existing = db.query(IntakeResponse).filter(
        IntakeResponse.client_id == profile.id,
        IntakeResponse.section_key == section_key,
    ).first()

    return templates.TemplateResponse("client/intake_section.html", {
        "request": request,
        "user": user,
        "section": section,
        "existing": existing,
    })


@router.post("/intake/{section_key}", response_class=HTMLResponse)
async def save_intake(
    section_key: str,
    request: Request,
    user: User = Depends(require_role(UserRole.CLIENT)),
    db: Session = Depends(get_db),
):
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    form_data = await request.form()
    data_dict = {k: v for k, v in form_data.items() if k != "is_complete"}

    existing = db.query(IntakeResponse).filter(
        IntakeResponse.client_id == profile.id,
        IntakeResponse.section_key == section_key,
    ).first()

    if existing:
        existing.data = json.dumps(data_dict)
        existing.is_complete = "is_complete" in form_data
    else:
        response = IntakeResponse(
            client_id=profile.id,
            section_key=section_key,
            data=json.dumps(data_dict),
            is_complete="is_complete" in form_data,
        )
        db.add(response)
    db.commit()

    return templates.TemplateResponse("components/intake_saved.html", {
        "request": request,
        "section_key": section_key,
        "saved": True,
    })


@router.get("/goals", response_class=HTMLResponse)
async def goals_page(
    request: Request,
    user: User = Depends(require_role(UserRole.CLIENT)),
    db: Session = Depends(get_db),
):
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    goals = db.query(Goal).filter(Goal.client_id == profile.id).order_by(Goal.priority.desc()).all()
    return templates.TemplateResponse("client/goals.html", {
        "request": request,
        "user": user,
        "goals": goals,
    })


@router.post("/goals", response_class=HTMLResponse)
async def add_goal(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(""),
    time_horizon: str = Form(""),
    user: User = Depends(require_role(UserRole.CLIENT)),
    db: Session = Depends(get_db),
):
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    goal = Goal(
        client_id=profile.id,
        title=title,
        description=description,
        category=category,
        time_horizon=time_horizon,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)

    return templates.TemplateResponse("components/goal_item.html", {
        "request": request,
        "goal": goal,
    })


def _parse_number(val: str) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _load_section_data(db: Session, profile_id: int, section_key: str) -> dict:
    resp = db.query(IntakeResponse).filter(
        IntakeResponse.client_id == profile_id,
        IntakeResponse.section_key == section_key,
    ).first()
    if resp and resp.data:
        return json.loads(resp.data)
    return {}


@router.get("/overview", response_class=HTMLResponse)
async def financial_overview(
    request: Request,
    user: User = Depends(require_role(UserRole.CLIENT)),
    db: Session = Depends(get_db),
):
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    if not profile:
        return RedirectResponse(url="/client/dashboard")

    # Gather all intake data
    income_data = _load_section_data(db, profile.id, "income")
    assets_data = _load_section_data(db, profile.id, "assets")
    liabilities_data = _load_section_data(db, profile.id, "liabilities")
    protection_data = _load_section_data(db, profile.id, "protection")
    tax_data = _load_section_data(db, profile.id, "tax")

    # Assets breakdown
    assets = {
        "Chequing & Savings": _parse_number(assets_data.get("chequing_savings")),
        "RRSP": _parse_number(assets_data.get("rrsp")),
        "TFSA": _parse_number(assets_data.get("tfsa")),
        "Other Investments": _parse_number(assets_data.get("other_investments")),
        "Property": _parse_number(assets_data.get("property_value")),
    }
    total_assets = sum(assets.values())

    # Liabilities breakdown
    liabilities = {
        "Mortgage": _parse_number(liabilities_data.get("mortgage")),
        "Car Loan": _parse_number(liabilities_data.get("car_loan")),
        "Student Loan": _parse_number(liabilities_data.get("student_loan")),
        "Credit Cards": _parse_number(liabilities_data.get("credit_cards")),
        "Other Debts": _parse_number(liabilities_data.get("other_debts")),
    }
    total_liabilities = sum(liabilities.values())

    # Income breakdown
    income = {
        "Employment": _parse_number(income_data.get("employment_income")),
        "Other": _parse_number(income_data.get("other_income")),
    }
    total_income = sum(income.values())

    # Net worth
    net_worth = total_assets - total_liabilities

    # Tax room
    tax_room = {
        "RRSP Room": _parse_number(tax_data.get("rrsp_room")),
        "TFSA Room": _parse_number(tax_data.get("tfsa_room")),
    }

    # Protection
    life_insurance = _parse_number(protection_data.get("life_insurance"))
    disability_insurance = protection_data.get("disability_insurance", "none")
    group_benefits = protection_data.get("group_benefits", "no")

    # Goals
    goals = db.query(Goal).filter(Goal.client_id == profile.id).order_by(Goal.priority.desc()).all()

    # Check if there is any data at all
    has_data = total_assets > 0 or total_liabilities > 0 or total_income > 0

    return templates.TemplateResponse("client/overview.html", {
        "request": request,
        "user": user,
        "has_data": has_data,
        "assets": assets,
        "total_assets": total_assets,
        "liabilities": liabilities,
        "total_liabilities": total_liabilities,
        "income": income,
        "total_income": total_income,
        "net_worth": net_worth,
        "tax_room": tax_room,
        "life_insurance": life_insurance,
        "disability_insurance": disability_insurance,
        "group_benefits": group_benefits,
        "goals": goals,
        # JSON for Chart.js
        "assets_json": json.dumps(assets),
        "liabilities_json": json.dumps(liabilities),
        "income_json": json.dumps(income),
    })


@router.get("/projections", response_class=HTMLResponse)
async def projections_page(
    request: Request,
    user: User = Depends(require_role(UserRole.CLIENT)),
    db: Session = Depends(get_db),
    # Allow overrides via query params (from HTMX sliders)
    retirement_age: int = 0,
    savings_rate: float = 0,
    income_growth: float = 0,
    inflation: float = 0,
    investment_return: float = 0,
    retirement_income_pct: float = 0,
):
    from datetime import date
    from projections import ProjectionParams, run_projection

    profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    if not profile:
        return RedirectResponse(url="/client/dashboard")

    # Load intake data
    personal_data = _load_section_data(db, profile.id, "personal")
    income_data = _load_section_data(db, profile.id, "income")
    assets_data = _load_section_data(db, profile.id, "assets")

    # Calculate age from DOB
    dob_str = personal_data.get("date_of_birth", "")
    current_age = 30  # default
    if dob_str:
        try:
            dob = date.fromisoformat(dob_str)
            today = date.today()
            current_age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        except ValueError:
            pass

    emp_income = _parse_number(income_data.get("employment_income"))
    other_income = _parse_number(income_data.get("other_income"))

    # Current invested savings (exclude property)
    current_savings = sum([
        _parse_number(assets_data.get("chequing_savings")),
        _parse_number(assets_data.get("rrsp")),
        _parse_number(assets_data.get("tfsa")),
        _parse_number(assets_data.get("other_investments")),
    ])

    # Build params — use query overrides if provided, otherwise smart defaults
    params = ProjectionParams(
        current_age=current_age,
        retirement_age=retirement_age if retirement_age > 0 else 65,
        employment_income=emp_income,
        other_income=other_income,
        savings_rate=savings_rate if savings_rate > 0 else 20.0,
        income_growth_rate=income_growth if income_growth > 0 else 2.5,
        inflation_rate=inflation if inflation > 0 else 2.0,
        investment_return=investment_return if investment_return > 0 else 5.0,
        retirement_income_pct=retirement_income_pct if retirement_income_pct > 0 else 70.0,
        current_savings=current_savings,
    )

    projections = run_projection(params)

    # Prepare JSON data for charts
    chart_data = {
        "ages": [p.age for p in projections],
        "gross_income": [p.gross_income for p in projections],
        "total_tax": [p.total_tax for p in projections],
        "after_tax_income": [p.after_tax_income for p in projections],
        "spending": [p.spending for p in projections],
        "annual_savings": [p.annual_savings for p in projections],
        "cumulative_savings": [p.cumulative_savings for p in projections],
        "effective_rate": [p.effective_rate for p in projections],
    }

    # Key milestones
    retirement_year = next((p for p in projections if p.is_retired), None)
    peak_income = max(projections, key=lambda p: p.gross_income)
    peak_savings = max(projections, key=lambda p: p.cumulative_savings)

    # Determine if this is an HTMX partial request
    is_htmx = request.headers.get("HX-Request") == "true"

    template_name = "components/projection_charts.html" if is_htmx else "client/projections.html"

    return templates.TemplateResponse(template_name, {
        "request": request,
        "user": user,
        "params": params,
        "projections": projections,
        "chart_data_json": json.dumps(chart_data),
        "retirement_year": retirement_year,
        "peak_income": peak_income,
        "peak_savings": peak_savings,
        "has_data": emp_income > 0 or other_income > 0,
    })
