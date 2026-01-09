import aiosqlite

DB_NAME = 'umiclean_db.sqlite'

async def init_db():
    """Инициализирует базу данных и заполняет ее базовыми ценами."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Создание таблицы цен
        await db.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                key TEXT PRIMARY KEY,
                value REAL,
                description TEXT
            )
        """)
        
        # Базовые услуги (примеры цен в сомах/м2)
        base_prices = [
            ('general_cleaning_m2', 150.0, 'Генеральная уборка (цена за м²)'),
            ('after_repair_m2', 250.0, 'Уборка после ремонта (цена за м²)'),
            ('windows_price', 300.0, 'Мытье окон (цена за м²)'),
            ('fridge_price', 1500.0, 'Мытье холодильника (фиксированная цена)'),
        ]

        # Добавление базовых цен, если таблица пуста
        for key, value, desc in base_prices:
            await db.execute(
                "INSERT OR IGNORE INTO prices (key, value, description) VALUES (?, ?, ?)",
                (key, value, desc)
            )
        
        await db.commit()

async def get_price(key: str) -> float:
    """Получает цену по ключу."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT value FROM prices WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0.0

async def update_price(key: str, new_value: float) -> bool:
    """Обновляет цену по ключу."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE prices SET value = ? WHERE key = ?", (new_value, key))
        await db.commit()
        return db.changes > 0

# --- Функции для админ-панели (список всех услуг) ---

async def get_all_prices():
    """Получает все цены и описания для админки."""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT key, value, description FROM prices") as cursor:
            return await cursor.fetchall()
