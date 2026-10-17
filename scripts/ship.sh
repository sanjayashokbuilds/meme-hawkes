#!/bin/bash
# Ship a stage in one command:
#   bash scripts/ship.sh "Stage 3: univariate Hawkes" stage-3
#
# 1. Unpacks this stage's zip from your Downloads over this repo
#    (your .git history and .env are untouched).
# 2. Installs any new packages and runs the tests.
# 3. Only if the tests pass: commits, tags and pushes to GitHub.

# The braces make bash read the whole script before running it, which matters
# because the zip may contain a newer copy of this very file.
{
set -e  # stop at the first error, so nothing broken gets pushed

cd "$(dirname "$0")/.."                       # the repo root, wherever you run this from
# The newest zip named after this stage's tag (e.g. meme-hawkes-stage-3.zip or "... (1).zip")
ZIP=$(ls -t ~/Downloads/meme-hawkes-"$2"*.zip | head -1)
echo "Unpacking: $ZIP"
unzip -oq "$ZIP" -d ..                        # the zip holds a meme-hawkes/ folder

source .venv/bin/activate
pip install -q -r requirements.txt
pytest -q

git add .
git commit -m "$1"
git tag "$2"
git push origin main --tags
echo "Shipped $2."
exit
}
