# Infrastructure Request Report — Database Server & Application Hosting

**Department:** RWE&Turcas Turkey – Commercial Asset Optimization  
**Date:** March 2026  
**Classification:** Internal – Confidential  
**Prepared by:** RWE&Turcas CAO

---

## 1. Executive Summary

The CAO Team operates an **internal-use-only** energy analytics dashboard that supports daily trading decisions. It is currently hosted on **Render** (a third-party cloud platform) with a managed PostgreSQL database.

**The dashboard currently contains no confidential RWE data** — only publicly available EPIAS market data and Meteologica weather forecasts. However, hosting on a third-party platform **prevents us from incorporating any confidential or RWE-internal data**, even when there is a clear business need (e.g., proprietary trading models, portfolio positions, internal cost structures). This limitation can only be resolved by moving to RWE-managed infrastructure.

We are requesting **two separate resources**, prioritized by urgency:

| Priority | Request | Summary |
|---|---|---|
| **Project 1 (Primary)** | **PostgreSQL Database Server** | RWE-managed database to store energy market data and enable future confidential data integration. |
| **Project 2 (Secondary)** | **Application Server** | Linux server to host the dashboard web application within the RWE environment. |

---

## 2. What Does the Dashboard Do?

The dashboard is a web-based analytics platform accessed exclusively by authorized RWE personnel. Key capabilities:

| Module | Description |
|---|---|
| **Real-Time Monitoring** | DPP and real-time generation tracking for Turkish power plants |
| **DPP Heatmaps** | Hourly heatmaps for Natural Gas, Import Coal, Hydro, and Lignite plants |
| **Generation & Demand Analysis** | Comparative analysis across fuel types and demand patterns |
| **System Direction Forecasting** | ML-based forecasting (CatBoost, LightGBM, XGBoost, Prophet) for YAL–YAT |
| **Forecast Performance** | Accuracy tracking of Meteologica generation forecasts |
| **Merit Order Analysis** | Forecasted vs. actual merit order comparison |
| **Automated Reporting** | Daily heatmap email reports to the trading team |

---

## 3. Current Setup & Why We Need to Migrate

**Current hosting:** Render Web Service + Render PostgreSQL + Supabase PostgreSQL (secondary)

> **All data is currently public (EPIAS + Meteologica).** We cannot place confidential data on Render under RWE's data governance policies, which limits the dashboard's analytical potential.

**Key reasons for migration:**
- **Enable confidential data use** — proprietary analytics, portfolio data, and internal cost models cannot be stored on third-party platforms
- **Corporate governance** — business-critical applications should reside within RWE-managed environments
- **Eliminate vendor dependency** — remove reliance on Render and Supabase
- **Audit & compliance** — better access logging and security controls

---

## 4. Technology Stack

**Backend:** Python 3.11, Flask, Gunicorn, SQLAlchemy, APScheduler, Pandas, NumPy  
**ML/Forecasting:** Darts, Prophet, CatBoost, LightGBM, XGBoost  
**Visualization:** Plotly, Kaleido, XlsxWriter  
**Frontend:** Bootstrap 5, jQuery, Plotly.js  
**Database:** PostgreSQL (with psycopg2 adapter, Alembic migrations)

#### Backend (Python 3.11)

| Library / Framework | Version | Purpose |
|---|---|---|
| Flask | 2.2.0 | Web application framework |
| Gunicorn | 21.2.0 | WSGI HTTP server for production deployment |
| SQLAlchemy | ≥ 2.0.0 | ORM and database toolkit |
| Flask-SQLAlchemy | ≥ 3.0.0 | Flask integration for SQLAlchemy |
| Flask-Migrate / Alembic | ≥ 4.0.0 / ≥ 1.12.0 | Database schema migrations |
| APScheduler | ≥ 3.10.4 | Background task scheduling (data collection, email reports) |
| Pandas | ≥ 2.0.0 | Data manipulation and analysis |
| NumPy | ≥ 1.16.0, < 2.0 | Numerical computing |
| Requests | ≥ 2.28.1 | HTTP client for external API communication |
| Flask-CORS | ≥ 4.0.0 | Cross-Origin Resource Sharing |
| Flask-Session | 0.8.0 | Server-side session management |
| psycopg2 | ≥ 2.9.9 | PostgreSQL database adapter |
| python-dotenv | 1.0.1 | Environment variable management |

#### Machine Learning & Forecasting

| Library | Version | Purpose |
|---|---|---|
| Darts | ≥ 0.30.0 | Time series forecasting framework |
| Prophet | 1.1.5 | Facebook's time series forecasting |
| CatBoost | ≥ 1.1.1 | Gradient boosting for time series |
| LightGBM | 4.4.0 | Gradient boosting for time series |
| XGBoost | ≥ 2.1.4 | Gradient boosting for time series |
| cmdstanpy | 1.2.2 | Backend for Prophet |

#### Visualization & Reporting

| Library | Version | Purpose |
|---|---|---|
| Plotly | 5.19.0 | Interactive chart generation |
| Kaleido | 0.2.1 | Static image export from Plotly (for email reports) |
| XlsxWriter | ≥ 3.1.0 | Excel file generation for data exports |
| openpyxl | ≥ 3.1.2 | Excel file reading/writing |

#### Frontend

| Technology | Purpose |
|---|---|
| Bootstrap 5.1.3 | UI framework |
| jQuery 3.6.0 | DOM manipulation and AJAX |
| Plotly.js 2.29.1 | Interactive client-side charting |
| Font Awesome 5.15.4 | Icon library |
| ES6 Modules | Modular JavaScript architecture |

### 4.2 External API Dependencies (Outbound Network Access Required)

The application requires **outbound HTTPS access** to the following external services:

| Service | URL | Purpose |
|---|---|---|
| **EPIAS Transparency Platform** | `https://seffaflik.epias.com.tr/electricity-service/` | Turkish electricity market data (DPP, realtime generation, AIC, prices, demand, order summary, merit order data) |
| **EPIAS Authentication** | `https://giris.epias.com.tr/cas/v1/tickets` | TGT token authentication for EPIAS API access |
| **Supabase Database** | `aws-0-us-east-2.pooler.supabase.com:5432` | Meteologica forecast data and EPIAS historical records (to be migrated) |
| **SMTP / SendGrid** | Configurable | Automated email report delivery |

> **Note:** If the database is migrated to RWE infrastructure, the Supabase dependency can be **fully eliminated** by consolidating all data into the RWE-hosted PostgreSQL instance. The EPIAS API access is mandatory as it is the official source of Turkish electricity market transparency data.

---

# PROJECT 1 (Primary): PostgreSQL Database Server

> **Most urgent request.** Having an RWE-managed database allows us to immediately migrate data away from third-party services and unlocks confidential data integration — even before the application server is migrated.

### Requirements

| Parameter | Requirement |
|---|---|
| **Engine** | PostgreSQL 15+ |
| **Storage** | **50 GB** (current data ~1–2 GB; headroom for 10+ years of growth and future confidential data) |
| **Concurrent Connections** | 20–50 |
| **Schemas** | Multiple schema support (`public`, `meteologica`, `epias`, and future schemas) |
| **Admin Privileges** | Full DDL/DML — ability to create schemas, tables, indexes, and manage roles |
| **Encryption** | SSL/TLS enforced for all connections |
| **Backup** | Automated daily backups with point-in-time recovery |
| **Availability** | High availability preferred — supports daily trading operations |

### External / Remote Access (Critical)

The database **must be accessible from outside the RWE corporate network**:
- Before the app server is migrated, the current Render-hosted application needs to connect to it
- Team members need direct access for ad-hoc queries and maintenance (home office, travel)
- Future integration with Databricks / Azure services may require cloud connectivity

**Recommended:** Secure external endpoint with IP allowlisting + SSL/TLS, or VPN-based access.

### Project 1 — Requested Resources

| Resource | Specification |
|---|---|
| **1× PostgreSQL Database** | Version 15+, 50 GB storage, SSL/TLS, multi-schema support |
| **External Accessibility** | VPN, IP allowlisting, or secure external endpoint |
| **Admin Privileges** | Full schema/role management capabilities |
| **Backup & Recovery** | Automated daily backups |

---

# PROJECT 2 (Secondary): Application Server

> **Secondary request.** Once the database is provisioned, deploy the dashboard application on RWE infrastructure to replace Render hosting entirely.

### Requirements

| Parameter | Requirement |
|---|---|
| **Operating System** | Linux (Ubuntu 22.04 LTS or similar) |
| **Python** | 3.11.x |
| **CPU** | 8 vCPUs (ML model training is CPU-intensive) |
| **RAM** | 16 GB (ML models + data processing + Gunicorn workers) |
| **Disk** | 100 GB SSD (code, dependencies, ML artifacts, logs, future expansion) |
| **Network (Outbound)** | HTTPS to EPIAS APIs, SMTP for email |
| **Network (Inbound)** | HTTP/HTTPS for dashboard access by RWE personnel |

The server also runs **scheduled background tasks** (Europe/Istanbul timezone): daily DPP data updates (16:05), hourly current-version updates, realtime generation updates (05:00 & 12:00), and daily email reports (16:10).

### Project 2 — Requested Resources

| Resource | Specification |
|---|---|
| **1× Linux Server** | 8 vCPUs, 16 GB RAM, 100 GB SSD, Python 3.11 |
| **Network (Outbound)** | HTTPS to `seffaflik.epias.com.tr`, `giris.epias.com.tr`, SMTP |
| **Network (Inbound)** | HTTP/HTTPS for authorized dashboard users |
| **Database Connectivity** | Must reach the PostgreSQL database from Project 1 |

---

## 5. Conclusion

**Project 1 (Database)** is the primary and most urgent need. The dashboard currently holds only public EPIAS data because we **cannot** store confidential data on third-party infrastructure. An RWE-managed PostgreSQL database would remove this barrier and serve as the data foundation for all current and future CAO analytics.

**Project 2 (Application Server)** would complete the migration by bringing the entire stack under RWE governance.

Both requests involve modest infrastructure requirements. We are ready to execute upon approval.

---

*For questions or further technical details, please contact the RWE&Turcas CAO Team.*
