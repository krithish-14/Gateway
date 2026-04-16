#!/bin/bash

# Function to wait for SQL Server
function wait_for_db() {
    echo "Waiting for MS SQL Server at $DB_HOST:$DB_PORT..."
    # We use a simple python check to see if the port is open
    while ! python -c "import socket; s = socket.socket(); s.connect(('$DB_HOST', int('$DB_PORT')))" > /dev/null 2>&1; do
        sleep 2
    done
    echo "SQL Server is up!"
}

# Wait for database
wait_for_db

# Run Django migrations
echo "Running migrations..."
python manage.py migrate --noinput || echo "Migrations failed, continuing anyway..."

# Create superuser if environment variables are set
if [ "$DJANGO_SUPERUSER_USERNAME" ]; then
    echo "Creating superuser..."
    python manage.py createsuperuser --noinput || echo "Superuser creation failed (maybe already exists)"
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Start Gunicorn
echo "Starting Gunicorn..."
exec gunicorn final_setup.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120
