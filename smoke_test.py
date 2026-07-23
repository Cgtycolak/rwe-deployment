#!/usr/bin/env python3
"""
Smoke test — hits every readable route and asserts no 500s.
Run before every deploy:  python smoke_test.py
Include data-update routes: python smoke_test.py --mutations

Exit code 0 = all passed, 1 = at least one failure.
"""
import argparse
import os
import sys
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"


def login(base: str, username: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(
        f"{base}/login",
        data={"username": username, "password": password},
        allow_redirects=True,
        timeout=15,
    )
    if "/login" in r.url:
        print(f"{RED}LOGIN FAILED — wrong credentials or server not running{RESET}")
        sys.exit(1)
    print(f"{GREEN}✓  Login OK  ({username}){RESET}\n")
    return s


def check(s: requests.Session, base: str, label: str, method: str, path: str, **kwargs):
    """Return (passed: bool, status_code: int, detail: str)."""
    try:
        r = s.request(method, f"{base}{path}", timeout=30, **kwargs)
        ok = r.status_code < 500
        detail = ""
        if not ok:
            try:
                detail = str(r.json())[:200]
            except Exception:
                detail = r.text[:200]
        return ok, r.status_code, detail
    except requests.exceptions.ConnectionError:
        return False, 0, "connection refused — is the server running?"
    except requests.exceptions.Timeout:
        return False, 0, "timed out after 30s"
    except Exception as e:
        return False, 0, str(e)


def main():
    parser = argparse.ArgumentParser(description="Smoke-test every route before deploy")
    parser.add_argument("--base-url",  default="http://localhost:5000")
    parser.add_argument("--mutations", action="store_true",
                        help="Also run data-update routes (writes to DB, slower)")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    username = os.getenv("DASHBOARD_USERNAME")
    password = os.getenv("DASHBOARD_PASSWORD")
    if not username or not password:
        print(f"{RED}Set DASHBOARD_USERNAME and DASHBOARD_PASSWORD in .env{RESET}")
        sys.exit(1)

    s = login(base, username, password)

    # Shared date values used across routes
    today     = date.today()
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    week_ago  = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    gen_date  = yesterday
    pred_date = today.strftime("%Y-%m-%d")

    # (label, method, path, extra kwargs for requests)
    READ_ROUTES = [
        # --- Pages ---
        ("dashboard",                   "GET",  "/",                             {}),

        # --- Production / DPP ---
        ("powerplants",                 "GET",  "/powerplants",                  {}),
        ("get_orgs",                    "POST", "/get_orgs",                     {"json": {"start": week_ago, "end": yesterday}}),
        ("get_orgs_uevcbids",           "POST", "/get_orgs_uevcbids",            {"json": {"start": week_ago, "end": yesterday, "orgIds": []}}),
        ("get_aic_data",                "GET",  "/get_aic_data",                 {"params": {"range": "week"}}),
        ("production_data",             "POST", "/production_data",              {"json": {"start_date": week_ago, "end_date": yesterday}}),

        # --- Market prices ---
        ("get_order_summary",           "GET",  "/get_order_summary",            {}),
        ("get_smp_data",                "GET",  "/get_smp_data",                 {}),
        ("get_pfc_data",                "GET",  "/get_pfc_data",                 {}),
        ("get_sfc_data",                "GET",  "/get_sfc_data",                 {}),
        ("get_all_table_data",          "GET",  "/get_all_table_data",           {}),
        ("supply_demand_price",         "GET",  "/api/supply_demand_price",      {"params": {"date": gen_date}}),

        # --- Natural gas heatmap ---
        ("heatmap_data current",        "POST", "/heatmap_data",                 {"json": {"date": gen_date, "version": "current"}}),
        ("heatmap_data first",          "POST", "/heatmap_data",                 {"json": {"date": gen_date, "version": "first"}}),
        ("realtime_heatmap_data",       "POST", "/realtime_heatmap_data",        {"json": {"date": gen_date}}),

        # --- Import coal heatmap ---
        ("import_coal current",         "POST", "/import_coal_heatmap_data",     {"json": {"date": gen_date, "version": "current"}}),
        ("import_coal first",           "POST", "/import_coal_heatmap_data",     {"json": {"date": gen_date, "version": "first"}}),

        # --- Hydro heatmap ---
        ("hydro_heatmap current",       "POST", "/hydro_heatmap_data",           {"json": {"date": gen_date, "version": "current"}}),
        ("hydro_heatmap first",         "POST", "/hydro_heatmap_data",           {"json": {"date": gen_date, "version": "first"}}),
        ("hydro_realtime",              "POST", "/hydro_realtime_heatmap_data",  {"json": {"date": gen_date}}),

        # --- Lignite heatmap ---
        ("lignite_heatmap current",     "POST", "/lignite_heatmap_data",         {"json": {"date": gen_date, "version": "current"}}),
        ("lignite_heatmap first",       "POST", "/lignite_heatmap_data",         {"json": {"date": gen_date, "version": "first"}}),
        ("lignite_realtime",            "POST", "/lignite_realtime_heatmap_data",{"json": {"date": gen_date}}),

        # --- Rolling / solar ---
        ("get-rolling-last-update",     "GET",  "/get-rolling-last-update",      {}),
        ("get-rolling-data",            "GET",  "/get-rolling-data",             {}),
        ("get-solar-weekly-data",       "GET",  "/get-solar-weekly-data",        {}),

        # --- Demand ---
        ("check-demand-completeness",   "GET",  "/check-demand-completeness",    {}),
        ("get_demand_data",             "GET",  "/get_demand_data",              {}),
        ("get_monthly_demand_data",     "GET",  "/get_monthly_demand_data",      {}),
        ("check_demand_updates",        "GET",  "/check_demand_updates",         {}),

        # --- Data completeness ---
        ("check-data-completeness",     "GET",  "/check-data-completeness",      {}),

        # --- Forecast performance ---
        ("forecast-perf d+1",           "GET",  "/forecast-performance-data",    {"params": {"horizon": "d+1", "period": "7"}}),
        ("forecast-perf d+2",           "GET",  "/forecast-performance-data",    {"params": {"horizon": "d+2", "period": "7"}}),

        # --- Merit order ---
        ("merit-order-failure-data",    "GET",  "/merit-order-failure-data",     {"params": {"gen_date": gen_date, "pred_date": pred_date}}),
        ("merit-order-aic-data",        "GET",  "/merit-order-aic-data",         {"params": {"gen_date": gen_date, "pred_date": pred_date}}),
        ("merit-order-data",            "GET",  "/merit-order-data",             {"params": {"gen_date": gen_date, "pred_date": pred_date}}),

        # --- Generation comparison ---
        ("generation-comparison",       "POST", "/api/generation-comparison",    {"json": {"start": week_ago, "end": yesterday}}),
    ]

    # Data-update routes — excluded by default, run with --mutations
    MUTATION_ROUTES = [
        ("update-rolling-data",          "GET", "/update-rolling-data",          {}),
        ("update-unlicensed-solar-data", "GET", "/update-unlicensed-solar-data", {}),
        ("update-licensed-solar-data",   "GET", "/update-licensed-solar-data",   {}),
        ("update_demand_data_api",       "GET", "/update_demand_data_api",       {}),
    ]

    # File-upload routes — cannot be smoke tested without real Excel files
    SKIPPED = [
        "api/forecasting/recent-data      (needs Excel file upload)",
        "api/forecasting/evaluate         (needs Excel file upload)",
        "api/forecasting/predict          (needs Excel file upload)",
        "api/forecasting/download-forecast(needs prior predict run)",
        "download-forecast-performance-excel (needs prior run)",
        "download-merit-order-excel       (needs prior run)",
        "merit-order-power-plant-results  (needs specific plant name)",
        "dpp_table                        (needs full orgsData payload)",
        "realtime_data                    (needs valid powerPlantId)",
    ]

    routes_to_run = READ_ROUTES + (MUTATION_ROUTES if args.mutations else [])

    passed = failed = 0
    for label, method, path, kwargs in routes_to_run:
        ok, status, detail = check(s, base, label, method, path, **kwargs)
        tag   = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        code  = f"[{status}]" if status else "[---]"
        print(f"  {tag}  {code:<6}  {method:<5}  {path:<45}  {label}")
        if detail:
            print(f"         {YELLOW}{detail}{RESET}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{'─' * 65}")
    print(f"  {GREEN}{passed} passed{RESET}  |  "
          f"{(RED + str(failed) + ' failed' + RESET) if failed else '0 failed'}  |  "
          f"{len(SKIPPED)} skipped")

    if not args.mutations:
        print(f"\n  {YELLOW}Mutation routes not tested (add --mutations to include them).{RESET}")

    print(f"\n  Skipped (require file uploads or specific state):")
    for s_ in SKIPPED:
        print(f"    • {s_}")

    if failed:
        print(f"\n{RED}Smoke test FAILED — do not deploy.{RESET}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}Smoke test passed — safe to deploy.{RESET}")


if __name__ == "__main__":
    main()
