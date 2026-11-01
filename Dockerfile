FROM python:3.13-slim

RUN useradd -m -u 1000 user
WORKDIR /app
RUN chown user:user /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .
USER user

EXPOSE 7860
CMD ["gunicorn", "-b", "0.0.0.0:7860", "--workers", "1", "--timeout", "300", "app:create_app()"]