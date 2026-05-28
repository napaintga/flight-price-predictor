# Система прогнозування та інтерактивної аналітики цін на авіаквитки

> Вебзастосунок для пошуку авіарейсів, збереження історії цін, прогнозування вартості авіаквитків за допомогою моделей машинного навчання та перегляду аналітичних висновків.

> Проєкт розроблено як бакалаврську кваліфікаційну роботу зі спеціальності 122 - Комп'ютерні науки.

---

## Автор

- **ПІБ**: Сітка І.-В. І.
- **Група**: ФЕІ-42
- **Спеціальність**: 122 - Комп'ютерні науки
- **Керівник**: ас. Парубочий В. О.
- **Дата виконання**: 2026

---

## Загальна інформація

- **Тип проєкту**: вебзастосунок з ML-модулем та аналітичною панеллю
- **Backend**: Python, FastAPI, PostgreSQL
- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Machine Learning**: pandas, NumPy, scikit-learn, XGBoost, PyTorch
- **Інтеграції**: SerpApi Google Flights API
- **Контейнеризація**: Docker, Docker Compose

---

## Опис функціоналу

- Пошук авіарейсів за маршрутом, датою, кількістю пасажирів і класом подорожі.
- Отримання детальної інформації про конкретний рейс.
- Збереження знімків цін у PostgreSQL для подальшого аналізу.
- Прогнозування ціни авіаквитка на основі ознак рейсу та контексту пошуку.
- Перегляд історії зміни ціни для рейсу.
- Аналітична сторінка з метриками якості моделі та графіками actual-vs-predicted.
- Авторизація користувачів, історія пошуків і список обраних квитків.
- API для пошуку, прогнозування, аналітики та роботи з користувацькими даними.

---

## Опис основних папок і файлів

| Папка / файл | Призначення |
|---|---|
| `backend/main.py` | Точка входу FastAPI-застосунку |
| `backend/routes/` | REST API маршрути для рейсів, прогнозів, аналітики, квитків та авторизації |
| `backend/db/` | Операції з PostgreSQL і створення необхідних таблиць |
| `backend/ml/` | Навчання моделей, збережені артефакти, дослідницькі ноутбуки й звіти |
| `backend/services/` | Сервіси інтеграції, авторизації та бізнес-логіки |
| `frontend/src/` | Клієнтський React-застосунок |
| `etl/` | Скрипти збору, підготовки та експорту даних |
| `docker-compose.yml` | Запуск PostgreSQL, backend і frontend в Docker |

---

## Як запустити проєкт з нуля

### 1. Встановлення інструментів

- Git
- Docker Desktop
- Python 3.11+
- Node.js 20+ та npm

Для найпростішого запуску достатньо Docker Desktop.

### 2. Клонування репозиторію

```bash
git clone https://github.com/napaintga/flight-price-predictor.git
cd flight-price-predictor
```

### 3. Створення `.env` для backend

Створіть файл `backend/.env` і заповніть змінні середовища:

```env
SERPAPI_KEY=your_serpapi_key
DATABASE_URL=postgresql://flight_user:flight_pass@localhost:5432/flight_db
AUTH_SECRET=change_me
```

Під час запуску через Docker Compose значення `DATABASE_URL` для backend автоматично замінюється на адресу контейнера бази даних.

### 4. Запуск через Docker Compose

```bash
docker compose up --build
```

Після запуску сервіси будуть доступні за адресами:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- PostgreSQL: `localhost:5432`

---

## Локальний запуск без Docker

### Backend

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend за замовчуванням запускається через Vite і працює з API backend.

---

## API приклади

### Авторизація

**POST `/api/auth/register`**

```json
{
  "email": "user@example.com",
  "password": "123456"
}
```

**POST `/api/auth/login`**

```json
{
  "email": "user@example.com",
  "password": "123456"
}
```

**GET `/api/auth/me`**

Повертає інформацію про поточного користувача.

---

### Рейси

**GET `/api/flights`**

Приклад:

```bash
curl "http://localhost:8000/api/flights?departure_id=CDG&arrival_id=KRK&outbound_date=2026-03-10&adults=1"
```

**GET `/api/flights/{flight_uid}`**

Повертає детальну інформацію про конкретний рейс.

**GET `/api/flights/{flight_uid}/price-history`**

Повертає історію ціни рейсу.

**GET `/api/flights/{flight_uid}/price-snapshots`**

Повертає локально збережені знімки ціни з бази даних.

---

### Прогнозування та аналітика

**GET `/api/predictions/flight/{flight_uid}`**

Повертає прогноз ціни для рейсу.

**GET `/api/price-insights`**

Повертає аналітичні висновки щодо поточної ціни.

**GET `/api/analytics/metrics`**

Повертає метрики якості активної ML-моделі.

**GET `/api/analytics/actual-vs-predicted`**

Повертає дані для графіка порівняння фактичних і прогнозованих цін.

**GET `/api/analytics/dashboard`**

Повертає агреговані дані для аналітичної сторінки.

---

## Інструкція для користувача

1. Відкрити `http://localhost:3000`.
2. Зареєструватися або увійти в обліковий запис.
3. На сторінці пошуку вказати місто вильоту, місто прибуття, дату та кількість пасажирів.
4. Переглянути список знайдених рейсів.
5. Відкрити деталі потрібного рейсу.
6. Переглянути прогнозовану ціну, історію зміни ціни та рекомендаційні інсайти.
7. За потреби додати квиток до обраного або перейти на сторінку аналітики.

---

## Приклади / скриншоти

### Сторінка пошуку рейсів та список результатів
![Search Results](./screenshots/search_results.png)

### Сторінка деталей рейсу
![Flight Details](./screenshots/flight_details.png)

### Блок прогнозування ціни
![Price Prediction](./screenshots/price_prediction.png)

### Аналітична сторінка
![Analytics Dashboard 1](./screenshots/analytics_dashboard1.png)

![Analytics Dashboard 2](./screenshots/analytics_dashboard2.png)

---

## Проблеми і рішення

| Проблема | Рішення |
|---|---|
| Backend не стартує через помилку `SERPAPI_KEY` | Перевірити наявність ключа в `backend/.env` |
| Не вдається підключитися до PostgreSQL | Перевірити `DATABASE_URL` і чи запущений контейнер `db` |
| Frontend не отримує дані | Переконатися, що backend доступний на `http://localhost:8000` |
| Порожній список рейсів | Перевірити параметри пошуку, дату та доступність SerpApi |
| Не відображається прогноз | Перевірити наявність артефактів моделі в `backend/ml/` |
| CORS помилка | Переконатися, що запити йдуть на backend FastAPI, де CORS middleware вже увімкнено |

---

## Використані джерела / документація

- FastAPI documentation: https://fastapi.tiangolo.com/
- React documentation: https://react.dev/
- PostgreSQL documentation: https://www.postgresql.org/docs/
- scikit-learn documentation: https://scikit-learn.org/
- XGBoost documentation: https://xgboost.readthedocs.io/
- SerpApi Google Flights API documentation: https://serpapi.com/google-flights-api

---
