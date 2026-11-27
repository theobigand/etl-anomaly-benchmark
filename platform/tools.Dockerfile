# One small image per tool profile; versions come from docs/architecture/adr and are passed as build arguments.
FROM python:3.11-slim
ARG PACKAGES=""
ARG JAVA="no"
RUN if [ "$JAVA" = "yes" ]; then apt-get update && apt-get install -y --no-install-recommends default-jre-headless && rm -rf /var/lib/apt/lists/*; fi \
 && if [ -n "$PACKAGES" ]; then pip install --no-cache-dir $PACKAGES; fi \
 && useradd --create-home runner
USER runner
WORKDIR /work
