# UFC Bot - Ideas & Roadmap

## 1. Фильтры по лигам

### Функционал
- `/ufc` — только UFC события
- `/pfl` — только PFL события
- `/bellator` — только Bellator события
- `/settings` — настройка подписки (выбор лиг для уведомлений)

### Реализация
- Добавить команды-хендлеры для каждой лиги
- Расширить `SubscriberStorage` — хранить `{chat_id: ["UFC", "PFL"]}` вместо просто списка
- Inline-кнопки для выбора лиг в `/settings`

### Сложность: 🟢 Легко (2-3 часа)

---

## 2. Информация о бойцах

### Функционал
- Показывать рекорд бойца (15-2-0) рядом с именем
- Ранг в дивизионе (#3 Lightweight)
- `/fighter Khabib` — карточка бойца

### Источники данных
- **UFCStats.com** — `http://ufcstats.com/statistics/fighters/search?query=NAME`
- **Sherdog** — `https://www.sherdog.com/fighter/NAME`
- **Tapology** — хорошие данные по рангам

### Реализация
- Новый сервис `services/fighter_scraper.py`
- Кэширование данных бойцов (JSON или SQLite)
- Парсить при показе fight card

### Сложность: 🟡 Средне (4-6 часов)

---

## 3. Результаты боёв

### Функционал
- Уведомление после завершения события с результатами
- Формат: `✅ Islam Makhachev def. Dustin Poirier via SUB (R4, 3:25)`
- Команда `/results` — последние результаты

### Источники данных
- **UFCStats.com** — `http://ufcstats.com/event-details/ID`
- **ESPN** — результаты появляются быстро

### Реализация
- Scheduler проверяет завершённые события (каждые 30 мин в день события)
- Парсить результаты после завершения
- Хранить `event_id -> results_sent: bool`

### Сложность: 🟡 Средне (4-5 часов)

---

## 4. Countdown + Calendar

### Функционал
- `/countdown` — красивый таймер до ближайшего события
- Кнопка "📅 Add to Calendar" — генерирует .ics файл
- Можно добавить в Google Calendar / Apple Calendar

### Реализация
```python
# Countdown
days, hours, mins = calculate_countdown(event.date)
f"⏱ {days}d {hours}h {mins}m until {event.name}"

# ICS генерация
from icalendar import Calendar, Event
cal = Calendar()
cal_event = Event()
cal_event.add('summary', event.name)
cal_event.add('dtstart', event.date)
# Отправить как документ
```

### Зависимости
- `icalendar` — для генерации .ics

### Сложность: 🟢 Легко (2-3 часа)

---

## 5. Fight Card целиком

### Функционал
- `/card UFC315` — полная карта боёв
- Разделение: Main Card / Prelims / Early Prelims
- Время начала каждой части

### Формат вывода
```
🥊 UFC 315: Dvalishvili vs O'Malley

📺 MAIN CARD (23:00 CET)
• Dvalishvili vs O'Malley (BW Title)
• Adesanya vs Pereira (MW)
• Volkov vs Aspinall (HW)

📺 PRELIMS (21:00 CET)
• Fighter1 vs Fighter2
• Fighter3 vs Fighter4

📺 EARLY PRELIMS (19:00 CET)
• ...
```

### Источники
- ESPN event page — есть разделение по картам
- UFCStats — более детально

### Реализация
- Расширить `Event` модель: `main_card: list[Fight]`, `prelims: list[Fight]`
- Парсить детальную страницу события
- Новая команда `/card`

### Сложность: 🟡 Средне (4-5 часов)

---

## 6. Стримы по региону

### Функционал
- При первом запуске спросить страну (или определить по языку Telegram)
- Показывать актуальные стримы для региона
- `/region DE` — сменить регион

### Данные по регионам
```python
STREAMING_BY_REGION = {
    "US": {
        "UFC": ["ESPN+", "ABC", "ESPN"],
        "PFL": ["ESPN", "ESPN+"],
        "Bellator": ["CBS Sports", "Showtime"]
    },
    "DE": {
        "UFC": ["DAZN"],
        "PFL": ["DAZN"],
        "Bellator": ["DAZN"]
    },
    "RU": {
        "UFC": ["Okko", "Матч ТВ"],
        ...
    },
    "UK": {
        "UFC": ["TNT Sports", "discovery+"],
        ...
    }
}
```

### Реализация
- Расширить `SubscriberStorage` — хранить `region` для каждого юзера
- Inline-кнопки для выбора региона
- Динамически показывать стримы в сообщениях

### Сложность: 🟢 Легко (2-3 часа)

---

## Приоритеты

| # | Фича | Сложность | Ценность | Приоритет |
|---|------|-----------|----------|-----------|
| 1 | Фильтры по лигам | 🟢 | ⭐⭐⭐ | HIGH |
| 4 | Countdown + Calendar | 🟢 | ⭐⭐⭐ | HIGH |
| 6 | Стримы по региону | 🟢 | ⭐⭐ | HIGH |
| 5 | Fight Card целиком | 🟡 | ⭐⭐⭐ | MEDIUM |
| 2 | Инфо о бойцах | 🟡 | ⭐⭐ | MEDIUM |
| 3 | Результаты боёв | 🟡 | ⭐⭐ | MEDIUM |

---

## Технические улучшения

- [ ] SQLite вместо JSON (для масштабирования)
- [ ] Логирование в файл + ротация
- [ ] Docker + docker-compose
- [ ] Health check endpoint
- [ ] Graceful shutdown
- [ ] Rate limiting для парсинга
- [ ] Retry логика с exponential backoff
