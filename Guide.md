# Simple GitHub Workflow Guide

This guide explains how to safely update the project and deploy changes.

**dev → CI → Pull Request → Production → Auto Deployment (VM)**

---

# STEP 1 — Go to the dev branch

```bash
git checkout dev
git pull
```

# STEP 2 — Create or update your file

- Add a new script OR modify an existing file

# STEP 3 — Commit your changes

```
git add .
git commit-m"Describe what you changed"
```

### Example:

```
git commit-m"Add new cleaning script"
```

# STEP 4 — Push to GitHub

```
git push
```

# STEP 5 — Check CI (IMPORTANT)

1. Go to GitHub
2. Click **Actions**

 Wait until the **CI is green** 

![image.png](attachment:7a16f892-f0a6-4640-9473-985fa9b15b54:image.png)

# STEP 6 — Create a Pull Request

1. Go to **Pull Requests**
2. Click **New Pull Request**

Set:

- **base** = `Production`
- **compare** = `dev`

**Create pull request**

# STEP 7 — Review and Merge

- Check your changes
- Click **Merge pull request**

![image.png](attachment:95115698-22cc-4c12-ab6e-a254ac9de727:image.png)

# STEP 8 — Automatic Deployment

After merging:

GitHub automatically deploys to the VM

For now still using manual slf hosted runner so:

```powershell
PS C:\actions-runner> .\run.cmd
```

![image.png](attachment:ef011dad-1e60-4596-8235-388e75e6fd91:image.png)

# STEP 9 — Verify deployment (VM)

On the server:

```
dirC:\DataCycle_CICD_Test
```

Your new file should be there
