
import asyncio
import csv
import io
import re
from urllib.parse import urlparse, parse_qs

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from playwright.async_api import async_playwright

app = FastAPI(title="PortalCasteller Ranking API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE = "https://www.portalcasteller.cat/v2/ranking/"

class RankingRequest(BaseModel):
    dataIni: str
    dataFi: str
    numCast: int = 3
    numRepet: int = 1
    dataRefIni: str | None = None
    dataRefFi: str | None = None

def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()

def valid_date(s):
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))

def parse_query(url):
    q = parse_qs(urlparse(url).query)
    return {k: (v[0] if v else None) for k, v in q.items()}

async def first_visible(page, selectors):
    for sel in selectors:
        loc = page.locator(sel)
        try:
            if await loc.count() and await loc.first.is_visible():
                return loc.first
        except Exception:
            pass
    return None

async def set_input(page, selectors, value):
    loc = await first_visible(page, selectors)
    if not loc:
        return False
    try:
        await loc.fill(value)
        return True
    except Exception:
        return False

async def set_select(page, selectors, value):
    loc = await first_visible(page, selectors)
    if not loc:
        return False
    try:
        await loc.select_option(value)
        return True
    except Exception:
        try:
            await loc.fill(value)
            return True
        except Exception:
            return False

async def submit_form(page):
    selectors = [
        'button:has-text("Generar")',
        'button:has-text("Calcular")',
        'input[type="submit"]',
        'button[type="submit"]',
        'a:has-text("Generar")',
        'a:has-text("Calcular")',
    ]
    btn = await first_visible(page, selectors)
    if not btn:
        return False
    try:
        await btn.click()
        return True
    except Exception:
        return False

async def build_result_url(req):
    """
    Obre el formulari oficial de PortalCasteller, intenta seleccionar
    el ranking basat en castells i introdueix dates/numCast/numRepet.
    No calcula ni fabrica el 'sig': el genera PortalCasteller.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1000)

        # Intentar activar el mode "Ranking basat en castells".
        radio = await first_visible(page, [
            'input[value="Castells"]',
            'input[name="RankType"][value="Castells"]',
            'label:has-text("Ranking basat en castells")',
        ])
        if radio:
            try:
                await radio.check()
            except Exception:
                try:
                    await radio.click()
                except Exception:
                    pass

        # Paràmetres coneguts pel formulari.
        await set_input(page, [
            'input[name="DataIni"]',
            '#DataIni',
            'input[id*="DataIni"]',
            'input[placeholder*="AAAA"]',
        ], req.dataIni)

        await set_input(page, [
            'input[name="DataFi"]',
            '#DataFi',
            'input[id*="DataFi"]',
        ], req.dataFi)

        await set_input(page, [
            'input[name="NumCast"]',
            '#NumCast',
            'input[id*="NumCast"]',
        ], str(req.numCast))

        await set_input(page, [
            'input[name="NumRepet"]',
            '#NumRepet',
            'input[id*="NumRepet"]',
        ], str(req.numRepet))

        if req.dataRefIni:
            await set_input(page, [
                'input[name="DataRefIni"]',
                '#DataRefIni',
                'input[id*="DataRefIni"]',
            ], req.dataRefIni)

        if req.dataRefFi:
            await set_input(page, [
                'input[name="DataRefFi"]',
                '#DataRefFi',
                'input[id*="DataRefFi"]',
            ], req.dataRefFi)

        # Aquests valors són els del mode que ja hem identificat.
        await set_select(page, ['select[name="ActType"]', '#ActType'], "3c")
        await set_select(page, ['select[name="RankType"]', '#RankType'], "Castells")

        await submit_form(page)
        await page.wait_for_timeout(1500)

        result_url = page.url
        if "ranking-res" not in result_url:
            # Alguns formularis fan submit amb JS després d'un temps addicional.
            await page.wait_for_timeout(2500)
            result_url = page.url

        await browser.close()

        if "ranking-res" not in result_url:
            raise RuntimeError(
                "PortalCasteller no ha retornat la pàgina de resultat. "
                "Cal revisar els selectors del formulari en aquesta versió del web."
            )
        return result_url

async def scrape_result(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(1000)

        tables = page.locator("table")
        best = None
        best_rows = 0

        for i in range(await tables.count()):
            t = tables.nth(i)
            rows = await t.locator("tr").count()
            txt = clean(await t.inner_text())
            if rows > best_rows and ("Colla" in txt and "Punts" in txt):
                best, best_rows = t, rows

        if best is None:
            await browser.close()
            raise RuntimeError("No s'ha trobat la taula del ranking.")

        rows = best.locator("tr")
        ranking = []

        for i in range(1, await rows.count()):
            cells = best.locator("tr").nth(i).locator("th,td")
            vals = [clean(await cells.nth(j).inner_text()) for j in range(await cells.count())]
            if len(vals) < 4:
                continue

            pos = vals[0]
            if not re.fullmatch(r"\d+", pos):
                continue

            ranking.append({
                "posicio": int(pos),
                "colla": vals[1],
                "castells": vals[2],
                "punts": int(re.sub(r"[^\d-]", "", vals[3])) if re.search(r"\d", vals[3]) else None,
                "percentatge": vals[4] if len(vals) > 4 else None,
            })

        title = clean(await page.locator("h1").first.inner_text()) if await page.locator("h1").count() else "Ranking"
        params = parse_query(url)

        await browser.close()

        return {
            "ok": True,
            "source": "PortalCasteller",
            "url": url,
            "params": params,
            "title": title,
            "ranking": ranking,
        }

@app.get("/health")
async def health():
    return {"ok": True, "version": "2.0.0"}

@app.get("/api/ranking")
async def ranking(
    dataIni: str = Query(...),
    dataFi: str = Query(...),
    numCast: int = Query(3, ge=1, le=20),
    numRepet: int = Query(1, ge=0, le=20),
    dataRefIni: str | None = Query(None),
    dataRefFi: str | None = Query(None),
):
    req = RankingRequest(
        dataIni=dataIni, dataFi=dataFi, numCast=numCast, numRepet=numRepet,
        dataRefIni=dataRefIni, dataRefFi=dataRefFi
    )
    for name, value in [("dataIni", dataIni), ("dataFi", dataFi)]:
        if not valid_date(value):
            raise HTTPException(400, f"{name} ha de tenir format YYYY-MM-DD")
    try:
        url = await build_result_url(req)
        result = await scrape_result(url)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/ranking")
async def ranking_post(req: RankingRequest):
    if not valid_date(req.dataIni) or not valid_date(req.dataFi):
        raise HTTPException(400, "Les dates han de tenir format YYYY-MM-DD")
    try:
        url = await build_result_url(req)
        return await scrape_result(url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.get("/api/ranking.csv")
async def ranking_csv(
    dataIni: str = Query(...),
    dataFi: str = Query(...),
    numCast: int = Query(3, ge=1, le=20),
    numRepet: int = Query(1, ge=0, le=20),
):
    req = RankingRequest(dataIni=dataIni, dataFi=dataFi, numCast=numCast, numRepet=numRepet)
    try:
        url = await build_result_url(req)
        result = await scrape_result(url)
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=["posicio","colla","castells","punts","percentatge"])
        writer.writeheader()
        writer.writerows(result["ranking"])
        from fastapi.responses import Response
        return Response(
            content=out.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=ranking.csv"},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
