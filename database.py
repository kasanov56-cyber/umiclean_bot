import aiosqlite

DB_NAME = 'umiclean_db.sqlite'

async def init_db():
    """Инициализирует базу данных и заполняет ее базовыми ценами."""
    async with aiosqlite.connect(DB_NAME) as db:
        # 1. Создание таблицы цен
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                key TEXT PRIMARY KEY,
                value REAL,
                description TEXT,
                category TEXT
            )
        """)
        
        # 2. Базовые цены за м² для основных видов уборки
        base_prices = [
            ('general_cleaning', 150.0, 'Генеральная уборка', 'base'),
            ('after_repair', 250.0, 'Уборка после ремонта', 'base'),
            ('support_cleaning', 100.0, 'Поддерживающая уборка', 'base'),
        ]
        
        # 3. Дополнительные услуги (фиксированная цена или за м²)
        addon_prices = [
            ('windows_price', 300.0, 'Мытье окон (за м²)', 'addon'),
            ('fridge_price', 1500.0, 'Мытье холодильника', 'addon'),
            ('oven_price', 1000.0, 'Мытье духовки/плиты', 'addon'),
        ]

        # Заполнение базы данных (INSERT OR IGNORE гарантирует, что существующие цены не перезапишутся)
        for key, value, desc, cat in base_prices + addon_prices:
            await db.execute(
                "INSERT OR IGNORE INTO prices (key, value, description, category) VALUES (?, ?, ?, ?)",
                (key, value, desc, cat)
            )
        
        await db.commit()

# --- Функции для работы с ценами ---

async def get_price(key: str) -> float:
    """Получает цену по ключу."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM prices WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0.0

async def get_base_services():
    """Получает основные виды уборки для кнопок."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Возвращает (key, description)
        async with db.execute("SELECT key, description FROM prices WHERE category = 'base'") as cursor:
            return await cursor.fetchall()

async def get_addon_services():
    """Получает дополнительные услуги для кнопок."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Возвращает (key, description, value)
        async with db.execute("SELECT key, description, value FROM prices WHERE category = 'addon'") as cursor:
            return await cursor.fetchall()

async def get_service_description(key: str) -> str:
    """Получает полное описание услуги по ключу."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT description FROM prices WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "Услуга не найдена"


# --- Функции для Админ-панели ---

async def get_all_prices():
    """Получает все цены и описания для админки."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Возвращает (key, value, description)
        async with db.execute("SELECT key, value, description FROM prices") as cursor:
            return await cursor.fetchall()

async def update_price(key: str, new_value: float) -> bool:
    """Обновляет цену по ключу."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE prices SET value = ? WHERE key = ?", (new_value, key))
        await db.commit()
        return db.changes > 0
