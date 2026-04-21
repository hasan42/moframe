# MoFrame - План работы (Актуализированный)

## Статус проекта

✅ **Завершено:**
- Загрузка файлов (CBZ, CBR, PDF, изображения)
- Автоматическая детекция панелей (contours)
- Ручное редактирование панелей через React Canvas
- Рендеринг видео (MP4)
- 4-step wizard интерфейс (Streamlit)

🔧 **В работе:**
- Улучшение синхронизации React ↔ Streamlit
- Добавление аудио
- Batch processing

---

## Архитектура проекта

```
moframe/
├── core/                  # Python backend
│   ├── loader.py          # Загрузка файлов
│   ├── panel_detector.py  # Детекция панелей
│   ├── morpher.py         # Морфинг между панелями
│   └── renderer.py        # Рендер в MP4
├── ui/                    # Streamlit interface
│   ├── app.py             # Main wizard application
│   └── components/
│       └── panel_editor.py # React Canvas wrapper
├── ui-react/              # React frontend
│   └── src/
│       └── PanelEditor.tsx # Interactive Canvas editor
└── tests/                 # Unit tests
```

---

## Текущий workflow (4 шага)

### Step 1: Upload
- Поддержка: CBZ, CBR, PDF, JPG, PNG, WEBP
- Авто-извлечение страниц
- Предпросмотр загруженных страниц

### Step 2: Panel Detection
- **Auto Detect:** Автоматическая детекция через OpenCV contours
- **Manual Draw:** Ручное создание панелей
- Выбор порядка чтения (L-to-R или R-to-L)

### Step 3: Edit Panels
- **React Canvas Editor:**
  - Drag to move
  - Drag corners to resize
  - Double-click to delete
  - Click empty space to add
  - Copy JSON для экспорта
- **Fine-tune Fields:**
  - Точные значения X/Y/Width/Height
  - Кнопка Delete для каждой панели

### Step 4: Render
- Настройки:
  - Transition type (Ken Burns, Crossfade, Slide, Zoom)
  - Duration settings
  - FPS (12-60)
  - Resolution (Full HD, HD, SD)
- Результат: MP4 файл скачиванием

---

## Известные ограничения

1. **React ↔ Streamlit sync:** Canvas работает изолированно, данные передаются через JSON copy/paste
2. **Браузер:** React dev server должен быть запущен отдельно (localhost:3000)
3. **Морфинг:** Пока базовый (Ken Burns, Crossfade), без AI-генерации

---

## Следующие шаги

- [ ] Улучшить синхронизацию React-Streamlit (WebSocket?)
- [ ] Добавить AI-based морфинг (Stable Diffusion?)
- [ ] Поддержка аудио дорожки
- [ ] Batch processing (несколько файлов)
- [ ] Пресеты для соцсетей (9:16 для Reels/TikTok)
- [ ] Docker container для easy deploy

---

## Запуск для разработки

```bash
# Terminal 1 - React dev server
cd ui-react && npm run dev

# Terminal 2 - Streamlit
cd ui && streamlit run app.py
```

---

## Зависимости

- Python 3.9+
- Node.js 18+
- FFmpeg (для рендера)
