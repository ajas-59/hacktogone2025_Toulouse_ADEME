import math
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
import streamlit as st

# -----------------------------
# Config API ADEME / Data Fair
# -----------------------------
DATAFAIR_BASE = "https://data.ademe.fr/data-fair/api/v1/datasets"
DATASETS = {
    "base_carbone": "base-carboner",
    "beges": "bilan-ges",
}

DEFAULT_TIMEOUT = 30  # seconds

# -----------------------------------------
# Client HTTP minimal pour Data Fair (GET)
# -----------------------------------------
def _safe_get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    r = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    r.raise_for_status()
    return r.json()

# -----------------------------
# API: Base Carbone (facteurs)
# -----------------------------
def search_factors(
    q: Optional[str] = None,
    size: int = 50,
    page: int = 1,
    select: Optional[List[str]] = None,
    sort: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Interroge /lines du dataset 'base-carboner'.
    - q: recherche plein-texte (si activée sur le dataset)
    - size, page: pagination
    - select: liste de champs (si tu veux réduire la payload)
    - sort: champ de tri éventuel (ex: '-date')
    - extra_params: pour passer n'importe quel autre paramètre supporté par Data Fair
    """
    url = f"{DATAFAIR_BASE}/{DATASETS['base_carbone']}/lines"
    params: Dict[str, Any] = {"size": size, "page": page}
    if q:
        params["q"] = q
    if select:
        params["select"] = ",".join(select)
    if sort:
        params["sort"] = sort
    if extra_params:
        params.update(extra_params)
    return _safe_get(url, params=params)

# ---------------------------------------
# API: Bilans GES publiés (entreprises)
# ---------------------------------------
def get_beges_by_siren(siren: str, size: int = 50, page: int = 1) -> Dict[str, Any]:
    """
    Recherche des bilans publiés par une organisation via son SIREN (ou raison sociale en q).
    """
    url = f"{DATAFAIR_BASE}/{DATASETS['beges']}/lines"
    params = {"q": siren, "size": size, "page": page}
    return _safe_get(url, params=params)

# -----------------------------
# Conversion d'unités (léger)
# -----------------------------
# N.B. : La Base Carbone comporte diverses unités selon l’activité.
# Ici on gère quelques conversions "classiques". Étends ce mapping au besoin.
_CONV = {
    ("kWh", "GJ"): 1.0 / 277.7777777778,  # 1 kWh = 3.6e6 J ; 1 GJ = 1e9 J
    ("GJ", "kWh"): 277.7777777778,
    ("MWh", "kWh"): 1000.0,
    ("kWh", "MWh"): 1 / 1000.0,
    ("L", "L"): 1.0,
    ("kg", "kg"): 1.0,
}

def convert_amount(amount: float, from_unit: str, to_unit: str) -> float:
    key = (normalize_unit(from_unit), normalize_unit(to_unit))
    if key in _CONV:
        return amount * _CONV[key]
    if key[0] == key[1]:
        return amount
    raise ValueError(f"Conversion non supportée: {from_unit} -> {to_unit}")

def normalize_unit(u: Optional[str]) -> str:
    if not u:
        return ""
    u2 = u.strip().lower()
    # normalisations usuelles
    repl = {
        "gj pci": "gj",
        "kwh pci": "kwh",
        "mwh pci": "mwh",
        "kilowattheure": "kwh",
        "gigajoule": "gj",
        "litre": "l",
    }
    return repl.get(u2, u2)

# -------------------------------------------------------
# Heuristiques: deviner "valeur facteur" et "unité facteur"
# -------------------------------------------------------
_NUMERIC_FIELDS_HINTS = [
    # champs fréquents dans Base Carbone (varient selon versions)
    "valeur", "valeur_co2", "co2", "kgco2", "kgco2e", "kgco2eq", "total", "total poste",
]
_UNIT_FIELDS_HINTS = ["unite", "unité", "unity", "unit"]

def _guess_factor_value(line: Dict[str, Any]) -> Optional[float]:
    # 1) cherche des float évidents
    candidates: List[Tuple[str, float]] = []
    for k, v in line.items():
        if isinstance(v, (int, float)) and not math.isnan(float(v)):
            # préférer les clés qui ressemblent à CO2/CO2e/valeur
            score = 0
            lk = k.lower()
            if any(h in lk for h in _NUMERIC_FIELDS_HINTS):
                score += 10
            if "co2" in lk:
                score += 5
            candidates.append((k, float(v) * (100 - score) + 0.00001))  # encode "préférence" via tri inversé
    if not candidates:
        # 2) fallback: nombres dans des strings ?
        for k, v in line.items():
            if isinstance(v, str):
                m = re.search(r"([0-9]+(?:[.,][0-9]+)?)", v)
                if m:
                    try:
                        val = float(m.group(1).replace(",", "."))
                        return val
                    except Exception:
                        pass
        return None
    # reprend le premier candidat après tri par score encodé
    # on tri sur le "valeur ajustée", donc on reprend le plus petit (score max)
    candidates.sort(key=lambda t: t[1])
    best_key = candidates[0][0]
    try:
        return float(line[best_key])
    except Exception:
        return None

def _guess_factor_unit(line: Dict[str, Any]) -> Optional[str]:
    # cherche un champ indiquant l’unité
    for k, v in line.items():
        if any(h in k.lower() for h in _UNIT_FIELDS_HINTS):
            if isinstance(v, str) and v.strip():
                return v.strip()
    # fallback: si une valeur ressemble à "kgCO2e / kWh", extraire après '/'
    for v in line.values():
        if isinstance(v, str) and "/" in v and "co2" in v.lower():
            right = v.split("/")[-1].strip()
            return right
    return None

# -----------------------------
# Calcul d'émissions
# -----------------------------
def compute_emissions(
    amount: float,
    amount_unit: str,
    factor_value: float,
    factor_unit: str,
) -> Tuple[float, str]:
    """
    Calcule: Emissions = amount(converti->factor_unit) * factor_value
    Retourne (emissions, "kgCO2e")
    """
    amount_in_factor_unit = convert_amount(amount, amount_unit, factor_unit)
    return amount_in_factor_unit * factor_value, "kgCO2e"

# -----------------------------
# UI Streamlit
# -----------------------------
st.set_page_config(page_title="CarbonScore • ADEME Connector", layout="wide")
st.title("🔌 ADEME Connector — Base Carbone & Bilans GES")

st.caption(
    "Demo : recherche de facteurs dans **Base Carbone®** et lookup **Bilans GES** "
    "pour intégrer au calculateur. Les résultats dépendent du schéma et de la configuration du dataset courant."
)

tab_factors, tab_calc, tab_beges = st.tabs(["🔎 Recherche FE", "🧮 Calcul", "🏢 BEGES (par SIREN)"])

with tab_factors:
    st.subheader("Recherche de facteurs (Base Carbone®)")
    q = st.text_input("Recherche plein-texte", placeholder="ex. diesel, électricité, gaz naturel…", value="diesel")
    size = st.number_input("Taille de page", min_value=1, max_value=1000, value=50, step=1)
    page = st.number_input("Page", min_value=1, max_value=100000, value=1, step=1)
    run = st.button("Rechercher", type="primary")

    @st.cache_data(show_spinner=False, ttl=300)
    def _cached_search(q, size, page):
        return search_factors(q=q, size=int(size), page=int(page))

    factors_rows: List[Dict[str, Any]] = []
    if run:
        try:
            res = _cached_search(q, size, page)
            factors_rows = res.get("results", [])
            st.success(f"{len(factors_rows)} ligne(s) récupérée(s).")
        except Exception as e:
            st.error(f"Erreur API Base Carbone: {e}")

    if factors_rows:
        df = pd.DataFrame(factors_rows)
        st.dataframe(df, use_container_width=True)

with tab_calc:
    st.subheader("Calcul rapide (Activité × FE)")

    col1, col2 = st.columns(2)
    with col1:
        activity_label = st.text_input("Libellé d’activité", value="Consommation d’électricité")
        amount = st.number_input("Quantité d’activité", value=1000.0, help="ex. 1000 kWh ou 5 GJ")
        amount_unit = st.text_input("Unité d’activité", value="kWh", help="kWh, GJ, MWh, L, kg…")

    with col2:
        st.markdown("**Sélection d’une ligne Base Carbone**")
        st.caption("Colle ici un JSON (une ligne retournée par l’onglet précédent) ou tape un mot-clé et lance la recherche locale.")
        line_json = st.text_area("Ligne (JSON) facultative", height=160)
        # Option de recherche express côté API
        q2 = st.text_input("…ou mot-clé pour chercher la ligne (express)", value="électricité")
        fetch_one = st.button("Chercher + Préparer la meilleure ligne")

    selected_line: Optional[Dict[str, Any]] = None
    if fetch_one:
        try:
            one = search_factors(q=q2, size=1, page=1)
            candidates = one.get("results", [])
            if candidates:
                selected_line = candidates[0]
                st.success("Une ligne candidate a été récupérée depuis Base Carbone.")
                st.json(selected_line)
            else:
                st.warning("Aucune ligne trouvée.")
        except Exception as e:
            st.error(f"Erreur pendant la recherche: {e}")

    if line_json and not selected_line:
        try:
            selected_line = pd.read_json(
                pd.io.common.StringIO(line_json), typ="series"
            ).to_dict()
            st.info("Ligne JSON chargée.")
        except Exception:
            try:
                import json
                selected_line = json.loads(line_json)
                st.info("Ligne JSON chargée.")
            except Exception as e:
                st.error(f"JSON invalide: {e}")

    if selected_line:
        st.markdown("**Extraction heuristique du facteur et de l’unité (peut varier selon schémas)**")
        factor_value = _guess_factor_value(selected_line)
        factor_unit = _guess_factor_unit(selected_line)
        colA, colB = st.columns(2)
        with colA:
            factor_value = st.number_input("Valeur du facteur (kgCO2e / unité FE)", value=float(factor_value) if factor_value else 0.0)
        with colB:
            factor_unit = st.text_input("Unité du facteur", value=factor_unit or "")

        if st.button("Calculer les émissions", type="primary"):
            try:
                if not factor_unit:
                    st.error("Impossible de calculer sans unité de facteur. Renseigne le champ 'Unité du facteur'.")
                else:
                    emissions, emis_unit = compute_emissions(amount, amount_unit, factor_value, factor_unit)
                    st.success(f"**Résultat** : {emissions:,.3f} {emis_unit}")
                    st.caption(f"Activité {amount} {amount_unit} × {factor_value} kgCO2e/{factor_unit}")
            except Exception as e:
                st.error(f"Échec du calcul: {e}")
        with st.expander("Voir la ligne complète"):
            st.json(selected_line)
    else:
        st.info("Aucune ligne sélectionnée pour le calcul (utilise l’un des boutons ci-dessus).")

with tab_beges:
    st.subheader("Bilans GES publiés — Lookup par SIREN (ou raison sociale)")
    siren = st.text_input("SIREN (ou mot-clé)", value="552100554", help="Exemple: SIREN de Carrefour SA: 652014051 ; Orange: 380129866 ; EDF: 552081317 (à vérifier)")
    size_b = st.number_input("Taille de page", min_value=1, max_value=500, value=50, step=1, key="szb")
    page_b = st.number_input("Page", min_value=1, max_value=100000, value=1, step=1, key="pgb")

    run_beges = st.button("Chercher bilans BEGES")
    @st.cache_data(show_spinner=False, ttl=300)
    def _cached_beges(siren, size, page):
        return get_beges_by_siren(siren=siren, size=int(size), page=int(page))

    if run_beges:
        try:
            res = _cached_beges(siren, size_b, page_b)
            rows = res.get("results", [])
            st.success(f"{len(rows)} résultat(s).")
            if rows:
                dfb = pd.DataFrame(rows)
                st.dataframe(dfb, use_container_width=True)
        except Exception as e:
            st.error(f"Erreur API Bilans GES: {e}")

st.divider()
st.caption(
    "⚠️ Démo pédagogique. Pour la **traçabilité**, enregistre l’ID de ligne, la version du dataset, la date de requête, "
    "et vérifie l’adéquation des unités. Étends le convertisseur d’unités selon tes cas réels."
)
