FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8765
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY outlook_rt_login ./outlook_rt_login
EXPOSE 8765
CMD ["sh", "-c", "gunicorn -w 2 -b 0.0.0.0:${PORT:-8765} outlook_rt_login.web:app"]
