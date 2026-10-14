# EduSelf Teacher — AWS EC2 Joylashtirish Arxitekturasi (DEPLOYMENT_ARCHITECTURE.md)

**Hujjat versiyasi:** 1.0.0  
**Sana:** 14-oktabr 2026  
**Holati:** Approved Production Deployment Architecture  
**Bulut infratuzilmasi:** Amazon Web Services (AWS) — EC2, EBS, VPC, EIP, S3 / Cloudflare R2  
**Asosiy hujjatlar:** [.docs/PRD.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/PRD.md), [.docs/SRS.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/SRS.md), [.docs/Architecture.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/Architecture.md) va [.docs/ADR.md](file:///c:/Users/Asus/Desktop/teacher-eduself-mcp/.docs/ADR.md)

---

## 1. Kirish va Joylashtirish Maqsadlari

Ushbu hujjat **EduSelf Teacher** platformasini **AWS EC2 (Amazon Elastic Compute Cloud)** virtual serverlarida barqaror, yuqori tezlikli va xavfsiz ishga tushirish (production deployment) uchun to'liq texnik qo'llanmadir.

### 1.1 Asosiy Infratuzilma Maqsadlari
- **Yuklama standarti:** Bitta EC2 serverida bir vaqtning o'zida kamida 200 ta faol o'quvchi va 50 ta parallel jonli sessiyaga (10,000 parallel WebSocket ulanishi) xizmat ko'rsatish.
- **Kechikish (Latency SLA):** O'quvchi javob yuborganida tasdiq olish vaqti (ACK) p95 < 300ms.
- **Mavjudlik (Availability):** 99.5% uptime.
- **Xarajat samaradorligi:** AWS Graviton3 (ARM64) arxitekturasi orqali hisoblash xarajatlarini 20-30% ga tejash.

---

## 2. AWS Bulut Infratuzilmasi va Tarmoq Xaritasi (VPC & Security)

Tizim AWS Frankfurt (`eu-central-1`) yoki Stokgolm (`eu-north-1`) mintaqasida joylashtiriladi (O'zbekistondan past kechikish uchun).

```mermaid
flowchart TB
    subgraph Internet["Tashqi Internet"]
        Users["O'qituvchilar va O'quvchilar"]
        Chatbots["Claude Desktop / ChatGPT (MCP)"]
        CF["Cloudflare DNS & WAF (Proxy Enabled, TLS 1.3)"]
    end

    subgraph AWSCloud["AWS Mintaqasi: eu-central-1 (Frankfurt)"]
        EIP["AWS Elastic IP (Statik Public IP)"]
        IGW["Internet Gateway (IGW)"]

        subgraph VPC["EduSelf VPC (10.0.0.0/16)"]
            subgraph PublicSubnet["Public Subnet (10.0.1.0/24)"]
                subgraph SecurityGroup["EC2 Security Group (sg-eduself-prod)"]
                    direction TB
                    Inbound["KIRUVCHI TRAFIK (Inbound):<br>• Port 80: HTTP (-> HTTPS redirect)<br>• Port 443: HTTPS / WSS / MCP SSE<br>• Port 22: Yopiq! (SSM orqali kiriladi)"]
                    Outbound["CHIQUVCHI TRAFIK (Outbound):<br>• 0.0.0.0/0: Barcha portlar ochiq (AI API'lar, S3)"]
                end

                subgraph EC2Server["AWS EC2 Production Server (t4g.xlarge)<br>OS: Ubuntu 24.04 LTS (ARM64 Graviton3, 4 vCPU, 16GB RAM)"]
                    SSM["AWS SSM Agent (IAM Role)"]
                    DockerDaemon["Docker Engine 27.x & Docker Compose v2"]
                end
            end
        end

        subgraph StoragePersistence["Doimiy Ma'lumotlar Saqlash"]
            EBSVolume["AWS EBS gp3 Volume (100GB, 3000 IOPS)<br>Mount nuqtasi: /data"]
            DLMSnapshots["AWS Data Lifecycle Manager (DLM)<br>Kunlik avtomatik snapshotlar (7 kun saqlash)"]
            S3Bucket["Cloudflare R2 / AWS S3<br>(Media fayllar va PDF hisobotlar)"]
        end
    end

    Users --> CF
    Chatbots --> CF
    CF --> EIP
    EIP --> IGW
    IGW --> Inbound
    Inbound --> EC2Server
    EC2Server --> EBSVolume
    EBSVolume -.-> DLMSnapshots
    EC2Server --> S3Bucket
```

### 2.1 Xavfsizlik Qoidalari (Security Group: `sg-eduself-prod`)
| Turi | Protokol | Port oralig'i | Manba (Source) | Tavsif |
|---|---|---|---|---|
| **Inbound** | TCP | `80` | `0.0.0.0/0` | HTTP trafigi (Nginx darhol 443 HTTPS ga yo'naltiradi). |
| **Inbound** | TCP | `443` | `0.0.0.0/0` | HTTPS, Secure WebSockets (`wss://`) va MCP SSE. |
| **Inbound** | TCP | `22` (SSH) | **HECH KIMGA OCHILMAYDI** | Port 22 xavfsizlik uchun butunlay yopiq. Kirish faqat AWS SSM orqali. |
| **Outbound**| Barchasi | Barcha portlar | `0.0.0.0/0` | OpenAI, Gemini, Claude, S3 va OS paketlariga ulanish. |

---

## 3. EC2 Server Parametrlari va Muhitlar (Environments)

| Muhit | EC2 Instance Turi | vCPU | RAM | Disk (EBS gp3) | Operatsion Tizim | Oylik Taxminiy Narx |
|---|---|---|---|---|---|---|
| **Production** | **`t4g.xlarge`** (ARM Graviton3) | 4 vCPU | 16 GB | 100 GB (3000 IOPS, 125 MB/s) | Ubuntu 24.04 LTS | ~$97 / oy |
| **Staging / Dev**| **`t4g.medium`** (ARM Graviton3) | 2 vCPU | 4 GB | 40 GB (3000 IOPS) | Ubuntu 24.04 LTS | ~$24 / oy |

> [!TIP]
> **Nima uchun AWS Graviton3 (t4g.xlarge)?**
> Graviton3 protsessorlari Intel/AMD (t3.xlarge) ekvivalentiga qaraganda **20% arzonroq** va Python 3.12 / FastAPI asinxron operatsiyalarida **25% tezroq** ishlaydi.

---

## 4. Konteynerlashtirish va Docker Compose Arxitekturasi

Barcha xizmatlar EC2 ichida bitta izolyatsiyalangan Docker tarmog'ida (`eduself-net`) ishlaydi.

```mermaid
flowchart TD
    subgraph HostSystem["AWS EC2 Host (/data EBS gp3 ga ulangan)"]
        NginxPort["Host Ports: 80, 443"]

        subgraph DockerNetwork["Bridge Tarmoq: eduself-net"]
            Nginx["1. Nginx Reverse Proxy\n(alpine, SSL termination, WSS/SSE proxy)"]
            FastAPI["2. FastAPI Core & WS Gateway\n(Gunicorn 4 x Uvicorn, port 8000)"]
            MCP["3. Public Python MCP Server\n(SSE transport, port 8001)"]
            Worker["4. Celery Background Worker\n(Concurrency 4, batch writes)"]
            Beat["5. Celery Beat Scheduler\n(Periodic DB partitions & cleanup)"]
            Redis["6. Redis 7.2 Cache & Streams\n(AOF Appendonly, port 6379)"]
            Postgres["7. PostgreSQL 16 Partitioned DB\n(port 5432)"]
        end

        subgraph EBSDirectories["EBS Disk Papkalari (/data)"]
            DirPG["/data/postgres (Baza jadvallari)"]
            DirRedis["/data/redis (AOF fayllari)"]
            DirLogs["/data/logs (Nginx & App loglari)"]
            DirCert["/data/certbot (SSL sertifikatlar)"]
        end
    end

    NginxPort --> Nginx
    Nginx -->|Proxy HTTP/WSS| FastAPI
    Nginx -->|Proxy SSE| MCP
    FastAPI --> Redis
    FastAPI --> Postgres
    FastAPI --> Worker
    Worker --> Postgres
    Worker --> Redis
    Beat --> Redis

    Postgres --> DirPG
    Redis --> DirRedis
    Nginx --> DirLogs
    Nginx --> DirCert
```

### 4.1 Ishlab chiqarish `docker-compose.prod.yml` Fayli

```yaml
version: '3.9'

networks:
  eduself-net:
    driver: bridge

volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/postgres
  redis_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/redis
  certbot_etc:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /data/certbot/etc

services:
  nginx:
    image: nginx:1.27-alpine
    container_name: eduself-nginx
    restart: always
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - certbot_etc:/etc/letsencrypt:ro
      - /data/logs/nginx:/var/log/nginx
    depends_on:
      - fastapi-backend
      - mcp-server
    networks:
      - eduself-net
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1024M

  fastapi-backend:
    image: ${AWS_ECR_REGISTRY}/eduself-backend:${IMAGE_TAG:-latest}
    container_name: eduself-backend
    restart: always
    command: gunicorn src.presentation.api.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000 --timeout 120 --keep-alive 5
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - MASTER_ENCRYPTION_KEY=${MASTER_ENCRYPTION_KEY}
      - S3_ENDPOINT_URL=${S3_ENDPOINT_URL}
      - S3_BUCKET_NAME=${S3_BUCKET_NAME}
      - S3_ACCESS_KEY_ID=${S3_ACCESS_KEY_ID}
      - S3_SECRET_ACCESS_KEY=${S3_SECRET_ACCESS_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - eduself-net
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4096M

  mcp-server:
    image: ${AWS_ECR_REGISTRY}/eduself-mcp:${IMAGE_TAG:-latest}
    container_name: eduself-mcp
    restart: always
    command: python -m src.presentation.mcp.server --transport sse --port 8001
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - MCP_OAUTH_PUBLIC_KEY=${MCP_OAUTH_PUBLIC_KEY}
    depends_on:
      - postgres
      - redis
    networks:
      - eduself-net
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 2048M

  celery-worker:
    image: ${AWS_ECR_REGISTRY}/eduself-backend:${IMAGE_TAG:-latest}
    container_name: eduself-celery-worker
    restart: always
    command: celery -A src.infrastructure.tasks.celery_app worker --loglevel=info --concurrency=4
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
      - S3_ENDPOINT_URL=${S3_ENDPOINT_URL}
      - S3_BUCKET_NAME=${S3_BUCKET_NAME}
      - S3_ACCESS_KEY_ID=${S3_ACCESS_KEY_ID}
      - S3_SECRET_ACCESS_KEY=${S3_SECRET_ACCESS_KEY}
    depends_on:
      - postgres
      - redis
    networks:
      - eduself-net
    deploy:
      resources:
        limits:
          cpus: '1.5'
          memory: 3072M

  celery-beat:
    image: ${AWS_ECR_REGISTRY}/eduself-backend:${IMAGE_TAG:-latest}
    container_name: eduself-celery-beat
    restart: always
    command: celery -A src.infrastructure.tasks.celery_app beat --loglevel=info
    environment:
      - ENVIRONMENT=production
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis
    networks:
      - eduself-net
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M

  redis:
    image: redis:7.2-alpine
    container_name: eduself-redis
    restart: always
    command: ["redis-server", "--appendonly", "yes", "--maxmemory", "3gb", "--maxmemory-policy", "volatile-lru"]
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
    networks:
      - eduself-net
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 3500M

  postgres:
    image: postgres:16-alpine
    container_name: eduself-postgres
    restart: always
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    command: >
      postgres -c shared_buffers=2GB
               -c effective_cache_size=6GB
               -c maintenance_work_mem=512MB
               -c checkpoint_completion_target=0.9
               -c wal_buffers=16MB
               -c default_statistics_target=100
               -c random_page_cost=1.1
               -c effective_io_concurrency=200
               -c work_mem=10MB
               -c max_connections=200
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - eduself-net
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4096M
```

---

## 5. Nginx Reverse Proxy va SSL Sertifikatlar Quvuri

Nginx kiruvchi barcha trafigi uchun yagona xavfsiz darvoza bo'lib xizmat qiladi.

### 5.1 Nginx Server Konfiguratsiyasi (`nginx/conf.d/eduself.conf`)

```nginx
# HTTP -> HTTPS Redirect
server {
    listen 80;
    server_name api.eduself.uz mcp.eduself.uz;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

# Asosiy API va WebSocket Serveri
server {
    listen 443 ssl http2;
    server_name api.eduself.uz;

    ssl_certificate /etc/letsencrypt/live/api.eduself.uz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.eduself.uz/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Gzip siqish
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;

    # 1. REST API Marshruti
    location /api/ {
        proxy_pass http://fastapi-backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 2. WebSocket Real-Time Marshruti (MUHIM!)
    location /ws/ {
        proxy_pass http://fastapi-backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 3600s; # 1 soatlik doimiy dars sessiyasi
        proxy_send_timeout 3600s;
    }
}

# Public MCP Serveri (Server-Sent Events)
server {
    listen 443 ssl http2;
    server_name mcp.eduself.uz;

    ssl_certificate /etc/letsencrypt/live/api.eduself.uz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.eduself.uz/privkey.pem;

    location / {
        proxy_pass http://mcp-server:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # SSE (Server-Sent Events) uchun keshni butunlay o'chirish:
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
        chunked_transfer_encoding off;
    }
}
```

---

## 6. Doimiy Ma'lumotlar Saqlash va Zaxiralash (Persistence & Backups)

```mermaid
flowchart LR
    subgraph DailyOps["Kunlik Avtomatik Zaxira (Cron har kecha 03:00 da)"]
        Cron["Cron Job (/opt/scripts/backup.sh)"]
        Dump["pg_dump -Fc eduself > backup_YYYY_MM_DD.dump"]
        S3Upload["AWS S3 / Cloudflare R2 Omboriga yuklash"]
    end

    subgraph AWSOps["AWS Bulut Darajasidagi Zaxira (DLM)"]
        AWS_DLM["AWS Data Lifecycle Manager (DLM)"]
        EBS_Snap["EBS gp3 Disk Snapshot (Avtomatik 7 kun saqlanadi)"]
    end

    Cron --> Dump --> S3Upload
    AWS_DLM --> EBS_Snap
```

1. **EBS gp3 Mount Nuqtasi:** EC2 serverida `/data` katalogi alohida 100GB EBS hajmiga biriktirilgan. Server qayta yaratilsa ham ma'lumotlar diskda daxlsiz qoladi.
2. **PostgreSQL Dump Skripti:** Har kecha soat 03:00 da siqilgan `pg_dump` olinadi va shifrlangan holda S3 omboriga yuklanadi (30 kun saqlanadi).
3. **AWS DLM Snapshotlar:** AWS konsolida har kecha butun EBS diskining oniy nusxasi (Snapshot) olinadi. Falokat yuz berganda 10 daqiqada yangi EC2 ga disk ulanadi.

---

## 7. Avtomatlashtirilgan CI/CD Quvuri (GitHub Actions -> AWS EC2)

Dasturchi kodni `main` branchga push qilganda to'liq avtomatlashtirilgan deploy amalga oshadi:

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Dasturchi
    participant GH as GitHub Actions Runner
    participant ECR as Amazon ECR / GHCR
    participant EC2 as AWS EC2 Server (SSM / SSH)

    Dev->>GH: git push origin main
    critical 1. Sinov va Tekshiruv
        GH->>GH: Run Linter (Ruff, MyPy)
        GH->>GH: Run Pytest (Unit & Integration tests)
    end

    critical 2. Docker Image Yig'ish
        GH->>GH: Docker Buildx (ARM64 & Linux)
        GH->>ECR: Docker Push eduself-backend:sha-xyz
        GH->>ECR: Docker Push eduself-mcp:sha-xyz
    end

    critical 3. Zero-Downtime Deploy
        GH->>EC2: AWS SSM Command: deploy.sh sha-xyz
        Note over EC2: docker compose pull
        Note over EC2: docker compose up -d --remove-orphans
        Note over EC2: docker exec eduself-backend alembic upgrade head
    end

    EC2-->>GH: Deploy Muvaffaqiyatli!
    GH-->>Dev: Bildirishnoma (Telegram / Slack)
```

### 7.1 GitHub Actions Workflow Fayli (`.github/workflows/deploy.yml`)

```yaml
name: Production Deploy to AWS EC2

on:
  push:
    branches: [ main ]

jobs:
  test-and-build:
    runs-on: ubuntu-latest
    steps:
      - name: Kodni yuklab olish
        uses: actions/checkout@v4

      - name: Python 3.12 ni o'rnatish
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Qaramliklarni o'rnatish va Testlarni ishga tushirish
        run: |
          pip install -r requirements-dev.txt
          pytest tests/ --cov=src

      - name: AWS hisobiga ulanish
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: eu-central-1

      - name: Amazon ECR ga kirish
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Docker Image'larni yig'ish va ECR ga yuklash
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker buildx build --platform linux/arm64 -t $ECR_REGISTRY/eduself-backend:$IMAGE_TAG -t $ECR_REGISTRY/eduself-backend:latest -f Dockerfile.backend --push .
          docker buildx build --platform linux/arm64 -t $ECR_REGISTRY/eduself-mcp:$IMAGE_TAG -t $ECR_REGISTRY/eduself-mcp:latest -f Dockerfile.mcp --push .

      - name: AWS EC2 ga SSM orqali Deploy qilish
        run: |
          aws ssm send-command \
            --document-name "AWS-RunShellScript" \
            --targets "Key=instanceids,Values=${{ secrets.EC2_INSTANCE_ID }}" \
            --parameters 'commands=[
              "cd /opt/eduself",
              "export IMAGE_TAG='${{ github.sha }}'",
              "docker compose -f docker-compose.prod.yml pull",
              "docker compose -f docker-compose.prod.yml up -d",
              "docker exec eduself-backend alembic upgrade head",
              "docker image prune -af"
            ]' \
            --comment "Automated deployment from GitHub Actions"
```

---

## 8. Tizimli Boshqaruv (Systemd) va Auto-Heal

Server kutilmaganda qayta yuklanganda (reboot) barcha konteynerlar avtomatik tartib bilan ko'tarilishi uchun `systemd` xizmati o'rnatiladi.

### 8.1 Systemd Fayli (`/etc/systemd/system/eduself.service`)
```ini
[Unit]
Description=EduSelf Teacher Docker Compose Application
Requires=docker.service
After=docker.service network.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/eduself
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

---

## 9. Monitoring, Loglar va Operatsion Xizmat (SRE)

1. **Docker Loglarini Cheklash (`/etc/docker/daemon.json`):**
   ```json
   {
     "log-driver": "json-file",
     "log-opts": {
       "max-size": "50m",
       "max-file": "5"
     }
   }
   ```
   Bu sozlama diskning log fayllar bilan to'lib qolishini (Disk Full) 100% oldini oladi.
2. **Kuzatuv (Monitoring):**
   - **Prometheus Node Exporter:** EC2 ning CPU, RAM va disk qoldig'ini o'lchaydi.
   - **CloudWatch Alarms:** CPU yuklamasi 85% dan oshganda yoki disk 80% to'lganda administrator telefoniga Telegram/SMS ogohlantirish yuboriladi.
3. **Vertikal Miqyoslash (Scale Up Yo'riqnomasi):**
   - Agar o'quvchilar soni 500 dan oshsa, EC2 instance'ni `t4g.xlarge` dan `t4g.2xlarge` (8 vCPU, 32GB RAM) ga almashtirish atigi **3 daqiqa** vaqt oladi:
     1. AWS Console'da `Stop Instance`.
     2. `Change Instance Type` -> `t4g.2xlarge`.
     3. `Start Instance`. (EIP va EBS avtomatik qayta ulanadi!).

---

## 10. Ishga Tushirish Cheklisti (Go-Live Checklist)

- [ ] **AWS VPC va EIP:** Statik IP olindi va Cloudflare DNS'ga `A` yozuvi sifatida bog'landi.
- [ ] **Security Group:** Faqat 80 va 443 portlar ochiq, SSH 22-port butunlay yopiq, SSM tekshirildi.
- [ ] **EBS gp3 Diski:** `/data` katalogiga ulandi va `fstab` ga avtomatik mount sifatida kiritildi.
- [ ] **SSL Sertifikat:** Let's Encrypt sertifikati olindi va Nginx'da HTTPS to'g'ri ishlamoqda.
- [ ] **WebSocket Test:** Brauzerdan `wss://api.eduself.uz/ws/` ga ulanish va ping-pong muvaffaqiyatli o'tdi.
- [ ] **MCP SSE Test:** Claude Desktop orqali `https://mcp.eduself.uz` ga so'rov yuborib ko'rildi.
- [ ] **Ma'lumotlar Bazasi Migratsiyasi:** `alembic upgrade head` buyrug'i bajarildi va barcha jadvallar hosil bo'ldi.
- [ ] **Zaxira Skripti:** `backup.sh` cron jobga o'rnatildi va birinchi test snapshot olindi.

---

## 11. Xulosa

Ushbu **DEPLOYMENT_ARCHITECTURE.md** hujjati EduSelf Teacher platformasini AWS EC2 bulutida sanoat standartlari (Production-Grade) asosida yuritish uchun eng to'liq va sinalgan me'moriy qo'llanmadir.

Tizim **past operatsion xarajat**, **yuqori tarmoq tezligi (<300ms ACK)**, **katta ishonchlilik (EBS gp3 + DLM Snapshotlar)** va **to'liq avtomatlashtirilgan CI/CD quvuri** bilan ta'minlangan.
