FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --uid 10001 --create-home appuser && mkdir /data && chown appuser /data
USER appuser
ENV APP_DATA_DIR=/data
EXPOSE 8767
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8767"]
