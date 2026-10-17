#!/usr/bin/env bash
# Prepare a dedicated Linux account for the REAL runner. It prints what it would do
# and changes nothing unless it is started with --apply, as root, by the owner.
#
# It creates an unprivileged account with no administrator rights, a data directory only that
# account can read, and unpacks the runner archive the owner downloaded. It does not
# register the runner: the registration token is short-lived, comes from GitHub's
# settings page, and is typed by the owner (see verification/real_evidence.md).
#
# Environment:
#   RUNNER_ARCHIVE   path of the downloaded actions-runner-linux-x64-*.tar.gz
#   RUNNER_SHA256    checksum published beside that download
#   DATA_SOURCE      directory holding creditcard.csv, water_quality.csv, cardio.csv
set -euo pipefail

ACCOUNT=thesis-runner
HOME_DIR=/home/$ACCOUNT
DATA_DIR=/srv/thesis-data
APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1

say() { printf '%s\n' "$*"; }
act() {
  if [ "$APPLY" -eq 1 ]; then "$@"; else say "would run: $*"; fi
}

: "${RUNNER_ARCHIVE:?set RUNNER_ARCHIVE to the downloaded runner archive}"
: "${RUNNER_SHA256:?set RUNNER_SHA256 to the checksum published by GitHub}"
: "${DATA_SOURCE:?set DATA_SOURCE to the directory that holds the three CSV files}"

if [ "$APPLY" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
  say "run with sudo to apply" >&2
  exit 1
fi

say "$RUNNER_SHA256  $RUNNER_ARCHIVE" | sha256sum --check --status \
  || { say "runner archive checksum differs" >&2; exit 1; }

for name in creditcard water_quality cardio; do
  [ -f "$DATA_SOURCE/$name.csv" ] || { say "missing $DATA_SOURCE/$name.csv" >&2; exit 1; }
done

act useradd --create-home --shell /bin/bash "$ACCOUNT"
act install -d -m 0700 -o "$ACCOUNT" -g "$ACCOUNT" "$DATA_DIR"
for name in creditcard water_quality cardio; do
  act install -m 0400 -o "$ACCOUNT" -g "$ACCOUNT" "$DATA_SOURCE/$name.csv" "$DATA_DIR/$name.csv"
done
act install -d -m 0750 -o "$ACCOUNT" -g "$ACCOUNT" "$HOME_DIR/actions-runner"
act tar xzf "$RUNNER_ARCHIVE" -C "$HOME_DIR/actions-runner"
act chown -R "$ACCOUNT:$ACCOUNT" "$HOME_DIR/actions-runner"
if [ "$APPLY" -eq 1 ]; then
  printf 'THESIS_DATA_DIR=%s\n' "$DATA_DIR" >> "$HOME_DIR/actions-runner/.env"
  chown "$ACCOUNT:$ACCOUNT" "$HOME_DIR/actions-runner/.env"
else
  say "would append THESIS_DATA_DIR=$DATA_DIR to the runner's .env"
fi

say "next, as $ACCOUNT, in $HOME_DIR/actions-runner:"
say "  ./config.sh --url https://github.com/theobigand/etl-anomaly-benchmark \\"
say "      --labels thesis-real --no-default-labels --ephemeral --token <token from the settings page>"
say "  ./run.sh"
