import os
import base64
import anthropic

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

def baca_struk(image_bytes):
    """Baca struk dari foto, return dict {tipe, nominal, keterangan, kategori}"""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    
    prompt = """Kamu adalah asisten keuangan. Analisa foto/struk/nota ini dan ekstrak informasi transaksi.

Tentukan:
1. Tipe: "masuk" (pemasukan/pendapatan) atau "keluar" (pengeluaran/pembelian)
2. Nominal: total amount dalam angka (tanpa titik/koma, contoh: 50000)
3. Keterangan: deskripsi singkat transaksi (max 30 karakter)
4. Kategori: salah satu dari [makan, transport, tagihan, belanja, hiburan, kesehatan, laundry, lainnya]

Jawab HANYA dalam format JSON ini, tanpa penjelasan lain:
{"tipe": "keluar", "nominal": 50000, "keterangan": "Makan siang", "kategori": "makan"}

Jika gambar bukan struk/nota keuangan, jawab:
{"error": "Bukan struk keuangan"}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_b64
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }]
    )
    
    import json
    text = response.content[0].text.strip()
    # Bersihkan kalau ada markdown
    text = text.replace("```json", "").replace("```", "").strip()
    result = json.loads(text)
    return result

