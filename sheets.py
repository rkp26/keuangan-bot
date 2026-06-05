import os
import json
from datetime import datetime
import pytz
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_ID = os.environ.get("SHEET_ID")
WIB = pytz.timezone("Asia/Jakarta")

SHEET_MASUK   = "Pemasukan"
SHEET_KELUAR  = "Pengeluaran"
SHEET_SUMMARY = "Summary"
SHEET_BUDGET  = "Budget"

def get_service():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds).spreadsheets()

def read_sheet(sheet_name, range_="A:F"):
    svc = get_service()
    result = svc.values().get(
        spreadsheetId=SHEET_ID,
        range=f"{sheet_name}!{range_}"
    ).execute()
    return result.get("values", [])

def append_row(sheet_name, row):
    svc = get_service()
    svc.values().append(
        spreadsheetId=SHEET_ID,
        range=f"{sheet_name}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]}
    ).execute()

def update_cell(sheet_name, range_, values):
    svc = get_service()
    svc.values().update(
        spreadsheetId=SHEET_ID,
        range=f"{sheet_name}!{range_}",
        valueInputOption="USER_ENTERED",
        body={"values": values}
    ).execute()

def clear_range(sheet_name, range_):
    svc = get_service()
    svc.values().clear(
        spreadsheetId=SHEET_ID,
        range=f"{sheet_name}!{range_}"
    ).execute()

# ── INIT HEADERS ──────────────────────────────────────────────
def init_headers():
    for sheet_name in [SHEET_MASUK, SHEET_KELUAR]:
        rows = read_sheet(sheet_name, "A1:G1")
        if not rows:
            append_row(sheet_name, ["No", "Tanggal", "Waktu", "Keterangan", "Kategori", "Nominal", "Dicatat Oleh"])

# ── SIMPAN TRANSAKSI ──────────────────────────────────────────
def simpan_transaksi(tipe, nominal, keterangan, kategori, tanggal, waktu, name):
    sheet_name = SHEET_MASUK if tipe == "masuk" else SHEET_KELUAR
    init_headers()
    rows = read_sheet(sheet_name, "A:A")
    no = len(rows)  # baris header = 1, jadi no = len - 1 + 1 = len
    append_row(sheet_name, [no, tanggal, waktu, keterangan, kategori, nominal, name])
    update_summary()

# ── GET SALDO ─────────────────────────────────────────────────
def get_saldo():
    masuk_rows  = read_sheet(SHEET_MASUK,  "F2:F")
    keluar_rows = read_sheet(SHEET_KELUAR, "F2:F")
    total_masuk  = sum(float(r[0]) for r in masuk_rows  if r and r[0])
    total_keluar = sum(float(r[0]) for r in keluar_rows if r and r[0])
    return {
        "total_masuk":  total_masuk,
        "total_keluar": total_keluar,
        "saldo":        total_masuk - total_keluar
    }

# ── GET REKAP BULAN ───────────────────────────────────────────
def get_rekap_bulan():
    now   = datetime.now(WIB)
    bln   = now.strftime("%m")
    thn   = now.strftime("%Y")
    nama_bln = ["Januari","Februari","Maret","April","Mei","Juni",
                "Juli","Agustus","September","Oktober","November","Desember"][now.month - 1]

    masuk_rows  = read_sheet(SHEET_MASUK,  "A:G")
    keluar_rows = read_sheet(SHEET_KELUAR, "A:G")

    total_masuk = 0
    for r in masuk_rows[1:]:
        if len(r) >= 6 and r[1]:
            tgl = str(r[1])
            if tgl[3:5] == bln and tgl[6:10] == thn:
                try: total_masuk += float(r[5])
                except: pass

    total_keluar = 0
    breakdown = {}
    for r in keluar_rows[1:]:
        if len(r) >= 6 and r[1]:
            tgl = str(r[1])
            if tgl[3:5] == bln and tgl[6:10] == thn:
                try:
                    nominal = float(r[5])
                    total_keluar += nominal
                    kat = r[4] if len(r) > 4 else "lainnya"
                    breakdown[kat] = breakdown.get(kat, 0) + nominal
                except: pass

    return {
        "masuk": total_masuk,
        "keluar": total_keluar,
        "nama_bulan": f"{nama_bln} {thn}",
        "breakdown": breakdown
    }

# ── GET LAST TRANSAKSI ────────────────────────────────────────
def get_last_transaksi(n=10):
    masuk_rows  = read_sheet(SHEET_MASUK,  "A:G")
    keluar_rows = read_sheet(SHEET_KELUAR, "A:G")

    all_tx = []
    for r in masuk_rows[1:]:
        if len(r) >= 6 and r[1]:
            all_tx.append({"tgl": r[1], "waktu": r[2] if len(r) > 2 else "", "keterangan": r[3], "nominal": float(r[5]), "tipe": "masuk"})
    for r in keluar_rows[1:]:
        if len(r) >= 6 and r[1]:
            all_tx.append({"tgl": r[1], "waktu": r[2] if len(r) > 2 else "", "keterangan": r[3], "nominal": float(r[5]), "tipe": "keluar"})

    all_tx.sort(key=lambda x: x["tgl"] + " " + x["waktu"], reverse=True)
    return [{"tanggal": t["tgl"], "waktu": t["waktu"], "keterangan": t["keterangan"], "nominal": t["nominal"], "tipe": t["tipe"]} for t in all_tx[:n]]

# ── BUDGET ────────────────────────────────────────────────────
def set_budget(nominal):
    now = datetime.now(WIB)
    bln_thn = now.strftime("%m/%Y")
    rows = read_sheet(SHEET_BUDGET, "A:B")
    # Cek apakah bulan ini udah ada
    for i, r in enumerate(rows):
        if r and r[0] == bln_thn:
            update_cell(SHEET_BUDGET, f"B{i+1}", [[nominal]])
            return
    append_row(SHEET_BUDGET, [bln_thn, nominal])

def cek_budget():
    now = datetime.now(WIB)
    bln = now.strftime("%m")
    thn = now.strftime("%Y")
    bln_thn = now.strftime("%m/%Y")

    rows = read_sheet(SHEET_BUDGET, "A:B")
    budget = None
    for r in rows:
        if r and len(r) >= 2 and r[0] == bln_thn:
            try: budget = float(r[1])
            except: pass
            break

    if budget is None:
        return None

    # Hitung total keluar bulan ini
    keluar_rows = read_sheet(SHEET_KELUAR, "A:G")
    total_keluar = 0
    for r in keluar_rows[1:]:
        if len(r) >= 6 and r[1]:
            tgl = str(r[1])
            if tgl[3:5] == bln and tgl[6:10] == thn:
                try: total_keluar += float(r[5])
                except: pass

    return {"budget": budget, "keluar": total_keluar}

# ── GET SUMMARY (alias) ───────────────────────────────────────
def get_summary():
    return get_saldo()

# ── UPDATE SUMMARY ────────────────────────────────────────────
def update_summary():
    data = get_saldo()
    now  = datetime.now(WIB).strftime("%d/%m/%Y %H:%M")
    clear_range(SHEET_SUMMARY, "A1:B10")
    update_cell(SHEET_SUMMARY, "A1:B6", [
        ["RINGKASAN KEUANGAN", ""],
        ["", ""],
        ["Total Pemasukan",   data["total_masuk"]],
        ["Total Pengeluaran", data["total_keluar"]],
        ["SALDO",             data["saldo"]],
        ["Terakhir Update",   now],
    ])
    try:
        from dashboard import build_dashboard
        build_dashboard()
    except Exception as e:
        print(f"Dashboard update error: {e}")
