import asyncio
import aiosqlite
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

DB_FILE = 'cashier.db'

# INIT DB
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS cashier (
                id INTEGER PRIMARY KEY,
                modal INTEGER,
                total_received INTEGER,
                total_change INTEGER,
                total_shortage INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount INTEGER
            )
        ''')
        await db.execute('''
            INSERT OR IGNORE INTO cashier (id, modal, total_received, total_change, total_shortage)
            VALUES (1, 0, 0, 0, 0)
        ''')
        await db.commit()

# START SHIFT
async def start_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /start_shift <modal>")
        return

    modal = int(context.args[0])
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            UPDATE cashier
            SET modal = ?, total_received = 0, total_change = 0, total_shortage = 0
            WHERE id = 1
        ''', (modal,))
        await db.execute('DELETE FROM withdrawals')
        await db.commit()

    await update.message.reply_text(f"Shift dimulai dengan modal: {modal}")

# TRANSAKSI
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
        await db.execute('''
            UPDATE cashier SET
                total_received = total_received + ?,
                total_change = total_change + ?,
                total_shortage = total_shortage + ?
            WHERE id = 1
        ''', (diterima, kembalian, shortage))
        await db.commit()

    msg = f"Transaksi dicatat:\nTotal belanja: {total}\nUang diterima: {diterima}\nKembalian: {kembalian}"
    if shortage > 0:
        msg += f"\n\n⚠️ Ada kekurangan: {shortage}"

    await update.message.reply_text(msg)

# PENARIKAN
async def tarik_tunai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /tarik <jumlah>")
        return

    amount = int(context.args[0])
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('INSERT INTO withdrawals (amount) VALUES (?)', (amount,))
        await db.commit()

    await update.message.reply_text(f"Penarikan tunai dicatat: {amount}")

# STATUS
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

    msg = (
        f"Status Saat Ini:\n\n"
        f"Total Kekurangan (utang): {total_shortage}\n"
        f"Jumlah Transaksi Penarikan: {jumlah_transaksi}\n"
        f"Total Uang yang Sudah Ditarik: {total_ditarik}\n\n"
        f"Detil Penarikan:\n"
    )

    if details:
        for idx, (wid, amt) in enumerate(details, 1):
            msg += f"{idx}. {amt}\n"
    else:
        msg += "(Belum ada penarikan)"

    await update.message.reply_text(msg)

# TUTUP SHIFT
async def tutup_shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute('SELECT modal, total_received, total_change, total_shortage FROM cashier WHERE id = 1') as cursor:
            row = await cursor.fetchone()
            if row:
                modal, total_received, total_change, total_shortage = row
            else:
                await update.message.reply_text("Data tidak ditemukan.")
                return

        async with db.execute('SELECT SUM(amount) FROM withdrawals') as cursor:
            wd_row = await cursor.fetchone()
            total_withdrawal = wd_row[0] if wd_row[0] else 0

    expected_cash = modal + total_received - total_change - total_withdrawal - total_shortage

    msg = (
        f"Shift ditutup.\n\n"
        f"Modal: {modal}\n"
        f"Total diterima: {total_received}\n"
        f"Total kembalian: {total_change}\n"
        f"Total kekurangan (utang): {total_shortage}\n"
        f"Total penarikan: {total_withdrawal}\n\n"
        f"➡️ Uang seharusnya di laci: {expected_cash}"
    )
    await update.message.reply_text(msg)

# MAIN
async def main():
    await init_db()
    app = ApplicationBuilder().token('8062375197:AAESP2LXxr6bYjOEJuHohEEYOTAjfPDlo-w').build()

    app.add_handler(CommandHandler("start_shift", start_shift))
    app.add_handler(CommandHandler("transaksi", transaksi))
    app.add_handler(CommandHandler("tarik", tarik_tunai))
    app.add_handler(CommandHandler("status", cek_status))
    app.add_handler(CommandHandler("tutup_shift", tutup_shift))

    await app.run_polling()

if __name__ == '__main__':
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())