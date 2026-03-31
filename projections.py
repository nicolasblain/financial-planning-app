"""
Financial projection engine.

Projects income, taxes, spending, and savings year-by-year until age 100.
Uses 2025 Canadian federal + Quebec provincial tax brackets.
"""

from dataclasses import dataclass, field
from datetime import date


# --- 2025 Federal Tax Brackets ---
FEDERAL_BRACKETS = [
    (57_375, 0.15),
    (57_375, 0.205),    # 57,375 to 114,750
    (63_000, 0.26),     # 114,750 to 177,750
    (75_000, 0.29),     # 177,750 to 252,750
    (float("inf"), 0.33),  # above 252,750
]

FEDERAL_BASIC_PERSONAL = 16_129

# --- 2025 Quebec Provincial Tax Brackets ---
QUEBEC_BRACKETS = [
    (53_255, 0.14),
    (53_250, 0.19),     # 53,255 to 106,505
    (23_495, 0.24),     # 106,505 to 130,000 (approx)
    (float("inf"), 0.2575),
]

QUEBEC_BASIC_PERSONAL = 18_056

# QPP/CPP + EI approximations (employee)
CPP_RATE = 0.0595
CPP_MAX_EARNINGS = 71_300
CPP_BASIC_EXEMPTION = 3_500
CPP_MAX_CONTRIBUTION = 4_034  # approximate

EI_RATE = 0.0132  # Quebec rate (lower due to QPIP)
EI_MAX_INSURABLE = 65_700
EI_MAX_CONTRIBUTION = 867

QPIP_RATE = 0.00494
QPIP_MAX_INSURABLE = 94_000


def calculate_federal_tax(taxable_income: float) -> float:
    income_after_personal = max(0, taxable_income - FEDERAL_BASIC_PERSONAL)
    tax = 0.0
    remaining = income_after_personal
    for bracket_size, rate in FEDERAL_BRACKETS:
        taxable_in_bracket = min(remaining, bracket_size)
        tax += taxable_in_bracket * rate
        remaining -= taxable_in_bracket
        if remaining <= 0:
            break
    return tax


def calculate_quebec_tax(taxable_income: float) -> float:
    income_after_personal = max(0, taxable_income - QUEBEC_BASIC_PERSONAL)
    tax = 0.0
    remaining = income_after_personal
    for bracket_size, rate in QUEBEC_BRACKETS:
        taxable_in_bracket = min(remaining, bracket_size)
        tax += taxable_in_bracket * rate
        remaining -= taxable_in_bracket
        if remaining <= 0:
            break
    # Federal abatement: Quebec residents get 16.5% reduction on federal tax
    return tax


def calculate_federal_abatement(federal_tax: float) -> float:
    return federal_tax * 0.165


def calculate_payroll_deductions(employment_income: float) -> float:
    # CPP/QPP
    pensionable = min(employment_income, CPP_MAX_EARNINGS) - CPP_BASIC_EXEMPTION
    cpp = min(max(0, pensionable) * CPP_RATE, CPP_MAX_CONTRIBUTION)

    # EI
    ei = min(employment_income * EI_RATE, EI_MAX_CONTRIBUTION)

    # QPIP
    qpip = min(employment_income * QPIP_RATE, QPIP_MAX_INSURABLE * QPIP_RATE)

    return cpp + ei + qpip


def calculate_total_tax(gross_income: float, employment_income: float) -> dict:
    federal = calculate_federal_tax(gross_income)
    abatement = calculate_federal_abatement(federal)
    federal_net = federal - abatement
    quebec = calculate_quebec_tax(gross_income)
    payroll = calculate_payroll_deductions(employment_income)

    total = federal_net + quebec + payroll
    return {
        "federal": round(federal_net),
        "quebec": round(quebec),
        "payroll": round(payroll),
        "total": round(total),
        "effective_rate": round(total / gross_income * 100, 1) if gross_income > 0 else 0,
    }


@dataclass
class ProjectionParams:
    current_age: int = 30
    retirement_age: int = 65
    employment_income: float = 0
    other_income: float = 0
    savings_rate: float = 20.0       # % of after-tax income
    income_growth_rate: float = 2.5  # % annual
    inflation_rate: float = 2.0      # %
    investment_return: float = 5.0   # % nominal
    retirement_income_pct: float = 70.0  # % of final working income
    current_savings: float = 0       # total invested assets


@dataclass
class YearProjection:
    age: int
    year: int
    gross_income: float
    employment_income: float
    other_income: float
    federal_tax: float
    quebec_tax: float
    payroll_deductions: float
    total_tax: float
    effective_rate: float
    after_tax_income: float
    spending: float
    annual_savings: float
    cumulative_savings: float
    is_retired: bool


def run_projection(params: ProjectionParams) -> list[YearProjection]:
    results = []
    current_year = date.today().year
    cumulative_savings = params.current_savings
    emp_income = params.employment_income
    other_income = params.other_income

    # Pre-retirement final income (for retirement income calculation)
    years_to_retirement = max(0, params.retirement_age - params.current_age)
    final_working_income = emp_income * (1 + params.income_growth_rate / 100) ** years_to_retirement

    for age in range(params.current_age, 101):
        year = current_year + (age - params.current_age)
        is_retired = age >= params.retirement_age
        years_from_now = age - params.current_age

        if is_retired:
            # Retirement: income is a % of final working income, adjusted for inflation
            years_in_retirement = age - params.retirement_age
            retirement_base = final_working_income * (params.retirement_income_pct / 100)
            # Adjust for inflation from retirement start
            gross = retirement_base * (1 + params.inflation_rate / 100) ** years_in_retirement
            emp = 0.0
            oth = gross
        else:
            # Working years: income grows
            growth_factor = (1 + params.income_growth_rate / 100) ** years_from_now
            emp = emp_income * growth_factor
            oth = other_income * growth_factor
            gross = emp + oth

        # Taxes
        taxes = calculate_total_tax(gross, emp)

        after_tax = gross - taxes["total"]

        if is_retired:
            # In retirement: spending = after-tax income, draw down savings if needed
            savings_flow = 0
            # Investment returns on accumulated savings
            investment_gains = cumulative_savings * (params.investment_return / 100)
            spending = after_tax
            cumulative_savings += investment_gains  # savings still grow from returns
        else:
            # Working: save a portion
            savings_flow = after_tax * (params.savings_rate / 100)
            spending = after_tax - savings_flow
            investment_gains = cumulative_savings * (params.investment_return / 100)
            cumulative_savings += savings_flow + investment_gains

        results.append(YearProjection(
            age=age,
            year=year,
            gross_income=round(gross),
            employment_income=round(emp),
            other_income=round(oth),
            federal_tax=taxes["federal"],
            quebec_tax=taxes["quebec"],
            payroll_deductions=taxes["payroll"],
            total_tax=taxes["total"],
            effective_rate=taxes["effective_rate"],
            after_tax_income=round(after_tax),
            spending=round(spending),
            annual_savings=round(savings_flow),
            cumulative_savings=round(cumulative_savings),
            is_retired=is_retired,
        ))

    return results
