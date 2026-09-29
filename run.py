"""Titik masuk untuk menjalankan aplikasi di laptop: python run.py"""

from app import create_app

# Buat aplikasi memakai environment dari APP_ENV di .env
app = create_app()

if __name__ == "__main__":
    # Jalankan server lokal, hanya bisa diakses dari laptop sendiri (127.0.0.1)
    app.run(host="127.0.0.1", port=5000)