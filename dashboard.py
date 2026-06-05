import os
import json
from datetime import datetime
import pytz
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
SHEET_ID = os.environ.get("SHEET_ID")
WIB = pytz.timezone("Asia/Jakarta")

COLORS = {
    "navy":       {"red": 0.102, "green": 0.137, "blue": 0.494},
    "dark_blue":  {"red": 0.157, "green": 0.196, "blue": 0.643},
    "green_bg":   {"red": 0.910, "green": 0.961, "blue": 0.918},
    "green_txt":  {"red": 0.180, "green": 0.490, "blue": 0.196},
    "red_bg":     {"red": 1.000, "green": 0.922, "blue": 0.922},
    "red_txt":    {"red": 0.776, "green": 0.157, "blue": 0.157},
    "blue_bg":    {"red": 0.890, "green": 0.937, "blue": 0.996},
    "blue_txt":   {"red": 0.086, "green": 0.337, "blue": 0.753},
    "yellow_bg":  {"red": 1.000, "green": 0.976, "blue": 0.882},
    "yellow_txt": {"red": 0.757, "green": 0.490, "blue": 0.000},
    "white":      {"red": 1.000, "green": 1.000, "blue": 1.000},
    "light_gray": {"red": 0.961, "green": 0.961, "blue": 0.961},
    "mid_gray":   {"red": 0.850, "green": 0.850, "blue": 0.850},
    "dark_gray":  {"red": 0.400, "green": 0.400, "blue": 0.400},
    "text_dark":  {"red": 0.200, "green": 0.200, "blue": 0.200},
}

def get_service():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)

def get_or_create_sheet(svc, name):
    ss = svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    for s in ss["sheets"]:
        if s["properties"]["title"] == name:
            return s["properties"]["sheetId"]
    # Buat baru
    resp = svc.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID,
        body={"requests": [{"addSheet": {"properties": {"title": name}}}]}
    ).execute()
    return resp["replies"][0]["addSheet"]["properties"]["sheetId"]

def read_sheet(svc, sheet_name, range_="A:G"):
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"{sheet_name}!{range_}"
    ).execute()
    return result.get("values", [])

def format_rp(n):
    n = int(n)
    return f"Rp {abs(n):,}".replace(",", ".")

def sum_col(rows, col=5):
    total = 0
    for r in rows[1:]:
        if len(r) > col:
            try: total += float(r[col])
            except: pass
    return total

def sum_bulan(rows, bln2d, thn, col=5):
    total = 0
    for r in rows[1:]:
        if len(r) > col and len(r) > 1 and r[1]:
            tgl = str(r[1])
            if tgl[3:5] == bln2d and tgl[6:10] == str(thn):
                try: total += float(r[col])
                except: pass
    return total

def get_breakdown(rows, bln2d, thn):
    breakdown = {}
    for r in rows[1:]:
        if len(r) > 5 and r[1]:
            tgl = str(r[1])
            if tgl[3:5] == bln2d and tgl[6:10] == str(thn):
                try:
                    kat = r[4] if len(r) > 4 else "lainnya"
                    breakdown[kat] = breakdown.get(kat, 0) + float(r[5])
                except: pass
    return breakdown

def get_tren(masuk_rows, keluar_rows, now):
    result = []
    for i in range(5, -1, -1):
        d = datetime(now.year, now.month, 1)
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        bln2d = str(m).zfill(2)
        nama = ["Jan","Feb","Mar","Apr","Mei","Jun","Jul","Agu","Sep","Okt","Nov","Des"][m-1]
        masuk  = sum_bulan(masuk_rows,  bln2d, y)
        keluar = sum_bulan(keluar_rows, bln2d, y)
        result.append({"label": f"{nama} {y}", "masuk": masuk, "keluar": keluar, "net": masuk - keluar})
    return result

def cell(row, col): 
    return {"rowIndex": row, "columnIndex": col}

def make_cell_data(value, fg=None, bg=None, bold=False, size=10, align="LEFT", valign="MIDDLE", wrap=False, number_format=None):
    fmt = {
        "textFormat": {
            "bold": bold,
            "fontSize": size,
        },
        "horizontalAlignment": align,
        "verticalAlignment": valign,
    }
    if fg: fmt["textFormat"]["foregroundColor"] = fg
    if bg: fmt["backgroundColor"] = bg
    if wrap: fmt["wrapStrategy"] = "WRAP"
    if number_format: fmt["numberFormat"] = number_format

    if isinstance(value, (int, float)):
        return {"userEnteredValue": {"numberValue": value}, "userEnteredFormat": fmt}
    else:
        return {"userEnteredValue": {"stringValue": str(value)}, "userEnteredFormat": fmt}

def build_dashboard():
    svc = get_service()
    sid = get_or_create_sheet(svc, "Dashboard")

    masuk_rows  = read_sheet(svc, "Pemasukan",  "A:G")
    keluar_rows = read_sheet(svc, "Pengeluaran", "A:G")
    budget_rows = read_sheet(svc, "Budget",      "A:B")

    now = datetime.now(WIB)
    bln = str(now.month).zfill(2)
    thn = now.year
    nama_bln = ["Januari","Februari","Maret","April","Mei","Juni",
                "Juli","Agustus","September","Oktober","November","Desember"][now.month-1]

    total_masuk    = sum_col(masuk_rows)
    total_keluar   = sum_col(keluar_rows)
    saldo          = total_masuk - total_keluar
    masuk_bln      = sum_bulan(masuk_rows,  bln, thn)
    keluar_bln     = sum_bulan(keluar_rows, bln, thn)
    net_bln        = masuk_bln - keluar_bln
    breakdown      = get_breakdown(keluar_rows, bln, thn)
    tren           = get_tren(masuk_rows, keluar_rows, now)
    
    # Budget
    budget = 0
    bln_thn = f"{bln}/{thn}"
    for r in budget_rows:
        if r and len(r) >= 2 and r[0] == bln_thn:
            try: budget = float(r[1])
            except: pass
    budget_sisa   = budget - keluar_bln if budget > 0 else 0
    budget_persen = (keluar_bln / budget * 100) if budget > 0 else 0

    # Last 10 transaksi
    all_tx = []
    for r in masuk_rows[1:]:
        if len(r) > 5 and r[1]:
            all_tx.append({"tgl": r[1], "waktu": r[2] if len(r)>2 else "", "ket": r[3], "nominal": float(r[5]), "tipe": "masuk"})
    for r in keluar_rows[1:]:
        if len(r) > 5 and r[1]:
            all_tx.append({"tgl": r[1], "waktu": r[2] if len(r)>2 else "", "ket": r[3], "nominal": float(r[5]), "tipe": "keluar"})
    all_tx.sort(key=lambda x: x["tgl"] + x["waktu"], reverse=True)
    last10 = all_tx[:10]

    requests = []

    # ── CLEAR & SETUP ──────────────────────────────────────────
    requests.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {"rowCount": 120, "columnCount": 12}},
        "fields": "gridProperties"
    }})
    requests.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 12},
        "properties": {"pixelSize": 130}, "fields": "pixelSize"
    }})
    # Col A narrow
    requests.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
        "properties": {"pixelSize": 20}, "fields": "pixelSize"
    }})

    # ── BACKGROUND SELURUH SHEET ───────────────────────────────
    requests.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 120, "startColumnIndex": 0, "endColumnIndex": 12},
        "cell": {"userEnteredFormat": {"backgroundColor": COLORS["light_gray"]}},
        "fields": "userEnteredFormat.backgroundColor"
    }})

    # ── HEADER ────────────────────────────────────────────────
    # Row height
    for r, h in [(0,12),(1,52),(2,28),(3,16)]:
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r, "endIndex": r+1},
            "properties": {"pixelSize": h}, "fields": "pixelSize"
        }})

    requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 1, "endColumnIndex": 11}, "mergeType": "MERGE_ALL"}})
    requests.append({"updateCells": {
        "range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 1, "endColumnIndex": 11},
        "rows": [{"values": [make_cell_data("💰  DASHBOARD KEUANGAN PRIBADI", fg=COLORS["white"], bg=COLORS["navy"], bold=True, size=18, align="CENTER")]}],
        "fields": "userEnteredValue,userEnteredFormat"
    }})

    requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 1, "endColumnIndex": 11}, "mergeType": "MERGE_ALL"}})
    update_ts = f"Update terakhir: {now.strftime('%d %B %Y, %H:%M')} WIB"
    requests.append({"updateCells": {
        "range": {"sheetId": sid, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 1, "endColumnIndex": 11},
        "rows": [{"values": [make_cell_data(update_ts, fg=COLORS["dark_gray"], bg=COLORS["dark_blue"], size=9, align="CENTER")]}],
        "fields": "userEnteredValue,userEnteredFormat"
    }})

    # ── SECTION HELPER ────────────────────────────────────────
    def section_header(row, title):
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": row, "endIndex": row+1},
            "properties": {"pixelSize": 32}, "fields": "pixelSize"
        }})
        requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": 1, "endColumnIndex": 11}, "mergeType": "MERGE_ALL"}})
        requests.append({"updateCells": {
            "range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": 1, "endColumnIndex": 11},
            "rows": [{"values": [make_cell_data(title, fg=COLORS["white"], bg=COLORS["dark_blue"], bold=True, size=11, align="LEFT")]}],
            "fields": "userEnteredValue,userEnteredFormat"
        }})

    def kartu(row, col, title, value, sub, bg, fg, col_span=3):
        for r in [row, row+1, row+2]:
            requests.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": r, "endIndex": r+1},
                "properties": {"pixelSize": 30 if r == row+1 else 26}, "fields": "pixelSize"
            }})
        # title
        requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": col, "endColumnIndex": col+col_span}, "mergeType": "MERGE_ALL"}})
        requests.append({"updateCells": {
            "range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": col, "endColumnIndex": col+col_span},
            "rows": [{"values": [make_cell_data(title, fg=COLORS["dark_gray"], bg=bg, bold=True, size=9, align="CENTER")]}],
            "fields": "userEnteredValue,userEnteredFormat"
        }})
        # value
        requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row+1, "endRowIndex": row+2, "startColumnIndex": col, "endColumnIndex": col+col_span}, "mergeType": "MERGE_ALL"}})
        requests.append({"updateCells": {
            "range": {"sheetId": sid, "startRowIndex": row+1, "endRowIndex": row+2, "startColumnIndex": col, "endColumnIndex": col+col_span},
            "rows": [{"values": [make_cell_data(value, fg=fg, bg=bg, bold=True, size=14, align="CENTER")]}],
            "fields": "userEnteredValue,userEnteredFormat"
        }})
        # sub
        requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row+2, "endRowIndex": row+3, "startColumnIndex": col, "endColumnIndex": col+col_span}, "mergeType": "MERGE_ALL"}})
        requests.append({"updateCells": {
            "range": {"sheetId": sid, "startRowIndex": row+2, "endRowIndex": row+3, "startColumnIndex": col, "endColumnIndex": col+col_span},
            "rows": [{"values": [make_cell_data(sub, fg=COLORS["dark_gray"], bg=bg, size=8, align="CENTER")]}],
            "fields": "userEnteredValue,userEnteredFormat"
        }})
        # border
        requests.append({"updateBorders": {
            "range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+3, "startColumnIndex": col, "endColumnIndex": col+col_span},
            "top":    {"style": "SOLID_MEDIUM", "color": fg},
            "bottom": {"style": "SOLID_MEDIUM", "color": fg},
            "left":   {"style": "SOLID_MEDIUM", "color": fg},
            "right":  {"style": "SOLID_MEDIUM", "color": fg},
        }})

    # ── SECTION 1: BULAN INI ──────────────────────────────────
    section_header(4, f"📅  RINGKASAN {nama_bln.upper()} {thn}")
    net_bg  = COLORS["blue_bg"]  if net_bln >= 0 else COLORS["red_bg"]
    net_fg  = COLORS["blue_txt"] if net_bln >= 0 else COLORS["red_txt"]
    net_sub = "✅ Surplus" if net_bln >= 0 else "⚠️ Defisit"
    kartu(5, 1, "💰 PEMASUKAN BULAN INI", format_rp(masuk_bln), f"{sum(1 for r in masuk_rows[1:] if len(r)>1 and r[1] and str(r[1])[3:5]==bln)} transaksi", COLORS["green_bg"], COLORS["green_txt"])
    kartu(5, 4, "💸 PENGELUARAN BULAN INI", format_rp(keluar_bln), f"{sum(1 for r in keluar_rows[1:] if len(r)>1 and r[1] and str(r[1])[3:5]==bln)} transaksi", COLORS["red_bg"], COLORS["red_txt"])
    kartu(5, 7, "📊 NET BULAN INI", format_rp(net_bln), net_sub, net_bg, net_fg)

    # Budget kartu
    if budget > 0:
        bar = "█" * int(budget_persen / 10) + "░" * (10 - int(budget_persen / 10))
        bgt_bg  = COLORS["yellow_bg"]
        bgt_fg  = COLORS["yellow_txt"] if budget_persen < 80 else COLORS["red_txt"]
        kartu(5, 10, "🎯 BUDGET", format_rp(budget_sisa), f"{bar} {budget_persen:.0f}%", bgt_bg, bgt_fg, col_span=1)

    # ── SECTION 2: ALL TIME ───────────────────────────────────
    section_header(9, "🏦  TOTAL KESELURUHAN")
    saldo_bg  = COLORS["blue_bg"]  if saldo >= 0 else COLORS["red_bg"]
    saldo_fg  = COLORS["blue_txt"] if saldo >= 0 else COLORS["red_txt"]
    saldo_sub = "✅ Positif" if saldo >= 0 else "⚠️ Negatif"
    kartu(10, 1, "💰 TOTAL PEMASUKAN", format_rp(total_masuk), "All time", COLORS["green_bg"], COLORS["green_txt"])
    kartu(10, 4, "💸 TOTAL PENGELUARAN", format_rp(total_keluar), "All time", COLORS["red_bg"], COLORS["red_txt"])
    kartu(10, 7, "💼 SALDO", format_rp(saldo), saldo_sub, saldo_bg, saldo_fg)

    # ── SECTION 3: TREN 6 BULAN ───────────────────────────────
    section_header(14, "📈  TREN 6 BULAN TERAKHIR")
    # Header tabel
    requests.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 15, "endIndex": 16},
        "properties": {"pixelSize": 26}, "fields": "pixelSize"
    }})
    headers_tren = ["Bulan", "Pemasukan", "Pengeluaran", "Net", "Status"]
    col_spans_tren = [2, 2, 2, 2, 2]
    col_start = 1
    for i, (h, cs) in enumerate(zip(headers_tren, col_spans_tren)):
        requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": 15, "endRowIndex": 16, "startColumnIndex": col_start, "endColumnIndex": col_start+cs}, "mergeType": "MERGE_ALL"}})
        requests.append({"updateCells": {
            "range": {"sheetId": sid, "startRowIndex": 15, "endRowIndex": 16, "startColumnIndex": col_start, "endColumnIndex": col_start+cs},
            "rows": [{"values": [make_cell_data(h, fg=COLORS["white"], bg=COLORS["navy"], bold=True, size=10, align="CENTER")]}],
            "fields": "userEnteredValue,userEnteredFormat"
        }})
        col_start += cs

    for i, t in enumerate(tren):
        row = 16 + i
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": row, "endIndex": row+1},
            "properties": {"pixelSize": 24}, "fields": "pixelSize"
        }})
        bg = COLORS["white"] if i % 2 == 0 else COLORS["light_gray"]
        net_c = COLORS["green_txt"] if t["net"] >= 0 else COLORS["red_txt"]
        status = "✅ Surplus" if t["net"] >= 0 else "⚠️ Defisit"
        vals = [t["label"], format_rp(t["masuk"]), format_rp(t["keluar"]), format_rp(t["net"]), status]
        col_start = 1
        for j, (v, cs) in enumerate(zip(vals, col_spans_tren)):
            fg = net_c if j == 3 else COLORS["text_dark"]
            bld = j == 3
            requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": col_start, "endColumnIndex": col_start+cs}, "mergeType": "MERGE_ALL"}})
            requests.append({"updateCells": {
                "range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": col_start, "endColumnIndex": col_start+cs},
                "rows": [{"values": [make_cell_data(v, fg=fg, bg=bg, bold=bld, size=10, align="CENTER")]}],
                "fields": "userEnteredValue,userEnteredFormat"
            }})
            col_start += cs

    # Border tabel tren
    requests.append({"updateBorders": {
        "range": {"sheetId": sid, "startRowIndex": 15, "endRowIndex": 16+len(tren), "startColumnIndex": 1, "endColumnIndex": 11},
        "top":    {"style": "SOLID", "color": COLORS["mid_gray"]},
        "bottom": {"style": "SOLID", "color": COLORS["mid_gray"]},
        "left":   {"style": "SOLID", "color": COLORS["mid_gray"]},
        "right":  {"style": "SOLID", "color": COLORS["mid_gray"]},
        "innerHorizontal": {"style": "SOLID", "color": COLORS["mid_gray"]},
        "innerVertical":   {"style": "SOLID", "color": COLORS["mid_gray"]},
    }})

    # ── SECTION 4: KATEGORI ───────────────────────────────────
    sec4_row = 23
    section_header(sec4_row, f"📂  PENGELUARAN PER KATEGORI — {nama_bln.upper()} {thn}")
    if breakdown:
        sorted_bd = sorted(breakdown.items(), key=lambda x: -x[1])
        total_bd  = sum(v for _, v in sorted_bd)
        # Header
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": sec4_row+1, "endIndex": sec4_row+2},
            "properties": {"pixelSize": 26}, "fields": "pixelSize"
        }})
        for ci, (h, cs, col_s) in enumerate(zip(["Kategori","Jumlah","Persentase","Bar"], [2,2,1,6], [1,3,5,6])):
            requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": sec4_row+1, "endRowIndex": sec4_row+2, "startColumnIndex": col_s, "endColumnIndex": col_s+cs}, "mergeType": "MERGE_ALL"}})
            requests.append({"updateCells": {
                "range": {"sheetId": sid, "startRowIndex": sec4_row+1, "endRowIndex": sec4_row+2, "startColumnIndex": col_s, "endColumnIndex": col_s+cs},
                "rows": [{"values": [make_cell_data(h, fg=COLORS["white"], bg=COLORS["navy"], bold=True, size=10, align="CENTER")]}],
                "fields": "userEnteredValue,userEnteredFormat"
            }})
        for i, (kat, total) in enumerate(sorted_bd):
            row = sec4_row + 2 + i
            pct = total / total_bd * 100 if total_bd > 0 else 0
            bar_len = int(pct / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            bg = COLORS["white"] if i % 2 == 0 else COLORS["light_gray"]
            requests.append({"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": row, "endIndex": row+1},
                "properties": {"pixelSize": 24}, "fields": "pixelSize"
            }})
            for v, cs, col_s in zip(
                [kat.capitalize(), format_rp(total), f"{pct:.1f}%", bar],
                [2, 2, 1, 6], [1, 3, 5, 6]
            ):
                requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": col_s, "endColumnIndex": col_s+cs}, "mergeType": "MERGE_ALL"}})
                requests.append({"updateCells": {
                    "range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": col_s, "endColumnIndex": col_s+cs},
                    "rows": [{"values": [make_cell_data(v, fg=COLORS["red_txt"] if col_s==3 else COLORS["text_dark"], bg=bg, size=10, align="CENTER")]}],
                    "fields": "userEnteredValue,userEnteredFormat"
                }})
        last_bd_row = sec4_row + 2 + len(sorted_bd)
        requests.append({"updateBorders": {
            "range": {"sheetId": sid, "startRowIndex": sec4_row+1, "endRowIndex": last_bd_row, "startColumnIndex": 1, "endColumnIndex": 11},
            "top": {"style":"SOLID","color":COLORS["mid_gray"]}, "bottom": {"style":"SOLID","color":COLORS["mid_gray"]},
            "left": {"style":"SOLID","color":COLORS["mid_gray"]}, "right": {"style":"SOLID","color":COLORS["mid_gray"]},
            "innerHorizontal": {"style":"SOLID","color":COLORS["mid_gray"]}, "innerVertical": {"style":"SOLID","color":COLORS["mid_gray"]},
        }})
        next_row = last_bd_row + 2
    else:
        next_row = sec4_row + 3

    # ── SECTION 5: TRANSAKSI TERAKHIR ─────────────────────────
    section_header(next_row, "🕐  10 TRANSAKSI TERAKHIR")
    headers_tx = ["Tanggal", "Waktu", "Keterangan", "Nominal", "Tipe"]
    col_spans_tx = [1, 1, 4, 2, 2]
    col_start = 1
    requests.append({"updateDimensionProperties": {
        "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": next_row+1, "endIndex": next_row+2},
        "properties": {"pixelSize": 26}, "fields": "pixelSize"
    }})
    for h, cs in zip(headers_tx, col_spans_tx):
        requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": next_row+1, "endRowIndex": next_row+2, "startColumnIndex": col_start, "endColumnIndex": col_start+cs}, "mergeType": "MERGE_ALL"}})
        requests.append({"updateCells": {
            "range": {"sheetId": sid, "startRowIndex": next_row+1, "endRowIndex": next_row+2, "startColumnIndex": col_start, "endColumnIndex": col_start+cs},
            "rows": [{"values": [make_cell_data(h, fg=COLORS["white"], bg=COLORS["navy"], bold=True, size=10, align="CENTER")]}],
            "fields": "userEnteredValue,userEnteredFormat"
        }})
        col_start += cs

    for i, tx in enumerate(last10):
        row = next_row + 2 + i
        requests.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": row, "endIndex": row+1},
            "properties": {"pixelSize": 24}, "fields": "pixelSize"
        }})
        bg = COLORS["white"] if i % 2 == 0 else COLORS["light_gray"]
        tipe_str = "💰 Masuk" if tx["tipe"] == "masuk" else "💸 Keluar"
        tipe_fg  = COLORS["green_txt"] if tx["tipe"] == "masuk" else COLORS["red_txt"]
        vals = [tx["tgl"], tx["waktu"], tx["ket"], format_rp(tx["nominal"]), tipe_str]
        col_start = 1
        for v, cs, is_tipe in zip(vals, col_spans_tx, [False,False,False,False,True]):
            fg = tipe_fg if is_tipe else COLORS["text_dark"]
            requests.append({"mergeCells": {"range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": col_start, "endColumnIndex": col_start+cs}, "mergeType": "MERGE_ALL"}})
            requests.append({"updateCells": {
                "range": {"sheetId": sid, "startRowIndex": row, "endRowIndex": row+1, "startColumnIndex": col_start, "endColumnIndex": col_start+cs},
                "rows": [{"values": [make_cell_data(v, fg=fg, bg=bg, bold=is_tipe, size=10, align="CENTER")]}],
                "fields": "userEnteredValue,userEnteredFormat"
            }})
            col_start += cs

    requests.append({"updateBorders": {
        "range": {"sheetId": sid, "startRowIndex": next_row+1, "endRowIndex": next_row+2+len(last10), "startColumnIndex": 1, "endColumnIndex": 11},
        "top": {"style":"SOLID","color":COLORS["mid_gray"]}, "bottom": {"style":"SOLID","color":COLORS["mid_gray"]},
        "left": {"style":"SOLID","color":COLORS["mid_gray"]}, "right": {"style":"SOLID","color":COLORS["mid_gray"]},
        "innerHorizontal": {"style":"SOLID","color":COLORS["mid_gray"]}, "innerVertical": {"style":"SOLID","color":COLORS["mid_gray"]},
    }})

    # ── EXECUTE ───────────────────────────────────────────────
    # Bagi requests jadi batch kecil
    batch_size = 50
    for i in range(0, len(requests), batch_size):
        batch = requests[i:i+batch_size]
        svc.spreadsheets().batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": batch}
        ).execute()

    print("Dashboard updated!")
