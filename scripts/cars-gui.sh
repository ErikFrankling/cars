#!/usr/bin/env bash
# Start cars-gui from any directory, building it first if needed. Arguments go to the app.
# Uses the saved dev environment when there is one, which needs no Nix evaluation, else nix develop.
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/.." && pwd)"
ENV_FILE="${CARS_DEV_ENV:-/home/erikf/projects/personal/cars-data/dev-env.sh}"
export CARS_GUI_ROOT="$ROOT"
JOBS="${CARS_GUI_JOBS:-2}"
inner="cd '$ROOT' && cargo build --release -j $JOBS -p cars-gui && exec '$ROOT/target/release/cars-gui' \"\$@\""
if [ -r "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    exec bash -c "source '$ENV_FILE'; $inner" cars-gui "$@"
fi
exec nix develop "$ROOT" --command bash -c "$inner" cars-gui "$@"
