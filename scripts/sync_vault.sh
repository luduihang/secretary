#!/bin/bash
cd ~/secretary/obsidian_vault
git fetch --all
git reset --hard origin/main  # 强制覆盖，保证服务器是最新的
echo "Vault synced at $(date)" >> ~/secretary/logs/sync_log.txt

