#!/usr/bin/env bash
set -euo pipefail

cd /root/MultiGen

BACKUP_TGZ="${1:-/root/MultiGen/docker-business-data-export-20260329-053350.tar.gz}"

if [ ! -f "$BACKUP_TGZ" ]; then
  echo "备份包不存在: $BACKUP_TGZ" >&2
  exit 1
fi

tar -xzf "$BACKUP_TGZ" -C /root/MultiGen
BACKUP_DIR="/root/MultiGen/$(basename "$BACKUP_TGZ" .tar.gz)"

if [ -f "$BACKUP_DIR/SHA256SUMS.txt" ]; then
  (cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS.txt)
fi

docker compose up -d multigen-postgres multigen-redis

POSTGRES_VOL=$(docker inspect multigen-postgres --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')
REDIS_VOL=$(docker inspect multigen-redis --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Name}}{{end}}{{end}}')

if [ -z "$POSTGRES_VOL" ] || [ -z "$REDIS_VOL" ]; then
  echo "无法识别 Postgres 或 Redis 数据卷名" >&2
  exit 1
fi

docker compose down

docker run --rm -v "${POSTGRES_VOL}:/to" -v "${BACKUP_DIR}/volumes:/from" alpine sh -lc 'rm -rf /to/* /to/.[!.]* /to/..?* 2>/dev/null || true; tar -xzf /from/multigen_postgres_data.tar.gz -C /to'
docker run --rm -v "${REDIS_VOL}:/to" -v "${BACKUP_DIR}/volumes:/from" alpine sh -lc 'rm -rf /to/* /to/.[!.]* /to/..?* 2>/dev/null || true; tar -xzf /from/multigen_redis_data.tar.gz -C /to'

mkdir -p ./logs
if [ -f "${BACKUP_DIR}/api/logs.tar.gz" ]; then
  rm -rf ./logs/*
  tar -xzf "${BACKUP_DIR}/api/logs.tar.gz" -C .
fi

docker compose up -d
docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'multigen-(postgres|redis|api|ui|nginx|sandbox)' || true
