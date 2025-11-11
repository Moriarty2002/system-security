Postgres persistence and init scripts

This directory contains the Flask backend and init SQL for the homework project.

Persistence
- PostgreSQL data is bind-mounted to the host at `./postgres_data` (relative to the repo root).
- On first `docker compose up`, if `./postgres_data` is empty, Postgres will initialize the database there.

Init scripts
- SQL files placed in `./be_flask/db_init` are mounted into the container at `/docker-entrypoint-initdb.d` and will be executed by the official Postgres image when the DB directory is empty.

Resetting the database
1. Stop the containers: `docker compose down`
2. Remove or rename the host folder `postgres_data/` to force reinitialization.
   - Example: `mv postgres_data postgres_data.bak`
3. Start again: `docker compose up -d`
4. The init SQL scripts in `be_flask/db_init` will run on the fresh DB.

Notes
- If you prefer a named docker volume instead of a host bind, change `docker-compose.yaml`'s `db` service to use a named volume (e.g. `pgdata:/var/lib/postgresql/data`).
- Ensure the Docker host user has permission to write to `./postgres_data`.
