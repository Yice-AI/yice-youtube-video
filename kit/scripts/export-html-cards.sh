#!/bin/sh
exec node "$(dirname "$0")/export-html-cards.mjs" "$@"
