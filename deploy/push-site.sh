#!/usr/bin/env bash
# Force-push the `site` branch: tag `site-base` (an orphan commit holding only the refresh workflow, because scheduled
# workflows run from the default branch) + ONE commit on top with the built dist/, the Vercel functions and vercel.json.
# The build commit never changes workflow files, so CI can push it with GITHUB_TOKEN. History stays at 2 commits.
#   deploy/push-site.sh              # CI and normal use
#   deploy/push-site.sh --new-base   # after editing .github/workflows/refresh.yml on main (needs a token with workflow scope)
# Env: PUSH_URL (default: origin's URL).
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$PWD
URL="${PUSH_URL:-$(git remote get-url origin)}"
OUT="$(mktemp -d)"
trap 'rm -rf "$OUT"' EXIT
export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-github-actions[bot]}" GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME" GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"
src=$(git rev-parse --short HEAD)

cd "$OUT" && git init -q -b site
if [ "${1:-}" = "--new-base" ]; then
  mkdir -p .github/workflows && cp "$ROOT/.github/workflows/refresh.yml" .github/workflows/
  git add -A && git commit -q -m "site base: refresh workflow from main@$src"
  git tag -f site-base && git push -f -q "$URL" refs/tags/site-base
else
  git fetch -q --depth=1 "$URL" refs/tags/site-base:refs/tags/site-base
  git checkout -q site-base -- .github
  cmp -s .github/workflows/refresh.yml "$ROOT/.github/workflows/refresh.yml" ||
    echo "::warning::refresh.yml on main differs from site-base; run deploy/push-site.sh --new-base locally"
fi
cp -a "$ROOT/dist/." . && cp -a "$ROOT/deploy/vercel/." .
printf '# Layoff Tracker: built site\n\nGenerated hourly from the `main` branch by deploy/push-site.sh. Do not edit here.\n' > README.md
git add -A
c=$(git commit-tree "$(git write-tree)" -p site-base -m "Site build $(date -u +%Y-%m-%dT%H:%MZ) from main@$src")
git push -f -q "$URL" "$c:refs/heads/site"
echo "pushed site $c ($(git ls-tree -r --name-only "$c" | wc -l) files)"
