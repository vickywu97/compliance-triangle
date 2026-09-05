# compliance-triangle — multi-tenant SaaS image.
#
# The whole product is stdlib-only, so there is no `pip install` step: the
# build needs no network access and the image stays small.
FROM python:3.11-slim

WORKDIR /app
COPY . /app

# HOST=0.0.0.0 is required: bound to loopback the container would be
# unreachable from outside, and /analyze would silently stay in demo mode.
ENV HOST=0.0.0.0 \
    PORT=10000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    COMPLIANCE_TRIANGLE_DB=/var/data/saas.db

EXPOSE 10000

# /healthz reports KB status; used by the platform's health check.
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','10000'))"

CMD ["python", "-m", "compliance_triangle.web"]
