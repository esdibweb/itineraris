# Deployment

The application runs as a Docker stack (e.g. in Portainer) with three services:

| Service  | Purpose                                                        |
|----------|----------------------------------------------------------------|
| `web`    | Django served by Gunicorn on port 8000; applies migrations on start |
| `db`     | PostgreSQL, data in the `pgdata` volume                        |
| `backup` | Daily `pg_dump` to the `backups` volume                        |

HTTPS is terminated by the reverse proxy in front (nginx), which forwards to the VM on `APP_PORT`.

## How a change reaches production

1. Push to `master`.
2. The GitHub workflow (`.github/workflows/deploy.yml`) runs the tests, builds the image and
   publishes it as `ghcr.io/esdibweb/itineraris:latest` (and `:sha-<commit>`).
3. Portainer pulls the new image and recreates the `web` container, either automatically through
   a webhook (see below) or with one click.

## First-time setup

### 1. Publish the image

Push the repository to GitHub and wait for the **Test, build and deploy** workflow to finish.
New GitHub packages are private, so either make it public
(*GitHub → your profile → Packages → the package → Package settings → Change visibility*)
or add `ghcr.io` as a registry in Portainer with a token that has `read:packages`.

### 2. Create the stack in Portainer

*Stacks → Add stack*:

- **Build method:** Repository
- **Repository URL:** the GitHub repository URL; **reference:** `refs/heads/master`;
  **compose path:** `docker-compose.yml`
- **Environment variables:** *Load variables from .env file* with a copy of `.env.example`
  filled in. At least `APP_IMAGE`, `SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `POSTGRES_PASSWORD`
  and the Google credentials are required.
- Deploy the stack.

### 3. Configure the reverse proxy

Forward `apps.escoladisseny.com` to `http://<vm-address>:<APP_PORT>`. The proxy must:

- send `X-Forwarded-Proto: https`. Django redirects every plain HTTP request to HTTPS, so
  without this header the site loops forever;
- pass the original `Host` header;
- append the client address to `X-Forwarded-For` (`proxy_set_header X-Forwarded-For
  $proxy_add_x_forwarded_for;`). Failed logins are limited per address;
- allow uploads of at least 20 MB (`client_max_body_size 20m;` in nginx). The default of 1 MB
  rejects a full-year Codex CSV.

Only the proxy should be able to reach `APP_PORT`: block it for other hosts in the VM's
firewall. A client connecting directly could set its own `X-Forwarded-For` header.

### 4. Bring the existing data

Create a dump on the current server, copy it to the VM and restore it with the `web` service
stopped (the container names below assume the stack is called `intranet`):

```sh
# on the current server
pg_dump --format=custom --file=intranet.dump <database>

# on the VM
docker stop intranet-web-1
docker exec -i intranet-db-1 sh -c 'pg_restore --clean --if-exists --no-owner --no-acl -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < intranet.dump
docker start intranet-web-1
```

`POSTGRES_VERSION` must be at least the PostgreSQL version that created the dump.
Avatars do not need to be copied: they are downloaded again at each Google login.

For a fresh installation instead, create an administrator:

```sh
docker exec -it intranet-web-1 python manage.py createsuperuser
```

## Updating

After the workflow has published a new image, open the stack in Portainer and update it with
**re-pull image** enabled. The page header and footer then show the new version, the build
date and commit (e.g. `2026.10.08-f5462d7`), which matches the commit on GitHub.

To make this automatic, enable the stack webhook in Portainer (with re-pull image enabled), if
your Portainer edition offers it, and save its URL as the repository secret
`PORTAINER_WEBHOOK_URL` (*GitHub → Settings → Secrets and variables → Actions*). The workflow
calls it after each successful build. Portainer must be reachable from the internet for this.

To roll back, set `APP_IMAGE` to a previous `:sha-<commit>` tag and update the stack.

## Maintenance

```sh
# Check, and then fix, the cached hour totals of all students
docker exec -it intranet-web-1 python manage.py recalculate_hours
docker exec -it intranet-web-1 python manage.py recalculate_hours --apply

# List backups and copy one out of the volume
docker exec intranet-backup-1 ls -l /backups
docker cp intranet-backup-1:/backups/intranet-YYYY-MM-DD.dump .
```

Take a snapshot of the VM before major updates; the database dumps cover day-to-day
recovery.

## Notes

- Notification emails are queued in the database by django-mailer but not delivered:
  `MAILER_EMAIL_BACKEND` is the console backend and no worker sends the queue.
- Local development does not use Docker. Tests run with `python manage.py test --settings=home.settings_test`.
