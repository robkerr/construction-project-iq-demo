"""Project master: dim_project.

Origin system (narrative): non-SAP — Project Controls & Estimating (PC&E) master.
Twelve projects, one hero (Project Falcon, PRJ-001). Baseline is healthy; the at-risk
story is injected deterministically later in seed_scenario.py.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd

from .common import (GenContext, CLIENTS, CONTRACT_TYPES, PROJECT_CODENAMES,
                     ids, iso)


# Generic global engineering & construction hubs (real coordinates, no customer ties).
# One tuple per site: (region, city, country, latitude, longitude). Projects are spread
# across these so the executive map shows a global portfolio.
LOCATIONS = [
    ("North America", "Houston", "United States", 29.7604, -95.3698),
    ("Latin America", "Santiago", "Chile", -33.4489, -70.6693),
    ("EMEA", "Rotterdam", "Netherlands", 51.9244, 4.4777),
    ("Middle East", "Al Jubail", "Saudi Arabia", 27.0174, 49.6251),
    ("Asia Pacific", "Singapore", "Singapore", 1.3521, 103.8198),
    ("North America", "Calgary", "Canada", 51.0447, -114.0719),
    ("Latin America", "Lima", "Peru", -12.0464, -77.0428),
    ("EMEA", "Aberdeen", "United Kingdom", 57.1497, -2.0943),
    ("Middle East", "Dubai", "United Arab Emirates", 25.2048, 55.2708),
    ("Asia Pacific", "Perth", "Australia", -31.9523, 115.8613),
    ("EMEA", "Johannesburg", "South Africa", -26.2041, 28.0473),
    ("Asia Pacific", "Mumbai", "India", 19.0760, 72.8777),
]


def generate(ctx: GenContext) -> None:
    n = ctx.n_projects
    project_ids = ids("PRJ-", n)

    names, clients, regions, contracts = [], [], [], []
    cities, countries, lats, lons = [], [], [], []
    planned_finish, forecast_finish, pct_complete, start_dates = [], [], [], []

    for i in range(n):
        codename = PROJECT_CODENAMES[i % len(PROJECT_CODENAMES)]
        names.append(f"Project {codename}")
        clients.append(CLIENTS[i % len(CLIENTS)])
        contracts.append(ctx.rng.choice(CONTRACT_TYPES))

        # Spread projects across distinct hubs for a global map; region follows the site.
        loc_region, loc_city, loc_country, loc_lat, loc_lon = LOCATIONS[i % len(LOCATIONS)]
        regions.append(loc_region)
        cities.append(loc_city)
        countries.append(loc_country)
        # Small jitter so co-located projects don't perfectly overlap on the map.
        lats.append(round(loc_lat + float(ctx.rng.uniform(-0.06, 0.06)), 4))
        lons.append(round(loc_lon + float(ctx.rng.uniform(-0.06, 0.06)), 4))

        # Mid-execution portfolio: started 12-30 months ago, finishing 3-18 months out.
        start = ctx.today - timedelta(days=int(ctx.rng.integers(360, 900)))
        start_dates.append(start)
        planned = ctx.today + timedelta(days=int(ctx.rng.integers(90, 540)))
        planned_finish.append(planned)
        # Baseline: forecast == planned (healthy). Injection will slip the hero + secondaries.
        forecast_finish.append(planned)
        pct_complete.append(round(float(ctx.rng.uniform(0.30, 0.75)), 2))

    df = pd.DataFrame({
        "project_id": project_ids,
        "project_name": names,
        "client": clients,
        "region": regions,
        "city": cities,
        "country": countries,
        "latitude": lats,
        "longitude": lons,
        "contract_type": contracts,
        "start_date": [iso(d) for d in start_dates],
        "planned_finish": [iso(d) for d in planned_finish],
        "forecast_finish": [iso(d) for d in forecast_finish],
        "pct_complete": pct_complete,
        "is_active": True,
        "origin_system": "non-SAP",
    })

    # Pin the hero project's identity and put it squarely mid-execution.
    hero = ctx.config["hero"]
    df.loc[df["project_id"] == hero["project_id"], "project_name"] = hero["project_name"]
    df.loc[df["project_id"] == hero["project_id"], "pct_complete"] = 0.55

    ctx.add("dim_project", df)
