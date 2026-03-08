# ManbaAI (Replit-ready)

Telegram uchun AI knowledge bot. Foydalanuvchi yuborgan shaxsiy va ommaviy ma'lumotlardan javob beradi.

## Nimalar ishlaydi
- `/start` -> majburiy kanal obunasi tekshiruvi -> interfeys tilini tanlash
- Savolga javob berish: private + public qidiruv bir vaqtda
- Javob 2 bo'limda chiqadi: private/public
- Har bo'limda 3 qism bor: qisqa javob, batafsil, manba
- PDF, DOCX, TXT, rasm, ovoz, oddiy matn qabul qiladi
- Asl fayl Telegram serverida turadi, bot esa `file_id` va indekslangan matnni saqlaydi
- Ommaviy fayllar moderatsiyadan o'tadi
- Admin dashboard
- Ommaviy fayllarni CSV eksport qilish
- Dubl fayl aniqlash
- Loglar

## Replit'da ishga tushirish
1. Yangi **Python Repl** oching.
2. Shu fayllarni loyihaga yuklang.
3. `Secrets` bo'limiga `.env.example` dagi o'zgaruvchilarni kiriting.
4. Shell'da o'rnating:
   ```bash
   pip install -r requirements.txt
   ```
5. Run tugmasini bosing yoki shell'da:
   ```bash
   python main.py
   ```

## Kerakli sozlamalar
- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `ADMIN_USER_IDS`
- `REQUIRED_CHANNEL_IDS`
- `REQUIRED_CHANNEL_URLS`

## Telegram serverda fayl saqlash
Bu loyiha foydalanuvchi yuborgan asl faylni o'z serveringizda doimiy saqlamaydi.
- Telegram `file_id` saqlanadi
- Qidiruv uchun ajratilgan matn va embedding SQLite bazada saqlanadi
- Temp fayl faqat parsing vaqtida ishlatiladi

## Muhim eslatma
Bu MVP / starter code. Kengaytirish uchun quyidagilarni keyin qo'shish mumkin:
- webhook deploy
- PostgreSQL
- Qdrant yoki pgvector
- admin panel uchun inline sahifalash
- user darajalari va blok tizimini chuqurlashtirish
- smart tavsiyalar UI

## Asosiy papkalar
- `main.py` - bot entrypoint
- `db.py` - SQLite sxema va querylar
- `services/openai_service.py` - OpenAI bilan ishlash
- `services/file_service.py` - upload parsing
- `services/search_service.py` - RAG qidiruv
- `texts.py` - ko'p tilli interfeys matnlari
- `keyboards.py` - Telegram tugmalari
