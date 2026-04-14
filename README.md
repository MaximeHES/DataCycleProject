# DataCycleProject - GitHub Usage Guide

This guide explains how to use the GitHub repository for this project in a simple way.

The goal is:
- work safely as a team
- avoid breaking the production branch
- use GitHub Actions correctly
- keep the workflow simple

---

# Repository branches

This repository uses 2 main branches:

- `dev` → branch for daily work and testing
- `Production` → stable branch for validated code only

## Important rule

Always work on `dev`.

Do **not** work directly on `Production`.

---

# Team workflow

The normal workflow is:

1. Go to the `dev` branch
2. Download latest changes
3. Make your code changes
4. Save your work
5. Commit your changes
6. Push to GitHub
7. Check that CI is green in GitHub Actions
8. When the code is ready, create a Pull Request from `dev` to `Production`

---

# First time setup

## 1. Clone the repository

Open PowerShell in the folder where you want the project, then run:

```bash
git clone https://github.com/MaximeHES/DataCycleProject.git
cd DataCycleProject
