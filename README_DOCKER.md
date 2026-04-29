# MoFrame — Docker

Быстрый запуск MoFrame через Docker.

## Требования

- Docker
- Docker Compose

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/hasan42/moframe.git
cd moframe

# Запуск
docker-compose up -d

# Открыть в браузере
# http://localhost:8501
```

## Команды

```bash
docker-compose up -d      # Запуск
docker-compose down       # Остановка
docker-compose logs       # Логи
docker-compose build      # Пересборка
docker-compose pull       # Обновление образа
```

## Папки

- `data/input/` — входные комиксы (монтируется)
- `data/output/` — готовые видео (монтируется)
- `temp/` — временные файлы (монтируется)

## Jupyter (для разработки)

```bash
docker-compose --profile dev up -d jupyter
# http://localhost:8888
```

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| STREAMLIT_SERVER_PORT | Порт | 8501 |
| STREAMLIT_SERVER_ADDRESS | Адрес | 0.0.0.0 |
