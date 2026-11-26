FROM python:3.12-slim
WORKDIR /app
RUN groupadd --gid 10001 essenza && useradd --uid 10001 --gid 10001 --no-create-home essenza && mkdir /data && chown essenza:essenza /data
COPY --chown=essenza:essenza index.html ./
COPY --chown=essenza:essenza assets ./assets
COPY --chown=essenza:essenza backend ./backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ESSENZA_CONTAINER=1 ESSENZA_DB=/data/essenza-demo.sqlite3
USER essenza
EXPOSE 8765
CMD ["python","-m","backend.api"]
