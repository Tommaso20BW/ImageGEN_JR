"""CLASSIFICA: legge la classifica da Diretta.it (Serie A e coppe europee).

Viene dal vecchio bot Classifica_JR (aggiorna_classifica.py): stessa lettura della
pagina, stessi controlli e stesse fasce colorate. Qui la classifica non si salva su
file: `fetch()` la restituisce alla grafica.
"""
import log
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from urllib.parse import urljoin

import requests


# Le URL correnti senza ID seguono automaticamente la stagione attiva scelta
# da Diretta.it. Durante i test delle coppe si usano classifiche archiviate e
# complete: al 24 agosto 2026 le pagine 2026/27 mostrano ancora soltanto i
# tabelloni delle qualificazioni, non la classifica della fase campionato.
COMPETIZIONI = {
    "SA": {
        "nome": "Serie A",
        "url": "https://www.diretta.it/serie-a/classifiche/",
        "test_url": "https://www.diretta.it/serie-a/classifiche/",
        "giornate": 38,
        "squadre": 20,
    },
    "UCL": {
        "nome": "Champions League",
        "url": (
            "https://www.diretta.it/calcio/europa/"
            "champions-league/classifiche/"
        ),
        "test_url": (
            "https://www.diretta.it/calcio/europa/"
            "champions-league-2025-2026/classifiche/"
        ),
        "giornate": 8,
        "squadre": 36,
    },
    "UEL": {
        "nome": "Europa League",
        "url": (
            "https://www.diretta.it/calcio/europa/"
            "europa-league/classifiche/"
        ),
        "test_url": (
            "https://www.diretta.it/calcio/europa/"
            "europa-league-2025-2026/classifiche/"
        ),
        "giornate": 8,
        "squadre": 36,
    },
    "UECL": {
        "nome": "Conference League",
        "url": (
            "https://www.diretta.it/calcio/europa/"
            "conference-league/classifiche/"
        ),
        "test_url": (
            "https://www.diretta.it/calcio/europa/"
            "conference-league-2025-2026/classifiche/"
        ),
        "giornate": 6,
        "squadre": 36,
    },
}

COPPA_ITALIA_RISULTATI_URL = (
    "https://www.diretta.it/calcio/italia/coppa-italia/risultati/"
)

ZONE_SERIE_A_PROVVISORIE = {
    **{pos: "z1" for pos in range(1, 5)},
    5: "z2",
    6: "z3",
    **{pos: "z4" for pos in range(18, 21)},
}

ETICHETTE_ZONE_SERIE_A = (
    ("z1", "Champions"),
    ("z2", "Europa"),
    ("z3", "Conference"),
    ("z4", "Retrocesse"),
)

TEAM_PAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.7",
}

# La tabella usa icone 30x30. La pagina della squadra, sempre su Diretta.it,
# espone invece lo stesso stemma nella variante heading__logo da 100x100.
LOGO_GRANDE_RE = re.compile(
    r'<img\b(?=[^>]*\bclass=["\'][^"\']*\bheading__logo\b[^"\']*["\'])'
    r'(?=[^>]*\bsrc=["\']([^"\']+)["\'])[^>]*>',
    re.IGNORECASE,
)

# Uniche eccezioni richieste: tutti gli altri stemmi restano quelli grandi di
# Diretta.it. Il file Juventus e' l'originale 3359x3359 collegato da Wikipedia;
# quello Roma e' la risorsa 512x512 indicata dall'utente.
LOGHI_PERSONALIZZATI = {
    "juventus": (
        "https://upload.wikimedia.org/wikipedia/commons/9/99/"
        "Juventus_FC_2017_squared_icon_%28white%29.png"
    ),
    "roma": "https://assets.football-logos.cc/logos/italy/512x512/roma.8dfa8968.png",
    "as roma": "https://assets.football-logos.cc/logos/italy/512x512/roma.8dfa8968.png",
}


def format_stagione(anno_inizio) -> str:
    """Converte l'anno iniziale 2026 nella stagione breve 2026/27."""
    try:
        anno = int(anno_inizio)
    except (TypeError, ValueError):
        return ""
    if anno < 1900 or anno > 2100:
        return ""
    return f"{anno}/{(anno + 1) % 100:02d}"


def stagione_da_testo(testo: str) -> str:
    """Estrae la stagione da testi come 'Champions League 2025/2026'."""
    match = re.search(r"(19|20)\d{2}", testo or "")
    return format_stagione(match.group()) if match else ""


def stagione_corrente_da_data() -> str:
    """Fallback della stagione quando Diretta.it non la espone nel titolo."""
    oggi = date.today()
    anno_inizio = oggi.year if oggi.month >= 7 else oggi.year - 1
    return format_stagione(anno_inizio)


def _intero(valore, campo: str, squadra: str) -> int:
    """Converte un valore numerico della tabella e produce errori leggibili."""
    try:
        return int(str(valore).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"valore non valido per {campo} di {squadra}: {valore!r}"
        ) from exc


# Stemmi grandi già trovati in questa sessione: la seconda classifica chiede meno pagine.
_LOGHI_TROVATI: dict[str, str] = {}


def _logo_grande_diretta(team_url: str, fallback: str) -> str:
    """Recupera dalla pagina squadra lo stemma Diretta.it da 100x100.
    Se la pagina non risponde riprova una volta, dopo una breve pausa."""
    if not team_url:
        return fallback
    if team_url in _LOGHI_TROVATI:
        return _LOGHI_TROVATI[team_url]
    for tentativo in (1, 2):
        try:
            response = requests.get(
                urljoin("https://www.diretta.it/", team_url),
                headers=TEAM_PAGE_HEADERS,
                timeout=20,
            )
            response.raise_for_status()
            match = LOGO_GRANDE_RE.search(response.text)
            if match:
                _LOGHI_TROVATI[team_url] = urljoin(response.url, match.group(1))
                return _LOGHI_TROVATI[team_url]
            break
        except Exception as exc:
            log.warn('CLASSIFICA', f"Logo grande non disponibile per {team_url} (tentativo {tentativo}): {exc}")
            if tentativo == 1:
                time.sleep(1.5)
    return fallback


def _logo_personalizzato(nome_squadra: str) -> str:
    return LOGHI_PERSONALIZZATI.get(nome_squadra.strip().lower(), "")


def _loghi_grandi_diretta(raw_rows: list[dict]) -> list[str]:
    """Scarica in parallelo le varianti grandi, mantenendo l'ordine delle righe."""
    if not raw_rows:
        return []
    workers = min(4, len(raw_rows))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        loghi = list(executor.map(
            lambda raw: (
                _logo_personalizzato(raw.get("team", ""))
                or _logo_grande_diretta(
                    raw.get("team_url", ""),
                    raw.get("logo", ""),
                )
            ),
            raw_rows,
        ))

    trovati = sum(
        logo and logo != raw.get("logo", "")
        for logo, raw in zip(loghi, raw_rows)
    )
    log.info('CLASSIFICA', f"Loghi ad alta risoluzione: "
        f"{trovati}/{len(raw_rows)}.")
    if trovati != len(raw_rows):
        raise RuntimeError(
            "non tutte le squadre espongono il logo Diretta.it da 100x100; "
            "interrompo per evitare un'immagine con stemmi sgranati"
        )
    return loghi


def _zona_da_qualificazione_diretta(testo: str) -> str:
    """Converte la descrizione Diretta.it nel colore usato dalla grafica."""
    testo_norm = (testo or "").strip().lower()
    if "champions league" in testo_norm:
        return "z1"
    if "conference league" in testo_norm:
        return "z3"
    if "europa league" in testo_norm:
        return "z2"
    if "retrocessione" in testo_norm:
        return "z4"
    return ""


def _intervalli_posizioni(posizioni: list[int]) -> str:
    """Compatta [1, 2, 3, 5] in '1–3, 5'."""
    if not posizioni:
        return ""
    intervalli = []
    inizio = precedente = posizioni[0]
    for posizione in posizioni[1:]:
        if posizione == precedente + 1:
            precedente = posizione
            continue
        intervalli.append(
            str(inizio) if inizio == precedente else f"{inizio}–{precedente}"
        )
        inizio = precedente = posizione
    intervalli.append(
        str(inizio) if inizio == precedente else f"{inizio}–{precedente}"
    )
    return ", ".join(intervalli)


def _legenda_serie_a(classifica: list[dict]) -> list[str]:
    legenda = []
    for zona, etichetta in ETICHETTE_ZONE_SERIE_A:
        posizioni = [row["pos"] for row in classifica if row.get("zone") == zona]
        intervallo = _intervalli_posizioni(posizioni)
        if not intervallo:
            raise ValueError(f"zona Serie A mancante nella classifica: {zona}")
        legenda.append(f"{intervallo} {etichetta}")
    return legenda


def _applica_zone_serie_a(
    classifica: list[dict],
    coppa_italia_decisa: bool,
) -> tuple[str, list[str]]:
    """Applica fasce provvisorie o definitive e restituisce modalita'/legenda."""
    zone_diretta = {
        row["pos"]: _zona_da_qualificazione_diretta(
            row.pop("_qualification", "")
        )
        for row in classifica
    }
    zone_europee_presenti = {
        zona for zona in zone_diretta.values() if zona in {"z1", "z2", "z3"}
    }
    definitive_disponibili = zone_europee_presenti == {"z1", "z2", "z3"}

    if coppa_italia_decisa and definitive_disponibili:
        modalita = "definitive_diretta"
        zone = zone_diretta
        log.info('CLASSIFICA', "Coppa Italia conclusa: uso le fasce europee definitive "
            "pubblicate da Diretta.it.")
    else:
        modalita = "provvisorie_coppa_italia"
        zone = ZONE_SERIE_A_PROVVISORIE
        if coppa_italia_decisa:
            log.warn('CLASSIFICA', "Finale conclusa ma fasce definitive non ancora complete "
                "su Diretta.it: mantengo temporaneamente le fasce provvisorie.")
        else:
            log.info('CLASSIFICA', "Coppa Italia non ancora conclusa: 5ª Europa League, "
                "6ª Conference League.")

    for row in classifica:
        row["zone"] = zone.get(row["pos"], "")
    return modalita, _legenda_serie_a(classifica)


def _coppa_italia_decisa(page, url: str) -> bool:
    """Rileva una finale conclusa dalla dicitura 'Vincitore' di Diretta.it."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        page.locator(".event__round").first.wait_for(
            state="visible",
            timeout=45_000,
        )
        finale = page.evaluate(
            """
            () => {
                const round = document.querySelector('.event__round');
                if (!round) return null;
                let match = round.nextElementSibling;
                while (match && !match.classList.contains('event__match')) {
                    if (match.classList.contains('event__round')) return null;
                    match = match.nextElementSibling;
                }
                return {
                    round: (round.textContent || '').trim(),
                    match: (match?.textContent || '').trim()
                };
            }
            """
        )
        resolved_url = page.url
        decisa = bool(
            finale
            and finale.get("round", "").strip().lower() == "finale"
            and "vincitore:" in finale.get("match", "").lower()
        )
        stato = "conclusa" if decisa else "non conclusa"
        log.info('CLASSIFICA', f"Coppa Italia {stato}: {resolved_url}")
        return decisa
    except Exception as exc:
        log.warn('CLASSIFICA', "Stato Coppa Italia non verificabile; per sicurezza considero "
            f"le fasce ancora provvisorie: {exc}")
        return False


def scrape_standings_diretta(
    url: str,
    coppa_italia_url: str = "",
) -> tuple[list, int, str, bool] | None:
    """Legge una classifica dal DOM renderizzato di Diretta.it.

    La pagina carica la tabella tramite JavaScript, quindi viene usato Chromium
    headless, gia' installato dai workflow per creare lo screenshot Telegram.
    I loghi vengono copiati direttamente dalla tabella di Diretta.it senza
    override personalizzati.
    """
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                executable_path=os.environ.get("IMAGEGEN_CHROME") or None,
                args=["--disable-dev-shm-usage"],
            )
            try:
                context = browser.new_context(
                    locale="it-IT",
                    timezone_id="Europe/Rome",
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/140.0.0.0 Safari/537.36"
                    ),
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)

                rows = page.locator(".ui-table__body .ui-table__row")
                rows.first.wait_for(state="visible", timeout=45_000)

                raw_rows = rows.evaluate_all(
                    """
                    rows => rows.map(row => ({
                        pos: row.querySelector('.tableCellRank')?.textContent?.trim() || '',
                        qualification: row.querySelector('.tableCellRank')?.getAttribute('title') || '',
                        team: row.querySelector('.tableCellParticipant__name')?.textContent?.trim() || '',
                        team_url: row.querySelector('.tableCellParticipant__name')?.href || '',
                        logo: row.querySelector('.tableCellParticipant__image img')?.src || '',
                        values: [...row.querySelectorAll('span.table__cell--value')]
                            .map(cell => cell.textContent.trim())
                    }))
                    """
                )
                titolo = page.locator("h1").first.inner_text(timeout=10_000)
                resolved_url = page.url
                coppa_italia_decisa = (
                    _coppa_italia_decisa(page, coppa_italia_url)
                    if coppa_italia_url
                    else False
                )
            finally:
                browser.close()
    except Exception as exc:
        log.warn('CLASSIFICA', f"Errore durante l'estrazione da Diretta.it: {exc}")
        return None

    try:
        classifica = []
        loghi_grandi = _loghi_grandi_diretta(raw_rows)
        for raw, logo_grande in zip(raw_rows, loghi_grandi):
            squadra_originale = raw.get("team", "").strip()
            valori = raw.get("values", [])
            if not squadra_originale or len(valori) < 7:
                raise ValueError(f"riga incompleta: {raw!r}")

            posizione_testo = re.sub(r"\D", "", raw.get("pos", ""))
            if not posizione_testo:
                raise ValueError(f"posizione mancante per {squadra_originale}")

            pld = _intero(valori[0], "partite", squadra_originale)
            won = _intero(valori[1], "vittorie", squadra_originale)
            draw = _intero(valori[2], "pareggi", squadra_originale)
            lost = _intero(valori[3], "sconfitte", squadra_originale)
            score_match = re.fullmatch(r"(\d+)\s*:\s*(\d+)", valori[4])
            if not score_match:
                raise ValueError(
                    f"reti non valide per {squadra_originale}: {valori[4]!r}"
                )
            gf, ga = map(int, score_match.groups())
            dr = _intero(valori[5], "differenza reti", squadra_originale)
            points = _intero(valori[6], "punti", squadra_originale)

            if pld != won + draw + lost:
                raise ValueError(
                    f"totale partite incoerente per {squadra_originale}: "
                    f"{pld} != {won}+{draw}+{lost}"
                )
            if dr != gf - ga:
                raise ValueError(
                    f"differenza reti incoerente per {squadra_originale}: "
                    f"{dr} != {gf}-{ga}"
                )

            # Variante grande Diretta.it, salvo le sole eccezioni Juventus/Roma.
            logo = logo_grande
            classifica.append({
                "pos": int(posizione_testo),
                # Diretta.it e' gia' localizzato in italiano: manteniamo il
                # nome mostrato dal sito senza mappe legacy esterne.
                "team": squadra_originale,
                "logo": logo,
                "logo_light_bg": logo,
                "logo_dark_bg": logo,
                "pt": points,
                "p": pld,
                "v": won,
                "n": draw,
                "p_pers": lost,
                "gf": gf,
                "gs": ga,
                "dr": dr,
                "_qualification": raw.get("qualification", ""),
            })

        classifica.sort(key=lambda row: row["pos"])
        posizioni = [row["pos"] for row in classifica]
        if posizioni != list(range(1, len(classifica) + 1)):
            raise ValueError(f"posizioni non consecutive: {posizioni}")
        if len({row["team"] for row in classifica}) != len(classifica):
            raise ValueError("la tabella contiene squadre duplicate")

        giornata = max((row["p"] for row in classifica), default=0) or 1
        stagione = stagione_da_testo(titolo)
        log.info('CLASSIFICA', f"Pagina risolta: {resolved_url}")
        return classifica, giornata, stagione, coppa_italia_decisa
    except Exception as exc:
        log.warn('CLASSIFICA', f"Formato classifica Diretta.it non valido: {exc}")
        return None


class ClassificaError(ValueError):
    """Classifica non disponibile: il messaggio si mostra nella Mini App."""


def fetch(comp_key: str) -> dict:
    """Classifica aggiornata di SA, UCL, UEL o UECL, pronta per la grafica."""
    comp_key = (comp_key or "").upper()
    comp = COMPETIZIONI.get(comp_key)
    if not comp:
        raise ClassificaError("Competizione non valida: scegli Serie A, Champions, Europa o Conference.")

    log.info('CLASSIFICA', f"{comp['nome']}: leggo la classifica da Diretta.it")
    risultato = scrape_standings_diretta(
        comp["url"],
        COPPA_ITALIA_RISULTATI_URL if comp_key == "SA" else "",
    )
    if risultato is None:
        raise ClassificaError("Non riesco a leggere la classifica da Diretta.it. Riprova tra poco.")
    classifica, giornata, stagione, coppa_italia_decisa = risultato

    if len(classifica) != comp["squadre"]:
        raise ClassificaError(
            f"Diretta.it mostra {len(classifica)} squadre invece di {comp['squadre']}: "
            "la classifica della fase campionato forse non è ancora pubblicata."
        )

    output = {
        "competition": comp_key,
        "competition_name": comp["nome"],
        "giornata": giornata,
        "stagione": stagione or stagione_corrente_da_data(),
        "classifica": classifica,
    }
    if comp_key == "SA":
        mode, legend = _applica_zone_serie_a(classifica, coppa_italia_decisa)
        output["qualification_mode"] = mode
        output["qualification_legend"] = legend
    else:
        for row in classifica:
            row.pop("_qualification", None)
    return output
