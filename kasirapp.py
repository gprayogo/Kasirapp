import os
import asyncio
import aiosqlite
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("8062375197:AAESP2LXxr6bYjOEJuHohEEYOTAjfPDlo-w") or "8062375197:AAESP2LXxr6bYjOEJuHohEEYOTAjfPDlo-w"
DB_FILE = 'cashier.db'
WEBHOOK_URL = os.getenv("https://kasirapp.up.railway.app/") or "https://kasirapp.up.railway.app/"

app = Flask(__name__)

# Bot init
bot_app = ApplicationBuilder().token(TOKEN).build()

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS cashier (
            id INTEGER PRIMARY KEY,
            modal INTEGER,
            total_received INTEGER,
            total_change INTEGER,
            total_shortage INTEGER
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount INTEGER
        )''')
        await db.execute('''INSERT OR IGNORE INTO cashier (id, modal, total_received, total_change, total_shortage)
                            VALUES (1, 0, 0, 0, 0)''')
        await db.commit()

# Handlers
async def start_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /start_shift <modal>")
        return
    modal = int(context.args[0])
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''UPDATE cashier SET modal = ?, total_received = 0, total_change = 0, total_shortage = 0 WHERE id = 1''', (modal,))
        await db.execute('DELETE FROM withdrawals')
        await db.commit()
    await update.message.reply_text(f"Shift dimulai dengan modal: {modal}")

async def transaksi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /transaksi <total_tagihan> <uang_diterima>")
        return
    try:
        total = int(context.args[0])
        diterima = int(context.args[1])
    except ValueError:
        await update.message.reply_text("Input harus angka.")
        return
    kembalian = diterima - total if diterima >= total else 0
    shortage = total - diterima if diterima < total else 0
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''UPDATE cashier SET total_received = total_received + ?, total_change = total_change + ?, total_shortage = total_shortage + ? WHERE id = 1''', (diterima, kembalian, shortage))
        await db.commit()
    msg = f"Transaksi dicatat:\nTotal belanja: {total}\nUang diterima: {diterima}\nKembalian: {kembalian}"
    if shortage > 0:
        msg += f"\n\n⚠️ Ada kekurangan: {shortage}"
    await update.message.reply_text(msg)

async def tarik_tunai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /tarik <jumlah>")
        return
    amount = int(context.args[0])
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT INTO withdrawals (amount) VALUES (?)', (amount,))
        await db.commit()
    await update.message.reply_text(f"Penarikan tunai dicatat: {amount}")

async def cek_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT total_shortage FROM cashier WHERE id = 1') as cursor:
            row = await cursor.fetchone()
            total_shortage = row[0] if row else 0
        async with db.execute('SELECT COUNT(*), SUM(amount) FROM withdrawals') as cursor:
            count_row = await cursor.fetchone()
            jumlah_transaksi = count_row[0]
            total_ditarik = count_row[1] if count_row[1] else 0
        async with db.execute('SELECT id, amount FROM withdrawals') as cursor:
            details = await cursor.fetchall()
    msg = (f"Status Saat Ini:\n\n"
           f"Total Kekurangan (utang): {total_shortage}\n"
           f"Jumlah Transaksi Penarikan: {jumlah_transaksi}\n"
           f"Total Uang yang Sudah Ditarik: {total_ditarik}\n\n"
           f"Detil Penarikan:\n")
    if details:
        for idx, (wid, amt) in enumerate(details, 1):
            msg += f"{idx}. {amt}\n"
    else:
        msg += "(Belum ada penarikan)"
    await update.message.reply_text(msg)

async def tutup_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT modal, total_received, total_change, total_shortage FROM cashier WHERE id = 1') as cursor:
            row = await cursor.fetchone()
            if row:
                modal, total_received, total_change, total_shortage = row
            else:
                await update.message.reply_text("Belum ada shift yang dimulai.")
                return
        async with db.execute('SELECT SUM(amount) FROM withdrawals') as cursor:
            wd_row = await cursor.fetchone()
            total_withdrawal = wd_row[0] if wd_row[0] else 0
    expected_cash = modal + total_received - total_change - total_withdrawal - total_shortage
    msg = (f"Shift ditutup.\n\n"
           f"Modal: {modal}\n"
           f"Total diterima: {total_received}\n"
           f"Total kembalian: {total_change}\n"
           f"Total kekurangan (utang): {total_shortage}\n"
           f"Total penarikan: {total_withdrawal}\n\n"
           f"➡️ Uang seharusnya di laci: {expected_cash}")
    await update.message.reply_text(msg)

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    asyncio.run(bot_app.process_update(update))
    return 'OK'

@app.route('/')
def index():
    return 'Bot is running!'

async def set_webhook():
    await bot_app.bot.set_webhook(WEBHOOK_URL + TOKEN)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    loop.run_until_complete(set_webhook())
    bot_app.add_handler(CommandHandler("start_shift", start_shift))
    bot_app.add_handler(CommandHandler("transaksi", transaksi))
    bot_app.add_handler(CommandHandler("tarik", tarik_tunai))
    bot_app.add_handler(CommandHandler("status", cek_status))
    bot_app.add_handler(CommandHandler("tutup_shift", tutup_shift))
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
