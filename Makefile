# Override to point at another instance, e.g. COMPOSE="docker compose -p test -f other.yml"
COMPOSE ?= docker compose

.PHONY: init up down restart logs ps shell update backup plugin-deploy config-export config-restore dark-mode heal

init: ## create .env with a fresh APP_KEY (no-op if .env exists)
	@test -f .env || { sed "s|^APP_KEY=.*|APP_KEY=base64:$$(openssl rand -base64 32)|" .env.example > .env && echo "wrote .env"; }

up: init ## start (also comes back by itself after reboot/crash)
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

shell:
	$(COMPOSE) exec app sh

update: backup ## bump LARAPAPER_VERSION in .env first, then run this
	$(COMPOSE) pull
	$(COMPOSE) up -d

backup: ## copy the sqlite database into backups/
	@mkdir -p backups
	$(COMPOSE) cp app:/var/www/html/database/storage/database.sqlite backups/database-$$(date +%Y%m%d-%H%M%S).sqlite

# Push plugins/$(DIR)/template.liquid into the plugin called $(NAME) and save a preview to plugins/$(DIR)/preview.png
plugin-deploy:
	$(COMPOSE) cp plugins/$(DIR)/template.liquid app:/tmp/plugin-template.liquid
	$(COMPOSE) cp plugins/deploy.php app:/tmp/plugin-deploy.php
	@$(COMPOSE) exec -T -u root app rm -f /tmp/plugin-settings.json
	@test ! -f plugins/$(DIR)/plugin.json || $(COMPOSE) cp plugins/$(DIR)/plugin.json app:/tmp/plugin-settings.json
	@out=$$($(COMPOSE) exec -T -e PLUGIN_NAME="$(NAME)" app php artisan tinker --execute='require "/tmp/plugin-deploy.php";'); echo "$$out" | grep ^WEBHOOK; uuid=$$(echo "$$out" | awk '/^PREVIEW/{print $$2}'); \
	if echo "$$out" | grep -q "^DEPLOYED without preview"; then echo "$(NAME): deployed, no preview (no device yet)"; exit 0; fi; \
	test -n "$$uuid" || { echo "deploy failed"; echo "$$out" | tail -5; exit 1; }; \
	$(COMPOSE) cp app:/var/www/html/storage/app/public/images/generated/$$uuid.png plugins/$(DIR)/preview.png && echo "preview: plugins/$(DIR)/preview.png"

# Save plugins, non-secret settings, playlists and device into config/server.json (safe to commit)
config-export:
	$(COMPOSE) cp config/server.json app:/tmp/server.json
	$(COMPOSE) cp config/export.php app:/tmp/config-export.php
	@$(COMPOSE) exec -T app php artisan tinker --execute='require "/tmp/config-export.php";'
	$(COMPOSE) cp app:/tmp/server-export.json config/server.json

# Rebuild a server from config/server.json: deploy custom plugins, install the rest, restore playlists
config-restore:
	@python3 -c 'import json; [print(p["source"]["dir"] + "|" + p["name"]) for p in json.load(open("config/server.json"))["plugins"] if (p.get("source") or {}).get("dir")]' \
	| while IFS="|" read -r dir name; do $(MAKE) --no-print-directory plugin-deploy DIR="$$dir" NAME="$$name" </dev/null || exit 1; done
	$(COMPOSE) cp config/server.json app:/tmp/server.json
	$(COMPOSE) cp config/restore.php app:/tmp/config-restore.php
	@$(COMPOSE) exec -T app php artisan tinker --execute='require "/tmp/config-restore.php";'
	@$(MAKE) --no-print-directory dark-mode

# Re-apply the dark-mode CSS patches in config/dark-mode.json to imported plugins.
dark-mode:
	@$(COMPOSE) cp config/dark-mode.json app:/tmp/dark-mode.json 2>/dev/null
	@$(COMPOSE) cp maintenance/dark-mode.php app:/tmp/dark-mode.php 2>/dev/null
	@$(COMPOSE) exec -T app php artisan tinker --execute='require "/tmp/dark-mode.php";' </dev/null

# Re-render plugins whose image file is missing (otherwise the device shows the TRMNL logo)
heal:
	@$(COMPOSE) cp maintenance/heal-images.php app:/tmp/heal-images.php 2>/dev/null
	@$(COMPOSE) exec -T app php artisan tinker --execute='require "/tmp/heal-images.php";' | grep ^HEALED || true
