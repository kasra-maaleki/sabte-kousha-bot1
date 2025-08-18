FROM python:3.10-slim

WORKDIR /app

# بهتره اول requirements نصب بشه تا کش بهتر کار کنه
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# سپس کدها را کپی کن
COPY . /app

# لاگ‌ها بلافاصله بیاد
ENV PYTHONUNBUFFERED=1

# EXPOSE فقط مستندسازی است؛ Render خودش PORT را ست می‌کند
EXPOSE 10000

# مهم: روی Render باید به $PORT بایند شوی. gunicorn خودش از $PORT استفاده می‌کند.
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--workers", "1", "--threads", "8", "--timeout", "120", "main:app"]
