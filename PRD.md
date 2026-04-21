# MoFrame - Comic to Animation Converter

## Статус проекта

✅ **Рабочая версия с интерактивным редактором панелей**

## Что работает сейчас

### Core функционал
- ✅ Загрузка: CBZ, CBR, PDF, JPG, PNG, WEBP
- ✅ Автодетекция панелей (OpenCV contours)
- ✅ Интерактивный React Canvas редактор
- ✅ Рендеринг видео (MP4)

### Интерфейс (4-step wizard)
1. **Upload** — загрузка файла
2. **Panels** — выбор Auto/Manual detection
3. **Edit** — React Canvas + Fine-tune fields
4. **Render** — настройки и генерация видео

## Быстрый старт

```bash
# Python зависимости
pip install -r requirements.txt

# Node.js зависимости
cd ui-react && npm install

# Запуск (2 терминала)
# Terminal 1:
npm run dev

# Terminal 2:
cd ../ui && streamlit run app.py
```

## React Canvas Editor

Интерактивный редактор на React с Canvas:
- 🖱️ Drag — перемещение панелей
- ↔️ Drag corners — изменение размера
- 🗑️ Double-click — удаление
- ➕ Click empty space — добавление
- 📋 Copy JSON — экспорт изменений

Данные передаются в Streamlit через JSON copy/paste.

## Технический стек

**Backend:** Python 3.10+, OpenCV, Pillow, moviepy, Streamlit
**Frontend:** React 18, TypeScript, Canvas API
**Build:** Vite

## Roadmap

- [ ] WebSocket sync (вместо JSON copy/paste)
- [ ] AI morphing
- [ ] Аудио дорожка
- [ ] Batch processing
- [ ] Вертикальное видео (Reels/TikTok)

## Структура проекта

```
moframe/
├── core/           # Python backend
├── ui/             # Streamlit + React wrapper
├── ui-react/       # React Canvas editor
└── tests/
```
