# 🚀 Data Cycle Project



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
| `gold-loading-flow` | Data loading into DB |


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
# Project Setup

## 1. Run Folder Setup Script

First, execute the PowerShell setup script:

```powershell
.\FolderSetup.ps1
```

This script creates the required folder structure for the project.

---

## 2. Configure Credentials

After the folders are created, configure the credentials by following the guide below:

```text
Setup_Guide_Credentials.docx
```

This step is required to allow access to:
- Shared folders
- Network drives
- Source systems

---

## 3. Install Python Requirements

Install the dependencies required for the Silver and Gold layers:

```powershell
pip install -r requirements.txt
```

---

# Prefect Setup

## 4. Install Prefect

Install Prefect using pip:

```powershell
pip install prefect
```

Verify the installation:

```powershell
prefect version
```

---

## 5. Connect the VM to Prefect Cloud

Login to Prefect Cloud:

```powershell
prefect cloud login
```

A browser window will open for authentication.

After login:
- Select the correct organization
- Select the correct workspace

Verify the active profile:

```powershell
prefect profile ls
```

---

# Run the Pipeline

## 6. Execute the Full Pipeline

Once the setup is complete, start the pipeline:

```powershell
python FullPipeline.py


