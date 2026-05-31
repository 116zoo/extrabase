#!/usr/bin/env python3
"""
scrapling_fetcher.py — Couche HTTP unifiée pour tous les agents SEO-GEO-AEO.

Priorité de fetch :
1. FetcherSession(impersonate="chrome", stealthy_headers=True) si scrapling installé
2. Sur 403/429/503 + stealth=True → StealthyFetcher(headless=True)
3. Fallback requests.Session si scrapling absent (CI / tests)

Standalone — aucun import local.
"""
import json
import re
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Détection scrapling
# ---------------------------------------------------------------------------
try:
    from scrapling.fetchers import Fetcher, StealthyFetcher, FetcherSession  # noqa: F401
    SCRAPLING = True
except ImportError:
    SCRAPLING = False

BLOCKED_STATUSES = {403, 429, 503}

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# SelectorResult — compatible .get() / .getall()
# ---------------------------------------------------------------------------

class SelectorResult:
    """
    Résultat d'un appel .css() sur NormalizedResponse (mode fallback BS4).
    Imite l'interface scrapling/parsel : .get() et .getall().
    """

    def __init__(self, elements, pseudo: str | None, attr_name: str | None):
        self._elements = elements      # liste de balises BS4
        self._pseudo = pseudo          # "text" | "attr" | None
        self._attr_name = attr_name    # nom de l'attribut si pseudo == "attr"

    def _extract_one(self, el) -> str | None:
        if self._pseudo == "text":
            return el.get_text()
        if self._pseudo == "attr" and self._attr_name:
            return el.get(self._attr_name)
        return str(el)

    def get(self) -> str | None:
        for el in self._elements:
            val = self._extract_one(el)
            if val is not None:
                return val
        return None

    def getall(self) -> list:
        result = []
        for el in self._elements:
            val = self._extract_one(el)
            if val is not None:
                result.append(val)
        return result


# ---------------------------------------------------------------------------
# NormalizedResponse
# ---------------------------------------------------------------------------

_CSS_PSEUDO_RE = re.compile(r"^(.*?)(?:::(text|attr\(([^)]+)\)))?$")


class NormalizedResponse:
    """Interface commune requests / scrapling."""

    def __init__(
        self,
        status_code: int,
        text: str,
        headers: dict,
        url: str,
        _scrapling_page=None,
    ):
        self.status_code = status_code
        self.text = text
        self.headers = headers
        self.url = url
        self.blocked: bool = status_code in BLOCKED_STATUSES
        self._scrapling_page = _scrapling_page  # page scrapling native si dispo

    # ------------------------------------------------------------------
    # .css() — délègue à scrapling si dispo, sinon BS4
    # ------------------------------------------------------------------

    def css(self, selector: str):
        """
        Retourne un objet avec .get() -> str|None  et  .getall() -> list[str].

        Gère les pseudo-éléments ::text et ::attr(name).
        """
        if self._scrapling_page is not None:
            # scrapling expose déjà cette interface
            return self._scrapling_page.css(selector)

        # Fallback : BeautifulSoup + cssselect
        return self._bs4_css(selector)

    def _bs4_css(self, selector: str):
        from bs4 import BeautifulSoup

        # Découpe le pseudo-élément final s'il existe
        m = _CSS_PSEUDO_RE.match(selector)
        if m:
            base_selector = m.group(1).strip()
            pseudo_full = m.group(2)   # "text" ou "attr(name)" ou None
            attr_name = m.group(3)     # nom de l'attribut ou None
            if pseudo_full == "text":
                pseudo = "text"
            elif attr_name:
                pseudo = "attr"
            else:
                pseudo = None
        else:
            base_selector = selector
            pseudo = None
            attr_name = None

        soup = BeautifulSoup(self.text, "lxml")
        try:
            elements = soup.select(base_selector)
        except Exception:
            elements = []

        return SelectorResult(elements, pseudo, attr_name)


# ---------------------------------------------------------------------------
# smart_get
# ---------------------------------------------------------------------------

def smart_get(
    url: str,
    *,
    timeout: int = 15,
    stealth: bool = False,
    retries: int = 2,
    session=None,
) -> NormalizedResponse:
    """
    GET intelligent avec fallback transparent.

    - Si scrapling dispo : FetcherSession(impersonate='chrome', stealthy_headers=True)
    - Si 403/429/503 ET stealth=True : réessaie avec StealthyFetcher(headless=True)
    - Si scrapling absent : requests.get() avec User-Agent Chrome standard
    - Toute exception non gérée → NormalizedResponse(status_code=0)
    """
    try:
        if SCRAPLING:
            return _scrapling_get(url, timeout=timeout, stealth=stealth, retries=retries, session=session)
        return _requests_get(url, timeout=timeout, retries=retries, session=session)
    except Exception:
        return NormalizedResponse(status_code=0, text="", headers={}, url=url, _scrapling_page=None)


def _scrapling_get(url, *, timeout, stealth, retries, session) -> NormalizedResponse:
    last_exc = None
    attempt_session = session

    for attempt in range(max(1, retries)):
        try:
            if attempt_session is not None:
                page = attempt_session.get(url, timeout=timeout)
            else:
                fetcher = FetcherSession(impersonate="chrome", stealthy_headers=True)
                page = fetcher.get(url, timeout=timeout)

            resp = NormalizedResponse(
                status_code=page.status,
                text=page.text,
                headers=dict(page.headers) if page.headers else {},
                url=str(page.url),
                _scrapling_page=page,
            )

            # Escalade StealthyFetcher si bloqué et stealth demandé
            if resp.blocked and stealth:
                return _stealthy_get(url, timeout=timeout)

            return resp

        except Exception as exc:
            last_exc = exc

    # Tous les essais ont échoué → fallback requests
    return _requests_get(url, timeout=timeout, retries=1, session=None)


def _stealthy_get(url, *, timeout) -> NormalizedResponse:
    fetcher = StealthyFetcher(headless=True)
    page = fetcher.get(url, timeout=timeout)
    return NormalizedResponse(
        status_code=page.status,
        text=page.text,
        headers=dict(page.headers) if page.headers else {},
        url=str(page.url),
        _scrapling_page=page,
    )


def _requests_get(url, *, timeout, retries, session) -> NormalizedResponse:
    import requests

    headers = {"User-Agent": CHROME_UA}
    last_exc = None

    for _ in range(max(1, retries)):
        try:
            if session is not None:
                resp = session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            else:
                resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            try:
                hdrs = dict(resp.headers)
            except Exception:
                hdrs = {}
            return NormalizedResponse(
                status_code=resp.status_code,
                text=resp.text,
                headers=hdrs,
                url=str(resp.url) if hasattr(resp, "url") else url,
                _scrapling_page=None,
            )
        except requests.RequestException as exc:
            last_exc = exc

    # Retourne une réponse d'erreur plutôt que lever une exception
    return NormalizedResponse(
        status_code=0,
        text="",
        headers={},
        url=url,
        _scrapling_page=None,
    )


# ---------------------------------------------------------------------------
# smart_session
# ---------------------------------------------------------------------------

@contextmanager
def smart_session():
    """
    Context manager retournant un objet session réutilisable.

    Avec scrapling : FetcherSession (pool TCP persistant).
    Sans scrapling  : requests.Session.

    Usage :
        with smart_session() as sess:
            resp = smart_get(url, session=sess)
    """
    if SCRAPLING:
        sess = FetcherSession(impersonate="chrome", stealthy_headers=True)
        try:
            yield sess
        finally:
            pass  # FetcherSession gère son propre cycle de vie
    else:
        import requests
        sess = requests.Session()
        sess.headers.update({"User-Agent": CHROME_UA})
        try:
            yield sess
        finally:
            sess.close()


# ---------------------------------------------------------------------------
# extract_schema_types
# ---------------------------------------------------------------------------

def extract_schema_types(response: NormalizedResponse) -> list:
    """
    Extrait les @type de tous les blocs JSON-LD présents dans la page.

    Utilise response.css('script[type="application/ld+json"]::text').getall()
    si scrapling dispo (page native), sinon BeautifulSoup.
    """
    types = []

    # Tente d'abord via .css() qui dispatche vers scrapling ou BS4
    try:
        raw_blocks = response.css('script[type="application/ld+json"]::text').getall()
    except Exception:
        raw_blocks = []

    # Si .css() n'a rien donné (page vide ou erreur), BS4 direct
    if not raw_blocks:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "lxml")
            raw_blocks = [
                s.string or ""
                for s in soup.find_all("script", attrs={"type": "application/ld+json"})
            ]
        except Exception:
            raw_blocks = []

    for raw in raw_blocks:
        try:
            data = json.loads(raw)
        except Exception:
            continue

        # Cas @graph
        if "@graph" in data:
            for node in data["@graph"]:
                t = node.get("@type")
                if t:
                    if isinstance(t, list):
                        types.extend(str(x) for x in t)
                    else:
                        types.append(str(t))
        else:
            t = data.get("@type")
            if t:
                if isinstance(t, list):
                    types.extend(str(x) for x in t)
                else:
                    types.append(str(t))

    return types
