web: uvicorn src.main:app --host=0.0.0.0 --port=${PORT:-5000}
worker: celery -A src.tasks.celery_app worker --loglevel=info
beat: celery -A src.tasks.celery_app beat --loglevel=info