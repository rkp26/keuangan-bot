# Keuangan Bot v2 - Python + Railway

## Environment Variables yang perlu diisi di Railway:

| Variable | Isi |
|---|---|
| BOT_TOKEN | Token dari @BotFather |
| SHEET_ID | ID Google Sheet |
| GOOGLE_CREDENTIALS | JSON service account (lihat langkah 3) |

## Langkah Setup:

### 1. Upload ke GitHub
- Buat repo baru di github.com
- Upload semua file ini

### 2. Google Service Account
- Buka: console.cloud.google.com
- Buat project baru
- Enable Google Sheets API
- Buat Service Account → download JSON credentials
- Share Google Sheet ke email service account (Editor)

### 3. Deploy ke Railway
- Buka railway.app → New Project → Deploy from GitHub
- Pilih repo ini
- Tambah environment variables
- Deploy!
