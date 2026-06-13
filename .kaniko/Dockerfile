# ---- 1. Builder Stage (สำหรับติดตั้ง Dependencies ด้วย uv เพื่อความเร็ว) ----
    FROM python:3.11-slim AS builder

    # ดึงโปรแกรม uv เข้ามาช่วยติดตั้งแพ็กเกจ
    COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
    
    WORKDIR /app
    
    # ก๊อปปี้แค่ pyproject.toml มาก่อน (เพื่อใช้ประโยชน์จาก Docker Cache)
    COPY pyproject.toml ./
    
    # สั่งให้ uv ติดตั้งแพ็กเกจทั้งหมด (จะสร้างโฟลเดอร์ .venv ให้อัตโนมัติ)
    RUN uv sync --no-dev --no-install-project
    
    # ก๊อปปี้โค้ดโปรเจกต์ทั้งหมดตามเข้ามา
    COPY . .
    
    
    # ---- 2. Runtime Stage (อิมเมจตัวจริงที่เบาหวิว พร้อมใช้งาน) ----
    FROM python:3.11-slim

    WORKDIR /app

    # WeasyPrint runtime deps — Pango drives Thai/CJK text shaping; Cairo,
    # GLib, Fontconfig come in transitively via libpango.
    RUN apt-get update \
        && apt-get install -y --no-install-recommends \
            libpango-1.0-0 \
            libpangoft2-1.0-0 \
        && rm -rf /var/lib/apt/lists/*

    # ก๊อปปี้โฟลเดอร์ .venv และโค้ดแอป มาจากขั้นตอน Builder
    COPY --from=builder /app/.venv /app/.venv
    COPY --from=builder /app /app
    
    # บังคับให้ระบบใช้ Python และ Library จากใน .venv
    ENV PATH="/app/.venv/bin:$PATH"
    # บังคับให้แสดง Log ทันที (สำคัญมากเวลาดู Log ใน Kubernetes)
    ENV PYTHONUNBUFFERED=1
    
    # FastAPI / Uvicorn มักจะใช้พอร์ต 8000
    EXPOSE 8000
    
    # รัน FastAPI ด้วย Uvicorn
    CMD ["uvicorn", "main:app", \
         "--host", "0.0.0.0", \
         "--port", "8000", \
         "--workers", "2", \
         "--proxy-headers", \
         "--forwarded-allow-ips", "*"]

         