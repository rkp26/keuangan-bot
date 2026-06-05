import os
import logging
from datetime import datetime
import pytz
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes
)
from sheets import (
    simpan_transaksi, get_saldo,
    get_rekap_bulan, get_last_transaksi, cek_budget, set_budget
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WIB = pytz.timezone("Asia/Jakarta")

KATA_MASUK = [
    "gaji", "gajian", "bonus", "terima", "dapat", "dapet",
    "pemasukan", "income", "bayaran", "fee", "honor", "thr",
    "dividen", "refund", "cashback", "topup", "transfer masuk"
]
KATA_KELUAR = [
    "beli", "bayar", "makan", "minum", "belanja", "jajan",
    "bensin", "parkir", "listrik", "wifi", "internet", "tagihan",
    "cicilan", "nongkrong", "nonton", "ojek", "grab", "gojek",
    "tokopedia", "shopee", "ngopi", "kopi", "pengeluaran", "expense",
    "laundry", "obat", "pulsa", "paket data"
]

KATEGORI = {
    "makan": ["makan", "minum", "jajan", "nongkrong", "ngopi", "kopi", "resto", "warteg"],
    "transport": ["bensin", "parkir", "ojek", "grab", "gojek", "taxi", "busway", "kereta"],
    "tagihan": ["listrik", "wifi", "internet", "tagihan", "cicilan", "pulsa", "paket data"],
    "belanja": ["beli", "belanja", "tokopedia", "shopee", "lazada"],
    "hiburan": ["nonton", "bioskop", "game", "spotify", "netflix"],
    "kesehatan": ["obat", "dokter", "klinik", "apotek"],
    "laundry": ["laundry", "cuci"],
}

def detect_kategori(text):
    text = text.lower()
    for kat, keywords in KATEGORI.items():
        for kw in keywords:
            if kw in text:
                return kat
    return "lainnya"

def parse_nominal(text):
    import re
    match = re.search(r'(\d[\d.,]*)\s*(k|rb|ribu|jt|juta|m|miliar)?', text, re.IGNORECASE)
    if not match:
        return None
    nominal = float(match.group(1).replace(",", "").replace(".", ""))
    satuan = (match.group(2) or "").lower()
    if satuan in ["k", "rb", "ribu"]:
        nominal *= 1000
    elif satuan in ["jt", "juta"]:
        nominal *= 1000000
    elif satuan in ["m", "miliar"]:
        nominal *= 1000000000
    return int(nominal) if nominal > 0 else None

def parse_natural_language(text):
    import re
    lower = text.lower()
    nominal = parse_nominal(text)
    if not nominal:
        return None
    tipe = None
    for kata in KATA_MASUK:
        if kata in lower:
            tipe = "masuk"
            break
    if not tipe:
        for kata in KATA_KELUAR:
            if kata in lower:
                tipe = "keluar"
                break
    if not tipe:
        return None
    keterangan = re.sub(r'\d[\d.,]*\s*(k|rb|ribu|jt|juta|m|miliar)?', '', text, flags=re.IGNORECASE).strip()
    keterangan = keterangan or ("-" if tipe == "masuk" else "Pengeluaran")
    kategori = detect_kategori(text) if tipe == "keluar" else "pemasukan"
    return {"tipe": tipe, "nominal": nominal, "keterangan": keterangan, "kategori": kategori}

def format_rp(nominal):
    return f"Rp {int(nominal):,}".replace(",", ".")

def get_keyboard():
    keyboard = [
        [KeyboardButton("💰 Saldo"), KeyboardButton("📊 Rekap Bulan Ini")],
        [KeyboardButton("📋 Transaksi Terakhir"), KeyboardButton("🎯 Cek Budget")],
        [KeyboardButton("❓ Bantuan")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    await update.message.reply_text(
        f"👋 Halo *{name}*! Gua bot keuangan lu.\n\n"
        f"*📌 Command:*\n"
        f"/masuk 5000000 Gaji\n"
        f"/keluar 25000 Makan siang\n"
        f"/saldo — cek saldo\n"
        f"/rekap — rekap bulan ini\n"
        f"/budget 3000000 — set budget\n\n"
        f"*💬 Natural Language:*\n"
        f"• gajian 5jt\n"
        f"• beli bensin 50rb\n"
        f"• bayar listrik 200000\n\n"
        f"*Shorthand:* 50k = 50.000 | 2jt = 2.000.000",
        parse_mode="Markdown",
        reply_markup=get_keyboard()
    )

async def cmd_masuk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Format: /masuk 5000000 Gaji bulan ini")
        return
    nominal = parse_nominal(context.args[0])
    if not nominal:
        await update.message.reply_text("❌ Nominal tidak valid.")
        return
    keterangan = " ".join(context.args[1:]) or "Pemasukan"
    await proses_simpan(update, "masuk", nominal, keterangan, "pemasukan")

async def cmd_keluar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Format: /keluar 25000 Makan siang")
        return
    nominal = parse_nominal(context.args[0])
    if not nominal:
        await update.message.reply_text("❌ Nominal tidak valid.")
        return
    keterangan = " ".join(context.args[1:]) or "Pengeluaran"
    kategori = detect_kategori(keterangan)
    await proses_simpan(update, "keluar", nominal, keterangan, kategori)

async def cmd_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_saldo()
    saldo = data["saldo"]
    emoji = "✅" if saldo >= 0 else "⚠️"
    await update.message.reply_text(
        f"📊 *RINGKASAN KEUANGAN*\n\n"
        f"💰 Total Pemasukan  : {format_rp(data['total_masuk'])}\n"
        f"💸 Total Pengeluaran: {format_rp(data['total_keluar'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{emoji} *Saldo: {format_rp(saldo)}*",
        parse_mode="Markdown"
    )

async def cmd_rekap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_rekap_bulan()
    net = data["masuk"] - data["keluar"]
    emoji = "✅" if net >= 0 else "⚠️"
    breakdown = data.get("breakdown", {})
    kat_txt = ""
    if breakdown:
        kat_txt = "\n\n*📂 Per Kategori:*\n"
        for kat, total in sorted(breakdown.items(), key=lambda x: -x[1]):
            kat_txt += f"  • {kat.capitalize()}: {format_rp(total)}\n"
    await update.message.reply_text(
        f"📅 *REKAP {data['nama_bulan'].upper()}*\n\n"
        f"💰 Pemasukan  : {format_rp(data['masuk'])}\n"
        f"💸 Pengeluaran: {format_rp(data['keluar'])}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{emoji} *Net: {format_rp(net)}*{kat_txt}",
        parse_mode="Markdown"
    )

async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        data = cek_budget()
        if not data:
            await update.message.reply_text("🎯 Belum ada budget.\nSet dengan: /budget 3000000")
            return
        sisa = data["budget"] - data["keluar"]
        persen = (data["keluar"] / data["budget"] * 100) if data["budget"] > 0 else 0
        bar = "█" * int(persen / 10) + "░" * (10 - int(persen / 10))
        emoji = "✅" if sisa >= 0 else "🚨"
        await update.message.reply_text(
            f"🎯 *BUDGET BULAN INI*\n\n"
            f"Budget  : {format_rp(data['budget'])}\n"
            f"Terpakai: {format_rp(data['keluar'])} ({persen:.1f}%)\n"
            f"Sisa    : {format_rp(sisa)}\n\n"
            f"{bar} {persen:.0f}%\n\n"
            f"{emoji} {'Masih aman' if sisa >= 0 else 'OVER BUDGET!'}",
            parse_mode="Markdown"
        )
        return
    nominal = parse_nominal(context.args[0])
    if not nominal:
        await update.message.reply_text("❌ Format: /budget 3000000")
        return
    set_budget(nominal)
    await update.message.reply_text(
        f"🎯 Budget di-set: *{format_rp(nominal)}*",
        parse_mode="Markdown"
    )

async def cmd_last(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txs = get_last_transaksi(10)
    if not txs:
        await update.message.reply_text("📋 Belum ada transaksi.")
        return
    txt = "🕐 *10 TRANSAKSI TERAKHIR*\n\n"
    for tx in txs:
        emoji = "💰" if tx["tipe"] == "masuk" else "💸"
        txt += f"{emoji} {tx['tanggal']} — {tx['keterangan']}\n    {format_rp(tx['nominal'])}\n\n"
    await update.message.reply_text(txt, parse_mode="Markdown")

async def proses_simpan(update, tipe, nominal, keterangan, kategori):
    name = update.effective_user.first_name
    now = datetime.now(WIB)
    tanggal = now.strftime("%d/%m/%Y")
    waktu = now.strftime("%H:%M")
    simpan_transaksi(tipe, nominal, keterangan, kategori, tanggal, waktu, name)
    saldo_data = get_saldo()
    saldo = saldo_data["saldo"]
    emoji = "💰" if tipe == "masuk" else "💸"
    label = "Pemasukan" if tipe == "masuk" else "Pengeluaran"
    txt = (
        f"{emoji} *{label} tercatat!*\n\n"
        f"📝 Keterangan : {keterangan}\n"
        f"💵 Nominal    : {format_rp(nominal)}\n"
        f"📂 Kategori   : {kategori.capitalize()}\n"
        f"📅 Waktu      : {tanggal} {waktu}\n\n"
        f"💼 *Saldo: {format_rp(saldo)}*"
    )
    if tipe == "keluar":
        budget_data = cek_budget()
        if budget_data and budget_data["budget"] > 0:
            sisa = budget_data["budget"] - budget_data["keluar"]
            persen = budget_data["keluar"] / budget_data["budget"] * 100
            if persen >= 100:
                txt += f"\n\n🚨 *OVER BUDGET!*"
            elif persen >= 80:
                txt += f"\n\n⚠️ Budget terpakai {persen:.0f}%. Sisa {format_rp(sisa)}"
    await update.message.reply_text(txt, parse_mode="Markdown", reply_markup=get_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "💰 Saldo":
        await cmd_saldo(update, context); return
    if text == "📊 Rekap Bulan Ini":
        await cmd_rekap(update, context); return
    if text == "📋 Transaksi Terakhir":
        await cmd_last(update, context); return
    if text == "🎯 Cek Budget":
        context.args = []
        await cmd_budget(update, context); return
    if text == "❓ Bantuan":
        await start(update, context); return
    result = parse_natural_language(text)
    if result:
        await proses_simpan(update, result["tipe"], result["nominal"], result["keterangan"], result["kategori"])
        return
    await update.message.reply_text(
        f"🤔 Gua gak ngerti _\"{text}\"_\n\nKetik /bantuan atau tap tombol di bawah.",
        parse_mode="Markdown", reply_markup=get_keyboard()
    )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("masuk", cmd_masuk))
    app.add_handler(CommandHandler("keluar", cmd_keluar))
    app.add_handler(CommandHandler("saldo", cmd_saldo))
    app.add_handler(CommandHandler("summary", cmd_saldo))
    app.add_handler(CommandHandler("rekap", cmd_rekap))
    app.add_handler(CommandHandler("budget", cmd_budget))
    app.add_handler(CommandHandler("last", cmd_last))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(handle_callback))
    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

# ── PHOTO HANDLER ─────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Gua lagi baca struk-nya, tunggu sebentar...")
    
    try:
        # Ambil foto resolusi terbaik
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        
        from ocr import baca_struk
        result = baca_struk(bytes(image_bytes))
        
        if "error" in result:
            await update.message.reply_text(
                "❌ Gua gak bisa baca ini sebagai struk keuangan.\n"
                "Coba foto yang lebih jelas ya bro!"
            )
            return
        
        tipe      = result.get("tipe", "keluar")
        nominal   = int(result.get("nominal", 0))
        keterangan = result.get("keterangan", "Transaksi")
        kategori  = result.get("kategori", "lainnya")
        
        if nominal <= 0:
            await update.message.reply_text("❌ Gua gak bisa detect nominal-nya. Coba input manual ya.")
            return
        
        # Konfirmasi dulu sebelum simpan
        emoji = "💰" if tipe == "masuk" else "💸"
        label = "Pemasukan" if tipe == "masuk" else "Pengeluaran"
        
        # Simpan ke context buat konfirmasi
        context.user_data["pending_tx"] = {
            "tipe": tipe, "nominal": nominal,
            "keterangan": keterangan, "kategori": kategori
        }
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Ya, simpan", callback_data="confirm_tx"),
                InlineKeyboardButton("❌ Batal", callback_data="cancel_tx")
            ]
        ])
        
        await update.message.reply_text(
            f"📸 *Gua baca struk ini:*\n\n"
            f"{emoji} Tipe       : {label}\n"
            f"📝 Keterangan: {keterangan}\n"
            f"💵 Nominal   : {format_rp(nominal)}\n"
            f"📂 Kategori  : {kategori.capitalize()}\n\n"
            f"Bener gak bro?",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Photo handler error: {e}")
        await update.message.reply_text(
            "❌ Gagal baca struk. Coba lagi atau input manual ya bro."
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_tx":
        tx = context.user_data.get("pending_tx")
        if tx:
            await proses_simpan(query, tx["tipe"], tx["nominal"], tx["keterangan"], tx["kategori"])
            context.user_data.pop("pending_tx", None)
        else:
            await query.edit_message_text("❌ Data transaksi tidak ditemukan.")
    
    elif query.data == "cancel_tx":
        context.user_data.pop("pending_tx", None)
        await query.edit_message_text("❌ Transaksi dibatalkan.")
        
# ── PHOTO HANDLER ─────────────────────────────────────────────
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📸 Gua lagi baca struk-nya, tunggu sebentar...")
    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        from ocr import baca_struk
        result = baca_struk(bytes(image_bytes))
        if "error" in result:
            await update.message.reply_text("❌ Gua gak bisa baca ini sebagai struk keuangan.\nCoba foto yang lebih jelas ya bro!")
            return
        tipe = result.get("tipe", "keluar")
        nominal = int(result.get("nominal", 0))
        keterangan = result.get("keterangan", "Transaksi")
        kategori = result.get("kategori", "lainnya")
        if nominal <= 0:
            await update.message.reply_text("❌ Gua gak bisa detect nominal-nya. Coba input manual ya.")
            return
        emoji = "💰" if tipe == "masuk" else "💸"
        label = "Pemasukan" if tipe == "masuk" else "Pengeluaran"
        context.user_data["pending_tx"] = {"tipe": tipe, "nominal": nominal, "keterangan": keterangan, "kategori": kategori}
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Ya, simpan", callback_data="confirm_tx"), InlineKeyboardButton("❌ Batal", callback_data="cancel_tx")]])
        await update.message.reply_text(
            f"📸 *Gua baca struk ini:*\n\n{emoji} Tipe       : {label}\n📝 Keterangan: {keterangan}\n💵 Nominal   : {format_rp(nominal)}\n📂 Kategori  : {kategori.capitalize()}\n\nBener gak bro?",
            parse_mode="Markdown", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Photo handler error: {e}")
        await update.message.reply_text("❌ Gagal baca struk. Coba lagi atau input manual ya bro.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_tx":
        tx = context.user_data.get("pending_tx")
        if tx:
            await proses_simpan(query, tx["tipe"], tx["nominal"], tx["keterangan"], tx["kategori"])
            context.user_data.pop("pending_tx", None)
        else:
            await query.edit_message_text("❌ Data transaksi tidak ditemukan.")
    elif query.data == "cancel_tx":
        context.user_data.pop("pending_tx", None)
        await query.edit_message_text("❌ Transaksi dibatalkan.")
