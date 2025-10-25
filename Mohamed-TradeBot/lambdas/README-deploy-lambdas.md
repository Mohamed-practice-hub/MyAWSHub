# Lambda Deploy Scripts (v1)

This folder contains per-lambda `v1` deployment scripts and a top-level `deploy-all-lambdas-v1.sh` helper.

Prerequisites:
- AWS CLI v2 installed and configured
- jq (optional) for JSON parsing
- On Windows: Git Bash or WSL for bash scripts, or use the PowerShell `.ps1` scripts

Per-lambda:
- Each lambda folder should include its own `deploy-<lambda>-v1.sh` script to package and deploy the function.
- Example: `fetch_lambda/deploy-fetch_lambda-v1.sh` or `deploy-fetch-lambda-v1.sh`.

Top-level:
- Run `./deploy-all-lambdas-v1.sh` to attempt running each lambda's deploy script.

Notes:
- The scripts assume each lambda handler is a single Python file. If you have dependencies, update script to pip install into the package directory before zipping (or use a Docker build for Linux dependencies).
- The ROLE_ARNs are hardcoded per-lambda in the scripts; adjust as needed.

Example (run from repo root):

```bash
cd lambdas
./deploy-all-lambdas-v1.sh
```
