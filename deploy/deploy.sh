#!/bin/bash
# Deploy script for pamyat9may.ru → VPS 85.117.235.115
set -e

VPS="root@85.117.235.115"
REMOTE_DIR="/var/www/pamyat9may"

echo "=== Building Astro site ==="
cd "$(dirname "$0")/.."
npm run build

echo "=== Syncing site to VPS ==="
rsync -avz --delete dist/ "$VPS:$REMOTE_DIR/dist/"

echo "=== Syncing bot to VPS ==="
rsync -avz --exclude='data/' --exclude='.env' --exclude='__pycache__' \
  bot/ "$VPS:$REMOTE_DIR/bot/"

echo "=== Syncing deploy configs ==="
rsync -avz deploy/ecosystem.config.cjs "$VPS:$REMOTE_DIR/"
rsync -avz deploy/nginx.conf "$VPS:/etc/nginx/sites-available/pamyat9may"

echo "=== Restarting services on VPS ==="
ssh "$VPS" "
  ln -sf /etc/nginx/sites-available/pamyat9may /etc/nginx/sites-enabled/
  nginx -t && systemctl reload nginx
  cd $REMOTE_DIR
  pip3 install -r bot/requirements.txt -q
  pm2 restart ecosystem.config.cjs --update-env || pm2 start ecosystem.config.cjs
  pm2 save
"

echo "=== Done! Site: https://pamyat9may.ru ==="
