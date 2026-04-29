#!/bin/bash
# Тест Docker-сборки

echo "🐳 Тест Docker для MoFrame"
echo "=========================="

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен"
    exit 1
fi

echo "✅ Docker найден"

# Сборка
echo ""
echo "🔨 Сборка образа..."
docker-compose build

if [ $? -ne 0 ]; then
    echo "❌ Сборка не удалась"
    exit 1
fi

echo "✅ Сборка успешна"

# Запуск
echo ""
echo "🚀 Запуск MoFrame..."
docker-compose up -d

# Ждем загрузки
echo "⏳ Ожидание запуска (10 секунд)..."
sleep 10

# Проверка
echo ""
echo "🔍 Проверка..."
if curl -s http://localhost:8501 > /dev/null; then
    echo "✅ MoFrame доступен на http://localhost:8501"
else
    echo "❌ MoFrame не отвечает"
    docker-compose logs
    exit 1
fi

echo ""
echo "=========================="
echo "✅ Тест пройден!"
echo ""
echo "Команды:"
echo "  docker-compose up -d    # Запуск"
echo "  docker-compose down     # Остановка"
echo "  docker-compose logs     # Логи"
