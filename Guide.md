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

<img width="1276" height="85" alt="image1" src="https://github.com/user-attachments/assets/b6d1cc4b-d091-4a42-aa14-479844501aad" />


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

<img width="862" height="314" alt="image2" src="https://github.com/user-attachments/assets/0435327b-59de-426a-bda8-6f6dbbdffcda" />


# STEP 8 — Automatic Deployment

After merging:

GitHub automatically deploys to the VM


# STEP 9 — Verify deployment (VM)

On the server:

```
dirC:\DataCycle_CICD_Test
```
<img width="660" height="201" alt="image3" src="https://github.com/user-attachments/assets/c8b826b5-dae7-4d82-8afc-d95931629d45" />

Your new file should be there
