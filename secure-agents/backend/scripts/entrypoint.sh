#!/bin/sh
set -e

# Run the prestart script if it exists
if [ -f /app/scripts/prestart.sh ]; then
    echo "Running prestart.sh..."
    /app/scripts/prestart.sh
fi

# Execute the main container command
exec "$@"