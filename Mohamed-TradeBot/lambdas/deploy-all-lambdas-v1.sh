#!/bin/bash
set -e

# Deploy all lambdas v1 - runs each lambda's deploy script if present
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying all lambdas in $ROOT_DIR"
for d in "$ROOT_DIR"/*; do
  if [ -d "$d" ]; then
    script="$d/deploy-$(basename "$d")-v1.sh"
    script_alt="$d/deploy-$(basename "$d")-v1.sh"
    # Fallback for existing named script
    if [ -x "$script" ]; then
      echo "Running $script"
      (cd "$d" && "$script")
    elif [ -x "$d/deploy-$(basename "$d")-v1.sh" ]; then
      echo "Running $d/deploy-$(basename "$d")-v1.sh"
      (cd "$d" && ./deploy-$(basename "$d")-v1.sh)
    elif [ -x "$d/deploy-$(basename "$d")-v1.sh" ]; then
      echo "Running $d/deploy-$(basename "$d")-v1.sh"
      (cd "$d" && ./deploy-$(basename "$d")-v1.sh)
    else
      echo "No deploy script found in $d"
    fi
  fi
done

echo "✅ All deployments attempted."