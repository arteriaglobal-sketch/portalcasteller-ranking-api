# Desplegament a Render

## 1. Crear repositori GitHub

Crea un repositori, per exemple:

`portalcasteller-ranking-api`

Puja-hi:
- Dockerfile
- render.yaml
- main.py
- requirements.txt

## 2. Crear el servei

A Render:
New -> Web Service -> connecta el repositori.

Si Render detecta `render.yaml`, configura Docker automàticament.

## 3. Configuració

Nom recomanat:
`portalcasteller-ranking-api`

Health Check:
`/health`

Plan:
Free per a proves.

## 4. URL

Render generarà una URL semblant a:

https://portalcasteller-ranking-api.onrender.com

Comprova:

https://portalcasteller-ranking-api.onrender.com/health

Ha de respondre:

{"ok":true,"version":"2.0.0"}

## 5. Prova del ranking

Obre:

https://portalcasteller-ranking-api.onrender.com/api/ranking?dataIni=2026-01-01&dataFi=2026-10-08&numCast=3&numRepet=1

La primera petició pot trigar perquè un servei Free de Render es pot haver adormit després de 15 minuts d'inactivitat. Render indica que el despertar pot trigar aproximadament un minut.

## 6. WordPress

Quan l'API funcioni, posa al `wp-config.php`:

define('PORTALCASTELLER_API_URL', 'https://portalcasteller-ranking-api.onrender.com');

I activa el plugin PortalCasteller Ranking.

Shortcode:

[ranking_casteller inici="2026-01-01" fi="2026-10-08" castells="3" repeticions="1"]

## Nota

El pla Free és adequat per fer proves, però Render adverteix que els serveis gratuïts no estan pensats per a producció i entren en repòs després de 15 minuts sense trànsit.
