
# PortalCasteller Ranking API 2.0

Aquesta versió ja no necessita que l'usuari proporcioni la URL amb `sig`.

## Petició

```text
GET /api/ranking?dataIni=2026-01-01&dataFi=2026-10-08&numCast=3&numRepet=1
```

Per tant:

- `dataIni`: inici del període
- `dataFi`: final del període
- `numCast=3`: tres millors castells
- `numRepet=1`: màxim d'una repetició segons el criteri de PortalCasteller

L'API obre la pàgina oficial de PortalCasteller amb Playwright, omple el formulari i deixa que PortalCasteller generi el seu `sig`. Després llegeix la taula de resultat.

## Instal·lació

```bash
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --host 0.0.0.0 --port 8000
```

Per producció, recomanable Docker:

```bash
docker build -t portalcasteller-api .
docker run -p 8000:8000 portalcasteller-api
```

## WordPress

Copia `wordpress-shortcode.php` al plugin/snippet del teu WordPress i defineix:

```php
define('PORTALCASTELLER_API_URL', 'https://api.elteudomini.cat');
```

Després:

```text
[ranking_casteller inici="2026-01-01" fi="2026-10-08" castells="3" repeticions="1"]
```

## Nota tècnica

Els selectors del formulari poden variar si PortalCasteller modifica el seu HTML. Per això la versió 2 intenta diversos selectors i manté el scraping separat de la presentació de WordPress.

No es fabrica ni es calcula el `sig`; el genera PortalCasteller.
