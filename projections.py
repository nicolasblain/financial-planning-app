"""
Financial projection engine.

Projects income, taxes, spending, and savings year-by-year until age 100.
Uses 2025 Canadian federal + Quebec provincial tax brackets.
Splits savings across RRSP, TFSA, FHSA, and non-registered accounts.
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

# --- Account contribution limits (2025) ---
TFSA_ANNUAL_LIMIT = 7_000
RRSP_RATE = 0.18  # 18% of earned income
RRSP_ANNUAL_MAX = 32_490
FHSA_ANNUAL_LIMIT = 8_000
FHSA_LIFETIME_LIMIT = 40_000
RRSP_MAX_AGE = 71  # must convert to RRIF at 71


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
    return tax


def calculate_federal_abatement(federal_tax: float) -> float:
    return federal_tax * 0.165


def calculate_payroll_deductions(employment_income: float) -> float:
    pensionable = min(employment_income, CPP_MAX_EARNINGS) - CPP_BASIC_EXEMPTION
    cpp = min(max(0, pensionable) * CPP_RATE, CPP_MAX_CONTRIBUTION)
    ei = min(employment_income * EI_RATE, EI_MAX_CONTRIBUTION)
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
    annual_spending: float = 0       # fixed spending; 0 = auto from savings_rate
    savings_rate: float = 20.0       # % of after-tax income (used if spending=0)
    income_growth_rate: float = 2.5  # % annual
    inflation_rate: float = 2.0      # %
    investment_return: float = 5.0   # % nominal
    retirement_income_pct: float = 70.0  # % of final working income
    current_savings: float = 0       # total invested assets
    # Current account balances
    current_rrsp: float = 0
    current_tfsa: float = 0
    current_fhsa: float = 0
    current_non_reg: float = 0
    # Current contribution room
    rrsp_room: float = 0
    tfsa_room: float = 0
    # FHSA eligibility
    fhsa_eligible: bool = False  # True if first-time home buyer


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
    # Account-level splits
    to_rrsp: float = 0
    to_tfsa: float = 0
    to_fhsa: float = 0
    to_non_reg: float = 0
    # Cumulative balances
    bal_rrsp: float = 0
    bal_tfsa: float = 0
    bal_fhsa: float = 0
    bal_non_reg: float = 0
    cumulative_savings: float = 0
    is_retired: bool = False


def run_projection(params: ProjectionParams) -> list[YearProjection]:
    results = []
    current_year = date.today().year
    emp_income = params.employment_income
    other_income = params.other_income

    # Account balances
    bal_rrsp = params.current_rrsp
    bal_tfsa = params.current_tfsa
    bal_fhsa = params.current_fhsa
    bal_non_reg = params.current_non_reg

    # Contribution room trackers
    rrsp_room = params.rrsp_room
    tfsa_room = params.tfsa_room
    fhsa_lifetime_used = 0.0  # how much has been contributed to FHSA total
    fhsa_eligible = params.fhsa_eligible

    # Spending: use fixed amount or derive from savings rate
    if params.annual_spending > 0:
        base_spending = params.annual_spending
        use_fixed_spending = True
    else:
        base_spending = 0
        use_fixed_spending = False

    # Pre-retirement final income (for retirement income calculation)
    years_to_retirement = max(0, params.retirement_age - params.current_age)
    final_working_income = (emp_income + other_income) * (1 + params.income_growth_rate / 100) ** years_to_retirement

    for age in range(params.current_age, 101):
        year = current_year + (age - params.current_age)
        is_retired = age >= params.retirement_age
        years_from_now = age - params.current_age

        if is_retired:
            years_in_retirement = age - params.retirement_age
            retirement_base = final_working_income * (params.retirement_income_pct / 100)
            gross = retirement_base * (1 + params.inflation_rate / 100) ** years_in_retirement
            emp = 0.0
            oth = gross
        else:
            growth_factor = (1 + params.income_growth_rate / 100) ** years_from_now
            emp = emp_income * growth_factor
            oth = other_income * growth_factor
            gross = emp + oth

        # Taxes
        taxes = calculate_total_tax(gross, emp)
        after_tax = gross - taxes["total"]

        if is_retired:
            savings_flow = 0
            to_rrsp = to_tfsa = to_fhsa = to_non_reg = 0
            if use_fixed_spending:
                spending = base_spending * (1 + params.inflation_rate / 100) ** years_from_now
            else:
                spending = after_tax
        else:
            # Determine spending and total savings
            if use_fixed_spending:
                spending = base_spending * (1 + params.inflation_rate / 100) ** years_from_now
                savings_flow = max(0, after_tax - spending)
            else:
                savings_flow = after_tax * (params.savings_rate / 100)
                spending = after_tax - savings_flow

            # --- Allocate savings across accounts (priority order) ---
            remaining_to_allocate = savings_flow

            # 1. FHSA (if eligible, under lifetime cap, max $8k/year)
            to_fhsa = 0
            if fhsa_eligible and fhsa_lifetime_used < FHSA_LIFETIME_LIMIT:
                fhsa_annual_room = min(FHSA_ANNUAL_LIMIT, FHSA_LIFETIME_LIMIT - fhsa_lifetime_used)
                to_fhsa = min(remaining_to_allocate, fhsa_annual_room)
                remaining_to_allocate -= to_fhsa
                fhsa_lifetime_used += to_fhsa

            # 2. RRSP (18% of earned income up to max, within available room, until age 71)
            to_rrsp = 0
            if age <= RRSP_MAX_AGE and rrsp_room > 0:
                rrsp_desired = min(remaining_to_allocate, rrsp_room)
                to_rrsp = max(0, rrsp_desired)
                remaining_to_allocate -= to_rrsp
                rrsp_room -= to_rrsp

            # 3. TFSA
            to_tfsa = 0
            if tfsa_room > 0:
                to_tfsa = min(remaining_to_allocate, tfsa_room)
                remaining_to_allocate -= to_tfsa
                tfsa_room -= to_tfsa

            # 4. Non-registered (remainder)
            to_non_reg = max(0, remaining_to_allocate)

        # Investment returns on each account
        ret = params.investment_return / 100
        bal_rrsp = bal_rrsp * (1 + ret) + to_rrsp
        bal_tfsa = bal_tfsa * (1 + ret) + to_tfsa
        bal_fhsa = bal_fhsa * (1 + ret) + to_fhsa
        bal_non_reg = bal_non_reg * (1 + ret) + to_non_reg
        cumulative = bal_rrsp + bal_tfsa + bal_fhsa + bal_non_reg

        # Generate new RRSP room for next year (from this year's earned income)
        if not is_retired:
            new_rrsp_room = min(emp * RRSP_RATE, RRSP_ANNUAL_MAX)
            rrsp_room += new_rrsp_room
            # TFSA room: $7k added each year
            tfsa_room += TFSA_ANNUAL_LIMIT

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
            to_rrsp=round(to_rrsp),
            to_tfsa=round(to_tfsa),
            to_fhsa=round(to_fhsa),
            to_non_reg=round(to_non_reg),
            bal_rrsp=round(bal_rrsp),
            bal_tfsa=round(bal_tfsa),
            bal_fhsa=round(bal_fhsa),
            bal_non_reg=round(bal_non_reg),
            cumulative_savings=round(cumulative),
            is_retired=is_retired,
        ))

    return results
