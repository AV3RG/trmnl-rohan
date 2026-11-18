.PHONY: init up down restart logs ps shell update backup plugin-deploy

init: ## create .env with a fresh APP_KEY (no-op if .env exists)
	@test -f .env || { sed "s|^APP_KEY=.*|APP_KEY=base64:$$(openssl rand -base64 32)|" .env.example > .env && echo "wrote .env"; }

up: init ## start (also comes back by itself after reboot/crash)
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f --tail=100

ps:
	docker compose ps

shell:
	docker compose exec app sh

update: backup ## bump LARAPAPER_VERSION in .env first, then run this
	docker compose pull
	docker compose up -d

backup: ## copy the sqlite database into backups/
	@mkdir -p backups
	docker compose cp app:/var/www/html/database/storage/database.sqlite backups/database-$$(date +%Y%m%d-%H%M%S).sqlite

# Push plugins/$(DIR)/template.liquid into the plugin called $(NAME) and save a preview to plugins/$(DIR)/preview.png
plugin-deploy:
	docker compose cp plugins/$(DIR)/template.liquid app:/tmp/plugin-template.liquid
	docker compose cp plugins/deploy.php app:/tmp/plugin-deploy.php
	@uuid=$$(docker compose exec -T -e PLUGIN_NAME="$(NAME)" app php artisan tinker --execute='require "/tmp/plugin-deploy.php";' | awk '/^PREVIEW/{print $$2}'); \
	test -n "$$uuid" || { echo "deploy failed"; exit 1; }; \
	docker compose cp app:/var/www/html/storage/app/public/images/generated/$$uuid.png plugins/$(DIR)/preview.png && echo "preview: plugins/$(DIR)/preview.png"
