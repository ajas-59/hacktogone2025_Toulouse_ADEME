# -------------------------------------------
# CarbonScore • DEMO ultra simple (Catégorie 1)
# -------------------------------------------
# 👉 Objectif : montrer le parcours et le calcul en live
# 👉 Facteurs = exemples pédagogiques (remplacer par ADEME ensuite)

import streamlit as st

st.set_page_config(page_title="CarbonScore Demo", layout="wide")
st.title("🌍 CarbonScore — Démo Émissions Directes (Cat. 1)")
st.caption("Méthodo ADEME (simplifiée) : Activité × Facteur d’émission. "
           "CO₂ biogénique affiché à part (non inclus dans le total).")

# --- Facteurs d'exemple (à remplacer par Base Carbone) ---
FE_1A = {  # Combustion fossile (kg CO2e / unité)
    "Gaz naturel (kWh PCI)": 0.204,
    "Fioul domestique (L)": 2.68,
    "Gazole flotte (L)": 3.17,
}
FE_1B = {  # Biomasse : CH4+N2O en CO2e / unité, et CO2 biogénique / unité
    "Bois énergie (kWh PCI)": {"ch4n2o": 0.012, "co2bio": 0.35}
}
FE_1C = {  # Procédés (kg CO2e / unité)
    "Clinker (t)": 550
}
GWP_1D = {  # PRG 100 ans (kg CO2e / kg de fluide)
    "R-410A": 2088,
    "R-134a": 1430,
}

# --- Interface minimale ---
col_form, col_result = st.columns([2, 1])

with col_form:
    st.subheader("1A. Combustion fossile")
    src_1a = st.selectbox("Source", list(FE_1A.keys()), index=0)
    q_1a = st.number_input("Quantité", min_value=0.0, value=12000.0)
    fe_1a = FE_1A[src_1a]
    e_1a = q_1a * fe_1a

    st.divider()
    st.subheader("1B. Biomasse / biogaz")
    src_1b = st.selectbox("Source biomasse", list(FE_1B.keys()), index=0)
    q_1b = st.number_input("Quantité (biomasse)", min_value=0.0, value=5000.0)
    fe_1b = FE_1B[src_1b]
    e_1b = q_1b * fe_1b["ch4n2o"]      # CH4+N2O -> comptabilisé
    co2bio = q_1b * fe_1b["co2bio"]    # CO2 biogénique -> à part

    st.divider()
    st.subheader("1C. Procédés industriels")
    src_1c = st.selectbox("Procédé", list(FE_1C.keys()), index=0)
    q_1c = st.number_input("Production (unité affichée dans le libellé)", min_value=0.0, value=100.0)
    fe_1c = FE_1C[src_1c]
    e_1c = q_1c * fe_1c

    st.divider()
    st.subheader("1D. Fuites de fluides frigorigènes")
    src_1d = st.selectbox("Fluide", list(GWP_1D.keys()), index=0)
    q_1d = st.number_input("Masse perdue (kg)", min_value=0.0, value=2.0, step=0.1)
    gwp_1d = GWP_1D[src_1d]
    e_1d = q_1d * gwp_1d

with col_result:
    st.subheader("Résultat en direct")
    st.metric("1A — Combustion (kg CO₂e)", f"{e_1a:,.0f}")
    st.metric("1B — Biomasse (kg CO₂e)", f"{e_1b:,.0f}")
    st.metric("1C — Procédés (kg CO₂e)", f"{e_1c:,.0f}")
    st.metric("1D — Fuites (kg CO₂e)", f"{e_1d:,.0f}")

    total = e_1a + e_1b + e_1c + e_1d
    st.metric("TOTAL (t CO₂e)", f"{total/1000:,.2f}")
    st.caption(f"CO₂ biogénique (info séparée) : {co2bio/1000:,.2f} t")

st.info("🧪 Démo : facteurs d’émission *exemples*. Pour passer en réel, remplace par les FE de la Base Carbone (v23.8.0+), garde les mêmes unités (kWh PCI, L, kg, t).")
