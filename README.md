# DataCycleProject - GitHub Usage Guide

This guide explains how to use the GitHub repository.

## 🎯 Goals

- Work safely as a team  
- Avoid breaking the production branch  
- Use GitHub Actions correctly  
- Keep the workflow simple  

---

# 🌿 Repository branches

This repository uses **2 main branches**:

- `dev` → daily work and testing (from your laptop)  
- `Production` → stable branch for validated code (deployed to the VM/server)  

## ⚠️ Important rule

👉 Always work on `dev`  
❌ Do **not** work directly on `Production`  

---

# 🔄 Team workflow

1. Go to the `dev` branch  
2. Download latest changes  
3. Make your code changes  
4. Save your work  
5. Commit your changes  
6. Push to GitHub  
7. Check that CI is green in GitHub Actions  
8. When ready, create a Pull Request from `dev` → `Production`  

---

# 🚀 First time setup

## 1. Clone the repository

Open PowerShell in the folder where you want the project:

```bash
git clone https://github.com/MaximeHES/DataCycleProject.git
cd DataCycleProject

2. Go to the dev branch
git checkout dev
3. Verify your current branch
git branch

You should see:

* dev
  Production
💻 Daily usage
Step 1 — Open the project
cd C:\Users\YourName\PycharmProjects\DataCycleProject
Step 2 — Go to dev
git checkout dev
Step 3 — Download latest version
git pull

⚠️ Always do this before starting work

Step 4 — Make your changes

Edit your files normally.

Step 5 — Add your changes
git add .
Step 6 — Commit your changes
git commit -m "Describe clearly what you changed"
Examples
git commit -m "Fix silver cleaner empty file handling"
git commit -m "Update bronze logging"
git commit -m "Add CI workflow"
Step 7 — Push to GitHub
git push
🔍 Check that CI worked

After pushing:

Go to GitHub
Open the repository
Click the Actions tab
Result meanings
🟡 Yellow = running
🟢 Green = success
🔴 Red = failed

👉 Only continue if the workflow is green
