#!/usr/bin/env bash
set -o errexit

echo "▶️ Starting Flick backend..."

echo "🧱 Running database migrations..."
python manage.py migrate --noinput

echo "👑 Ensuring superuser exists..."
if [[ -n "$DJANGO_SUPERUSER_PASSWORD" ]] || [[ -n "$DJANGO_ADMIN_PASSWORD" ]]; then
  python manage.py create_admin || true
else
  echo "ℹ️ Initial admin provisioning skipped (neither DJANGO_SUPERUSER_PASSWORD nor DJANGO_ADMIN_PASSWORD set)."
fi

# Optional one-time / manual syncs
# These should NOT run on every deploy
if [[ "$SYNC_TMDB_GENRES" == "true" ]]; then
  echo "🎬 Syncing genres from TMDB..."
  python manage.py sync_genres || true
fi

if [[ "$SYNC_TMDB_MOVIES" == "true" ]]; then
  echo "🍿 Syncing movies from TMDB..."
  python manage.py sync_movies || true
fi

echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Launching ASGI server..."
exec uvicorn backend.asgi:application \
  --host 0.0.0.0 \
  --port 10000
