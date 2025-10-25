############################################################
# Slim Playwright Lambda Image (Chromium only)
# Goal: keep under CloudShell disk limits (< ~1.5 GB during build)
# Base: Amazon Linux 2 Lambda python 3.11 image
############################################################

FROM public.ecr.aws/lambda/python:3.11 AS runtime

# 1. Install ONLY required system libraries for headless Chromium.
#    (Playwright's --with-deps script is large and Debian‑centric; we list minimal yum packages explicitly.)
#    If a missing lib shows up at runtime, add it here and rebuild.
RUN yum install -y \
	alsa-lib \
	atk \
	at-spi2-atk \
	cups-libs \
	dbus-glib \
	dbus-libs \
	expat \
	glib2 \
	gtk3 \
	libX11 \
	libXcomposite \
	libXcursor \
	libXdamage \
	libXext \
	libXfixes \
	libXi \
	libXrandr \
	libXScrnSaver \
	libXtst \
	nss \
	pango \
	libXrender \
	xorg-x11-fonts-Type1 \
	xorg-x11-fonts-misc \
	tar gzip && \
	yum clean all && rm -rf /var/cache/yum

# 2. Reduce Python bytecode & pip cache footprint.
ENV PYTHONDONTWRITEBYTECODE=1 \
	PIP_NO_CACHE_DIR=1 \
	PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
	PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net

# 3. Copy requirements first (better layer caching) then install.
COPY requirements.txt ./
RUN python -m pip install -r requirements.txt -t ${LAMBDA_TASK_ROOT}

# 4. Install ONLY chromium browser (no firefox/webkit) – smaller download.
RUN python -m playwright install chromium --only-shell

# 5. Copy function code.
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/

# 6. Strip unneeded locales, debug symbols if present (best-effort; ignore errors).
RUN find /opt/playwright -type f -name '*.debug' -delete 2>/dev/null || true && \
	rm -rf /root/.cache /var/tmp/*

# 7. Set the Lambda handler.
CMD ["lambda_function.lambda_handler"]

# Notes:
# * If you see missing shared library errors in CloudWatch Logs, capture the .so name
#   and add the corresponding yum package above, then rebuild.
# * If build still exceeds space in CloudShell: run `docker system prune -a --volumes` first,
#   or switch to CodeBuild for more ephemeral disk.
