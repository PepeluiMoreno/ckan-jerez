# Imagen INDEPENDIENTE. ckan-jerez NO se construye sobre ODM ni importa su motor:
# es una app suscrita que habla con ODM por su API pública. Por eso parte de una
# base limpia y solo trae sus propias dependencias.
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY scripts/ ./scripts/
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ARG BUILD_SHA=dev
ENV APP_VERSION=${BUILD_SHA}
ENTRYPOINT ["/entrypoint.sh"]
CMD ["help"]
