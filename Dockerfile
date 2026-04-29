# MoFrame Docker Image
# Содержит всё необходимое для запуска комикс-рендерера

FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# Создание рабочей директории
WORKDIR /app

# Копирование requirements
COPY requirements.txt .

# Установка Python-зависимостей
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY core/ ./core/
COPY ui/ ./ui/
COPY tests/ ./tests/
COPY test-files/ ./test-files/

# Создание папок для данных
RUN mkdir -p /app/data/input /app/data/output /app/temp

# Открытие порта для Streamlit
EXPOSE 8501

# Переменные окружения
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Запуск Streamlit
CMD ["python", "-m", "streamlit", "run", "ui/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--browser.gatherUsageStats=false"]
