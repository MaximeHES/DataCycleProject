# 🚀 Data Cycle Project – Production Branch


## 📌 Overview

Welcome to the Data Cycle project.
The goal of this project is transform raw data from coffee machine into business value.

## 🏗️ Architecture

We follow a **Medallion Architecture**:
SOURCE (Eversys Share)
↓
🥉 Bronze Layer (Raw Data)
↓
🥈 Silver Layer (Cleaned Data)
↓
🥇 Gold Layer (Analytics - future)


---

## 🥉 Bronze Layer – Raw Ingestion

### ✅ Characteristics
- No transformation applied
- Full historical data preserved
- Watermark-based ingestion
- Reliable and idempotent

---

## 🥈 Silver Layer – Data Transformation

- 🐍 Tool: Python
- 📦 Scripts:
  - `clean_product_history.py`
  - `clean_rinse_history.py`
  - `clean_info_message_history.py`
  - `clean_cleaning_history.py`

### 🧹 Processing Includes
- Data cleaning and normalization
- Schema standardization
- Deduplication
- Error handling and logging

---

## 🎯 Orchestration

Managed using **Prefect**

### 🔄 Production Flows

| Flow | Description |
|------|------------|
| `bronze-ingestion-flow` | Incremental ingestion from source |
| `silver-transformation-flow` | Data cleaning and structuring |

### ⏱️ Scheduling

- Bronze ingestion: runs periodically (e.g. hourly)
- Silver transformation: triggered after ingestion

---

## ⚙️ Branch Strategy

| Branch | Purpose |
|--------|--------|
| `Production` | Production 🚀 |
| `dev` | Development 🧪 |

### 🔁 Workflow

All development is done in `dev`.  
Once validated, changes are merged into `main` for production deployment.

---
