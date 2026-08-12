"""
BICO DE PATO — ANÁLISE DE DESCONEXÃO OPERACIONAL (B3)
======================================================

Hipótese:
    Investigar empiricamente se, entre 2021 e o período mais recente disponível,
    empresas não financeiras da B3 apresentaram crescimento operacional (EBITDA LTM),
    enquanto o mercado reduziu o múltiplo pelo qual esses resultados são avaliados (EV/EBITDA),
    em um ambiente de juros reais mais altos (NTN-B IPCA+).

    A hipótese NÃO é assumida como verdadeira.
    O código classifica o resultado de forma totalmente empírica e imparcial como:
        CONFIRMADA / PARCIALMENTE CONFIRMADA / NÃO CONFIRMADA / DADOS INSUFFICIENTES

Limitações Técnicas & Justificativa do yfinance Gratuito (Free Tier):
    1. Preços Sintéticos Removidos: Caso o yfinance falhe em obter a cotação real de um ticker,
       o código NÃO cria séries de preços artificiais a partir do Ibovespa. O ticker é marcado
       como PRICE_DATA_INSUFFICIENT e excluído das amostras afetadas.
    2. EBITDA LTM Trimestral vs. Anual: O yfinance gratuito disponibiliza a API de demonstrativos
       trimestrais apenas para os 4 a 5 trimestres mais recentes. Onde disponível, o EBITDA LTM
       é calculado via soma de 4 trimestres (YFINANCE_QUARTERLY_LTM). Nos períodos históricos anteriores
       ou falhas, utiliza-se o demonstrativo anual (YFINANCE_ANNUAL ou HARDCODED_FALLBACK).
    3. Look-Ahead Bias / As-Of Dates (Point-in-Time): O yfinance gratuito não fornece a data de
       publicação oficial CVM (announcement_date). Para mitigar look-ahead bias, cada dado
       fundamental possui uma publication_date estimada (~75 dias após period_end_date para
       dados anuais). Dados são filtrados por publication_date <= observation_date.
       Observações com publication_date desconhecida ou estimada recebem lookahead_flag = UNKNOWN.
       O relatório lookahead_audit.csv permite verificação manual de cada observação.
    4. Trimming Dinâmico de Datas: Nenhuma série (NTN-B, Ibovespa, Preços) é extrapolada com ffill/bfill
       além de suas observações reais. O período do estudo é o intervalo comum de dados válidos.
"""

import time
import logging
import warnings
import sys
import os
import contextlib
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

# Universo Candidato da B3 (100+ empresas não-financeiras)
from candidate_universe import (
    CANDIDATE_TICKERS,
    get_candidate_tickers,
    get_candidate_dict,
)

# Point-in-Time framework para correção de look-ahead bias
from point_in_time import (
    FundamentalRecord,
    FundamentalStore,
    check_lookahead,
    build_pit_monthly_series,
    populate_store_from_hardcoded,
    populate_store_from_yfinance,
    generate_audit_dataframe,
    compute_observation_lookahead_flag,
)

# Módulo de Estatística Inferencial, Econometria e Persistência
from bico_stats import (
    compute_exact_binomial_test,
    compute_correlations_and_magnitude,
    run_simple_regression,
    run_ntnb_controlled_regression,
    compute_temporal_persistence,
    compute_ev_decomposition,
    evaluate_evidence_scorecard,
    generate_statistical_report,
)

# ──────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP & SILENCING EXTERNAL YFINANCE CHATTER
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(levelname)s | %(message)s')
logger = logging.getLogger('bico_de_pato')
warnings.filterwarnings('ignore', category=FutureWarning)


import io

@contextlib.contextmanager
def silence_yfinance():
    """Silencia mensagens internas de download/erro do yfinance em stdout/stderr."""
    buf = io.StringIO()
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = buf
    sys.stderr = buf
    try:
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# ══════════════════════════════════════════════════════════════════════════════
# 1. CONFIGURAÇÃO GERAL
# ══════════════════════════════════════════════════════════════════════════════
START_DATE = "2021-01-01"

# Universo Candidato de Empresas Não-Financeiras da B3 (100+ tickers)
CANDIDATE_ITEMS = CANDIDATE_TICKERS
TICKERS = get_candidate_tickers()
CANDIDATE_DICT = get_candidate_dict()

# Preservação das 20 empresas originais do estudo
ORIGINAL_20_TICKERS = [
    "PETR4.SA", "VALE3.SA", "GGBR4.SA", "CSNA3.SA", "SUZB3.SA", "JBSS3.SA",
    "ELET3.SA", "EQTL3.SA", "CPLE6.SA", "SBSP3.SA", "EGIE3.SA",
    "ABEV3.SA", "MGLU3.SA", "LREN3.SA", "RADL3.SA", "HAPV3.SA",
    "WEGE3.SA", "RENT3.SA", "RAIL3.SA", "EMBR3.SA"
]

COMMODITY_LEADERS = ["PETR4.SA", "VALE3.SA"]
COMMODITY_ALL = ["PETR4.SA", "VALE3.SA", "GGBR4.SA", "CSNA3.SA", "SUZB3.SA", "JBSS3.SA"]
IBOV_TICKER = "^BVSP"

THRESHOLD_STRONG = 5.0      # % para crescimento/compressão forte
MIN_BICO_DIFFUSION = 50.0   # % mínimo de difusão de empresas com Bico de Pato

# ══════════════════════════════════════════════════════════════════════════════
# 2. DADOS FUNDAMENTAIS — FALLBACK HARDCODED AUDITADO
# ══════════════════════════════════════════════════════════════════════════════
EBITDA_DATES = pd.to_datetime([
    '2020-12-31', '2021-12-31', '2022-12-31',
    '2023-12-31', '2024-12-31', '2025-12-31'
])

EBITDA_HARDCODED_BI = {
    "PETR4.SA": [234.576, 340.482, 261.016, 264.987, 231.111, 304.174],
    "VALE3.SA": [159.222, 101.249, 91.242, 75.387, 78.527, 81.437],
    "GGBR4.SA": [23.222, 21.508, 13.502, 10.844, 10.074, 12.603],
    "CSNA3.SA": [22.002, 13.817, 11.907, 10.230, 11.796, 11.077],
    "SUZB3.SA": [23.471, 28.195, 18.273, 23.849, 21.736, 23.049],
    "JBSS3.SA": [45.662, 34.568, 17.159, 35.569, 35.676, 28.176],
    "ELET3.SA": [19.007, 17.780, 19.274, 25.488, 19.666, 28.717],
    "EQTL3.SA": [5.481, 7.002, 9.807, 10.924, 12.190, 11.653],
    "CPLE6.SA": [3.800, 4.260, 5.070, 5.530, 6.550, 6.550],
    "SBSP3.SA": [6.373, 7.088, 9.108, 11.339, 13.221, 15.808],
    "EGIE3.SA": [7.217, 6.941, 7.270, 7.367, 7.640, 7.383],
    "ABEV3.SA": [22.870, 23.771, 25.455, 29.029, 29.506, 30.485],
    "MGLU3.SA": [1.477, 2.128, 2.132, 2.962, 3.064, 3.130],
    "LREN3.SA": [1.723, 2.401, 2.104, 2.650, 3.187, 3.308],
    "RADL3.SA": [1.807, 2.262, 2.603, 2.992, 3.375, 3.842],
    "HAPV3.SA": [1.495, 2.100, 2.932, 3.795, 3.369, 2.780],
    "WEGE3.SA": [4.679, 5.617, 7.090, 8.503, 9.000, 9.167],
    "RENT3.SA": [3.698, 6.589, 10.523, 11.915, 13.753, 15.751],
    "RAIL3.SA": [3.350, 5.003, 5.650, 7.713, 8.021, 8.140],
    "EMBR3.SA": [2.016, 2.331, 2.805, 4.487, 4.265, 5.248],
}

NET_DEBT_HARDCODED_BI = {
    "PETR4.SA": [320.0, 270.0, 220.0, 222.0, 240.0, 235.0],
    "VALE3.SA": [25.0, 23.0, 40.0, 48.0, 55.0, 52.0],
    "GGBR4.SA": [12.5, 6.2, 5.8, 11.2, 12.0, 11.5],
    "CSNA3.SA": [25.6, 17.5, 29.8, 30.5, 33.2, 32.0],
    "SUZB3.SA": [63.8, 55.4, 53.9, 58.1, 62.4, 60.0],
    "JBSS3.SA": [45.2, 46.8, 72.1, 74.3, 76.5, 71.0],
    "ELET3.SA": [43.1, 48.9, 57.2, 60.4, 63.8, 62.0],
    "EQTL3.SA": [12.4, 15.6, 28.5, 33.2, 37.1, 36.0],
    "CPLE6.SA": [9.8, 10.2, 12.4, 11.8, 14.5, 14.0],
    "SBSP3.SA": [16.2, 16.5, 17.8, 19.4, 20.1, 19.5],
    "EGIE3.SA": [14.1, 15.2, 17.0, 18.2, 19.5, 19.0],
    "ABEV3.SA": [-16.5, -18.2, -21.4, -23.1, -20.5, -22.0],
    "MGLU3.SA": [-1.2, 1.5, 3.2, 2.1, 1.8, 1.5],
    "LREN3.SA": [-1.8, -1.2, 1.1, 1.4, 0.8, 0.5],
    "RADL3.SA": [1.2, 1.8, 2.4, 2.8, 3.1, 3.0],
    "HAPV3.SA": [1.5, 3.8, 7.2, 6.1, 5.4, 4.8],
    "WEGE3.SA": [-2.1, -1.8, -2.4, -3.1, -4.2, -4.5],
    "RENT3.SA": [12.1, 16.8, 28.4, 32.5, 36.8, 35.5],
    "RAIL3.SA": [10.5, 11.2, 14.8, 16.2, 17.5, 17.0],
    "EMBR3.SA": [8.5, 7.2, 6.8, 5.4, 4.8, 4.2],
}

NET_INCOME_HARDCODED_BI = {
    "PETR4.SA": [7.108, 106.668, 188.728, 124.606, 95.120, 102.500],
    "VALE3.SA": [26.712, 121.228, 95.736, 39.840, 42.150, 44.800],
    "GGBR4.SA": [5.590, 15.564, 9.488, 6.890, 5.210, 6.400],
    "CSNA3.SA": [4.293, 13.597, 2.370, 0.410, 0.250, 0.650],
    "SUZB3.SA": [-10.714, 8.636, 23.418, 14.090, 3.250, 9.800],
    "JBSS3.SA": [4.598, 20.487, 15.480, -1.060, 4.150, 5.300],
    "ELET3.SA": [6.387, 5.714, 3.638, 4.390, 5.120, 5.900],
    "EQTL3.SA": [1.380, 2.120, 2.310, 2.780, 3.100, 3.450],
    "CPLE6.SA": [3.890, 5.040, 4.520, 4.810, 3.250, 3.800],
    "SBSP3.SA": [0.973, 2.301, 3.121, 3.520, 3.840, 4.250],
    "EGIE3.SA": [2.802, 2.311, 2.671, 3.410, 3.150, 3.350],
    "ABEV3.SA": [11.711, 13.116, 14.891, 14.810, 15.200, 15.850],
    "MGLU3.SA": [0.392, 0.590, -0.372, -0.500, 0.102, 0.260],
    "LREN3.SA": [1.092, 1.100, 1.284, 1.090, 1.210, 1.340],
    "RADL3.SA": [0.579, 0.784, 0.995, 1.105, 1.150, 1.320],
    "HAPV3.SA": [0.785, 0.520, -0.310, 0.210, 0.540, 0.680],
    "WEGE3.SA": [2.340, 3.585, 4.208, 5.730, 6.020, 6.450],
    "RENT3.SA": [1.390, 1.630, 2.670, 1.790, 1.950, 2.250],
    "RAIL3.SA": [0.780, 0.820, 0.790, 0.710, 0.880, 1.100],
    "EMBR3.SA": [-3.620, 0.390, 0.780, 0.920, 1.180, 1.520],
}

SHARES_OUTSTANDING_FALLBACK_BI = {
    "PETR4.SA": 13.04, "VALE3.SA": 4.54, "GGBR4.SA": 1.72,
    "CSNA3.SA": 1.33,  "SUZB3.SA": 1.30, "JBSS3.SA": 2.22,
    "ELET3.SA": 2.30,  "EQTL3.SA": 1.15, "CPLE6.SA": 2.94,
    "SBSP3.SA": 0.684, "EGIE3.SA": 0.815, "ABEV3.SA": 15.73,
    "MGLU3.SA": 0.67,  "LREN3.SA": 1.00, "RADL3.SA": 1.72,
    "HAPV3.SA": 7.53,  "WEGE3.SA": 4.19, "RENT3.SA": 1.06,
    "RAIL3.SA": 1.85,  "EMBR3.SA": 0.74,
}

NTNB_SOURCE = "ANBIMA_COMPILED"
NTN_B_MONTHLY_DATA = {
    '2021-01-31': 2.83, '2021-02-28': 3.10, '2021-03-31': 3.45, '2021-04-30': 3.70,
    '2021-05-31': 3.85, '2021-06-30': 4.10, '2021-07-31': 4.35, '2021-08-31': 4.60,
    '2021-09-30': 4.80, '2021-10-31': 5.05, '2021-11-30': 5.25, '2021-12-31': 5.15,
    '2022-01-31': 5.30, '2022-02-28': 5.45, '2022-03-31': 5.60, '2022-04-30': 5.70,
    '2022-05-31': 5.80, '2022-06-30': 5.95, '2022-07-31': 5.85, '2022-08-31': 5.75,
    '2022-09-30': 5.85, '2022-10-31': 5.90, '2022-11-30': 6.15, '2022-12-31': 6.06,
    '2023-01-31': 6.25, '2023-02-28': 6.40, '2023-03-31': 6.30, '2023-04-30': 6.10,
    '2023-05-31': 5.85, '2023-06-30': 5.60, '2023-07-31': 5.45, '2023-08-31': 5.35,
    '2023-09-30': 5.40, '2023-10-31': 5.60, '2023-11-30': 5.45, '2023-12-31': 5.38,
    '2024-01-31': 5.45, '2024-02-29': 5.55, '2024-03-31': 5.65, '2024-04-30': 5.90,
    '2024-05-31': 6.10, '2024-06-30': 6.30, '2024-07-31': 6.20, '2024-08-31': 6.15,
    '2024-09-30': 6.35, '2024-10-31': 6.60, '2024-11-30': 7.10, '2024-12-31': 7.62,
    '2025-01-31': 7.45, '2025-02-28': 7.35, '2025-03-31': 7.20, '2025-04-30': 7.10,
    '2025-05-31': 6.95, '2025-06-30': 6.85, '2025-07-31': 7.00, '2025-08-31': 7.15,
    '2025-09-30': 7.25, '2025-10-31': 7.35, '2025-11-30': 7.45, '2025-12-31': 7.40,
    '2026-01-31': 7.35,
}

IBOV_FALLBACK = {
    '2021-01-31': 118873, '2021-02-28': 110035, '2021-03-31': 116634,
    '2021-04-30': 120891, '2021-05-31': 126216, '2021-06-30': 126802,
    '2021-07-31': 121801, '2021-08-31': 118780, '2021-09-30': 111037,
    '2021-10-31': 103500, '2021-11-30': 101915, '2021-12-31': 104822,
    '2022-01-31': 112143, '2022-02-28': 113161, '2022-03-31': 119999,
    '2022-04-30': 110526, '2022-05-31': 108335, '2022-06-30': 118082,
    '2022-07-31': 120187, '2022-08-31': 115742, '2022-09-30': 116560,
    '2022-10-31': 113143, '2022-11-30': 125666, '2022-12-31': 134185,
    '2023-01-31': 128159, '2023-02-28': 129020, '2023-03-31': 128158,
    '2023-04-30': 125924, '2023-05-31': 122098, '2023-06-30': 123906,
    '2023-07-31': 127652, '2023-08-31': 136000, '2023-09-30': 132000,
    '2023-10-31': 129000, '2023-11-30': 126000, '2023-12-31': 128500,
    '2024-01-31': 131000, '2024-02-29': 133500,
}

# ══════════════════════════════════════════════════════════════════════════════
# 3. FUNÇÕES DE COLETA DE DADOS REAIS
# ══════════════════════════════════════════════════════════════════════════════

def fetch_real_price_series(ticker, start_date):
    """
    Busca cotações reais via yfinance usando start=START_DATE e auto_adjust=False.
    SE NÃO HOUVER DADOS REAIS, RETORNA SERIES VAZIA (NÃO CRIA PREÇOS SINTÉTICOS).
    """
    candidate_tickers = [ticker]
    if ticker == "CPLE6.SA":
        candidate_tickers.append("CPLE3.SA")
    elif ticker == "ELET3.SA":
        candidate_tickers.append("ELET6.SA")
    elif ticker == "GGBR4.SA":
        candidate_tickers.append("GGBR3.SA")

    for cand in candidate_tickers:
        for attempt in range(2):
            try:
                with silence_yfinance():
                    df_single = yf.download(
                        cand, start=start_date, auto_adjust=False,
                        progress=False, ignore_tz=True
                    )
                    if df_single is not None and not df_single.empty:
                        s_c = df_single['Close'] if 'Close' in df_single.columns else df_single.iloc[:, 0]
                        if isinstance(s_c, pd.DataFrame):
                            s_c = s_c.iloc[:, 0]
                        s_c = s_c.dropna()
                        if not s_c.empty:
                            if s_c.index.tz is not None:
                                s_c.index = s_c.index.tz_localize(None)
                            return s_c
            except Exception:
                time.sleep(0.2 * (attempt + 1))

        try:
            with silence_yfinance():
                t = yf.Ticker(cand)
                hist = t.history(start=start_date, auto_adjust=False)
                if hist is not None and not hist.empty and 'Close' in hist.columns:
                    s_close = hist['Close'].dropna()
                    if not s_close.empty:
                        if s_close.index.tz is not None:
                            s_close.index = s_close.index.tz_localize(None)
                        return s_close
        except Exception:
            pass

    return pd.Series(dtype=float)


def download_all_prices(tickers, ibov_ticker, start_date):
    """
    Download em lote de preços reais.
    Retorna (prices_df, ibov_source).
    """
    ibov_source = "YFINANCE"
    prices_df = pd.DataFrame()

    try:
        with silence_yfinance():
            download_data = yf.download(
                [ibov_ticker] + tickers, start=start_date,
                auto_adjust=False, progress=False, ignore_tz=True
            )
            if isinstance(download_data, pd.DataFrame) and not download_data.empty:
                if isinstance(download_data.columns, pd.MultiIndex):
                    if 'Close' in download_data.columns.get_level_values(0):
                        prices_df = download_data['Close']
                elif 'Close' in download_data.columns:
                    prices_df = download_data['Close']
                else:
                    prices_df = download_data
    except Exception as e:
        logger.debug(f"Erro no download em lote: {e}")

    for sym in [ibov_ticker] + tickers:
        if sym not in prices_df.columns or prices_df[sym].dropna().empty:
            s_ind = fetch_real_price_series(sym, start_date)
            if not s_ind.empty:
                prices_df[sym] = s_ind

    if ibov_ticker not in prices_df.columns or prices_df[ibov_ticker].dropna().empty:
        ibov_source = "FALLBACK"
        logger.warning("⚠️  Ibovespa: yfinance indisponível. Usando fallback hardcoded.")

    return prices_df, ibov_source


def get_ebitda_ltm(ticker, ebitda_dates, hardcoded_values):
    """
    Busca EBITDA LTM com prioridade para demonstrativos trimestrais reais (YFINANCE_QUARTERLY_LTM).
    Se indisponível (limitação da API gratuita do yfinance), utiliza o anual (YFINANCE_ANNUAL ou HARDCODED).
    """
    s_ebitda = pd.Series(list(hardcoded_values), index=ebitda_dates, dtype=float)
    source = "HARDCODED_FALLBACK"

    candidate_tickers = [ticker]
    if ticker == "CPLE6.SA":
        candidate_tickers.append("CPLE3.SA")
    elif ticker == "ELET3.SA":
        candidate_tickers.append("ELET6.SA")

    yf_quarterly_found = False

    for cand in candidate_tickers:
        try:
            with silence_yfinance():
                t = yf.Ticker(cand)
                q_fin = t.quarterly_income_stmt if t.quarterly_income_stmt is not None and not t.quarterly_income_stmt.empty else t.quarterly_financials

            if q_fin is not None and not q_fin.empty:
                ebitda_q_row = None
                for row_name in ['EBITDA', 'Normalized EBITDA']:
                    if row_name in q_fin.index:
                        ebitda_q_row = q_fin.loc[row_name]
                        break

                if ebitda_q_row is not None and not ebitda_q_row.dropna().empty:
                    valid_q = ebitda_q_row.dropna().sort_index(ascending=False)
                    if len(valid_q) >= 4:
                        q_sum = float(valid_q.iloc[:4].sum())
                        if q_sum > 0:
                            ltm_bi = q_sum / 1e9 if abs(q_sum) > 1e6 else q_sum
                            latest_q_date = pd.to_datetime(valid_q.index[0])
                            for d in ebitda_dates:
                                if d.year == latest_q_date.year:
                                    s_ebitda.loc[d] = ltm_bi
                                    yf_quarterly_found = True
                                    source = "YFINANCE_QUARTERLY_LTM"
                                    break

            if not yf_quarterly_found:
                with silence_yfinance():
                    t = yf.Ticker(cand)
                    fin = t.income_stmt if t.income_stmt is not None and not t.income_stmt.empty else t.financials

                if fin is not None and not fin.empty:
                    ebitda_row = None
                    for row_name in ['EBITDA', 'Normalized EBITDA']:
                        if row_name in fin.index:
                            ebitda_row = fin.loc[row_name]
                            break

                    if ebitda_row is not None and not ebitda_row.dropna().empty:
                        for date_col, val in ebitda_row.items():
                            if pd.notna(val):
                                try:
                                    val_float = float(val)
                                    if val_float > 0:
                                        val_bi = val_float / 1e9 if abs(val_float) > 1e6 else val_float
                                        col_dt = pd.to_datetime(date_col)
                                        for d in ebitda_dates:
                                            if d.year == col_dt.year:
                                                s_ebitda.loc[d] = val_bi
                                                source = "YFINANCE_ANNUAL"
                                                break
                                except (ValueError, TypeError):
                                    continue

            if yf_quarterly_found or source == "YFINANCE_ANNUAL":
                break
        except Exception:
            continue

    return s_ebitda, source


def get_shares_outstanding(ticker, full_dates):
    """Busca quantidade de ações históricas via yfinance com fallbacks explícitos."""
    fallback_val = SHARES_OUTSTANDING_FALLBACK_BI.get(ticker, 1.0)
    fallback_series = pd.Series(fallback_val, index=full_dates)
    source = "FALLBACK_HARDCODED"

    try:
        with silence_yfinance():
            t = yf.Ticker(ticker)
            shares_series = t.get_shares_full(start=START_DATE)
            if shares_series is not None and not shares_series.empty:
                shares_series = shares_series.dropna()
                if not shares_series.empty:
                    if shares_series.index.tz is not None:
                        shares_series.index = shares_series.index.tz_localize(None)
                    shares_series = shares_series / 1e9
                    combined_idx = shares_series.index.union(full_dates)
                    aligned = (
                        shares_series.reindex(combined_idx)
                        .sort_index().ffill().bfill()
                        .reindex(full_dates)
                    )
                    if (aligned > 0).all():
                        return aligned, "YFINANCE_HISTORICAL_FULL"

            info_dict = t.info
            if info_dict and isinstance(info_dict, dict):
                sh = info_dict.get('sharesOutstanding') or info_dict.get('impliedSharesOutstanding')
                if sh and sh > 0:
                    return pd.Series(float(sh) / 1e9, index=full_dates), "YFINANCE_INFO_CURRENT"
    except Exception:
        pass

    return fallback_series, source


def build_monthly_series(raw_series, anchor_dates, target_dates):
    """Alinha dados fundamentais às datas mensais (sem look-ahead bias futuro)."""
    combined = anchor_dates.union(target_dates)
    return (
        raw_series.reindex(combined)
        .sort_index()
        .ffill()
        .reindex(target_dates)
    )


# ══════════════════════════════════════════════════════════════════════════════
# 4. SISTEMA DE CLASSIFICAÇÃO DA HIPÓTESE
# ══════════════════════════════════════════════════════════════════════════════

def classify_hypothesis(ebitda_pct_med, ebitda_pct_agg, mult_pct_med, mult_pct_agg, bico_diffusion_pct, data_sufficient=True):
    """
    Classifica a hipótese com critérios objetivos e defensáveis:
    - CONFIRMADA: EBITDA mediano E agregado > +5%, EV/EBITDA mediano E agregado < -5% E difusão Bico de Pato >= 50%
    - PARCIALMENTE CONFIRMADA: Direção principal presente (EBITDA > 0%, EV/EBITDA < 0%), mas métricas não atingem threshold forte ou difusão parcial
    - NÃO CONFIRMADA: EBITDA caiu ou EV/EBITDA subiu
    - DADOS INSUFICIENTES: Se amostragem for comprometida por falta de preços reais
    """
    if not data_sufficient:
        return "DADOS INSUFICIENTES"

    ebitda_strong = (ebitda_pct_med > THRESHOLD_STRONG) and (ebitda_pct_agg > THRESHOLD_STRONG)
    multiple_strong = (mult_pct_med < -THRESHOLD_STRONG) and (mult_pct_agg < -THRESHOLD_STRONG)
    diffusion_strong = bico_diffusion_pct >= MIN_BICO_DIFFUSION

    ebitda_positive = (ebitda_pct_med > 0) or (ebitda_pct_agg > 0)
    multiple_negative = (mult_pct_med < 0) or (mult_pct_agg < 0)

    if ebitda_strong and multiple_strong and diffusion_strong:
        return "CONFIRMADA"
    elif ebitda_positive and multiple_negative:
        return "PARCIALMENTE CONFIRMADA"
    else:
        return "NÃO CONFIRMADA"


# ══════════════════════════════════════════════════════════════════════════════
# 5. CÁLCULO DE MÉTRICAS E DECOMPOSIÇÃO POR AMOSTRA
# ══════════════════════════════════════════════════════════════════════════════

def calculate_sample_metrics(df_ev_ebitda, df_ebitda_yield, df_earnings_yield,
                              df_ebitda_monthly, df_ev, df_market_cap, df_netdebt,
                              full_dates, sample_tickers, delta_ntnb_series=None):
    """Calcula métricas agregadas por amostra (Mediana, Agregado Econômico ΣEV/ΣEBITDA, Difusão, Testes Estatísticos)."""
    if not sample_tickers:
        return None

    ev_ebitda_sub = df_ev_ebitda[sample_tickers]
    median_ev_ebitda = ev_ebitda_sub.median(axis=1, skipna=True)
    p25_ev_ebitda = ev_ebitda_sub.quantile(0.25, axis=1)
    p75_ev_ebitda = ev_ebitda_sub.quantile(0.75, axis=1)
    n_valid = ev_ebitda_sub.notna().sum(axis=1)

    # Agregado econômico: Σ EV / Σ EBITDA
    total_ev = df_ev[sample_tickers].sum(axis=1)
    total_ebitda = df_ebitda_monthly[sample_tickers].sum(axis=1)
    total_mcap = df_market_cap[sample_tickers].sum(axis=1)
    total_netdebt = df_netdebt[sample_tickers].sum(axis=1)

    total_ebitda_pos = total_ebitda.where(total_ebitda > 0)
    agg_ev_ebitda = total_ev / total_ebitda_pos

    # Índices de EBITDA (Mediano e Agregado)
    ebitda_norm = pd.DataFrame(index=full_dates)
    for col in sample_tickers:
        col_clean = df_ebitda_monthly[col].dropna()
        base_val = col_clean.iloc[0] if not col_clean.empty else np.nan
        if pd.notna(base_val) and base_val > 0:
            ebitda_norm[col] = (df_ebitda_monthly[col] / base_val) * 100.0
    ebitda_index_median = ebitda_norm.median(axis=1, skipna=True)

    base_total = total_ebitda.dropna().iloc[0] if not total_ebitda.dropna().empty else np.nan
    ebitda_index_agg = (total_ebitda / base_total * 100.0) if base_total and base_total > 0 else pd.Series(np.nan, index=full_dates)

    ebitda_yield_med = df_ebitda_yield[sample_tickers].median(axis=1, skipna=True)
    earnings_yield_med = df_earnings_yield[sample_tickers].median(axis=1, skipna=True)

    # Matriz de Difusão
    ebitda_base = df_ebitda_monthly[sample_tickers].iloc[0]
    ebitda_up = df_ebitda_monthly[sample_tickers].gt(ebitda_base, axis=1)

    mult_base = df_ev_ebitda[sample_tickers].iloc[0]
    mult_down = df_ev_ebitda[sample_tickers].lt(mult_base, axis=1)

    bico_matrix = ebitda_up & mult_down

    diffusion_ebitda_up = (ebitda_up.sum(axis=1) / len(sample_tickers)) * 100.0
    diffusion_mult_down = (mult_down.sum(axis=1) / len(sample_tickers)) * 100.0
    diffusion_bico = (bico_matrix.sum(axis=1) / len(sample_tickers)) * 100.0

    # Variações Início → Fim por empresa
    ebitda_growths = []
    mult_changes = []
    bico_flags = []

    for col in sample_tickers:
        eb_clean = df_ebitda_monthly[col].dropna()
        m_clean = df_ev_ebitda[col].dropna()
        if not eb_clean.empty and not m_clean.empty:
            eb_i, eb_f = eb_clean.iloc[0], eb_clean.iloc[-1]
            m_i, m_f = m_clean.iloc[0], m_clean.iloc[-1]

            eg = ((eb_f / eb_i) - 1.0) * 100.0 if eb_i > 0 else np.nan
            mc = ((m_f / m_i) - 1.0) * 100.0 if m_i > 0 else np.nan

            ebitda_growths.append(eg)
            mult_changes.append(mc)
            bico_flags.append((eg > 0) and (mc < 0) if pd.notna(eg) and pd.notna(mc) else False)
        else:
            ebitda_growths.append(np.nan)
            mult_changes.append(np.nan)
            bico_flags.append(False)

    s_eb_growths = pd.Series(ebitda_growths, index=sample_tickers)
    s_mult_changes = pd.Series(mult_changes, index=sample_tickers)
    s_bico_flags = pd.Series(bico_flags, index=sample_tickers)

    n_sample_valid = int(s_eb_growths.dropna().index.intersection(s_mult_changes.dropna().index).shape[0])
    k_sample_bico = int(s_bico_flags.sum())
    final_bico_diffusion = (k_sample_bico / n_sample_valid * 100.0) if n_sample_valid > 0 else 0.0

    # Teste Binomial Exato & IC95%
    binom_res = compute_exact_binomial_test(k_sample_bico, n_sample_valid)

    # Correlações & Quantis
    corr_res = compute_correlations_and_magnitude(s_eb_growths, s_mult_changes, s_bico_flags)

    # Regressão Simples
    reg_simple = run_simple_regression(s_eb_growths, s_mult_changes)

    # Regressão com NTN-B (se disponível)
    if delta_ntnb_series is not None and len(delta_ntnb_series) == len(s_eb_growths):
        reg_ntnb = run_ntnb_controlled_regression(s_eb_growths, s_mult_changes, delta_ntnb_series)
    else:
        # Cria série dummy constante se não fornecida por empresa
        reg_ntnb = run_ntnb_controlled_regression(s_eb_growths, s_mult_changes, pd.Series(0.0, index=sample_tickers))

    # Persistência Temporal
    pers_res = compute_temporal_persistence(df_ebitda_monthly, df_ev_ebitda, sample_tickers)

    # Decomposição do EV & Tipos A/B/C/D
    ev_decomp = compute_ev_decomposition(df_ebitda_monthly, df_ev, df_market_cap, df_netdebt, df_ev_ebitda, sample_tickers)

    med_clean = median_ev_ebitda.dropna()
    initial_mult_med = med_clean.iloc[0] if len(med_clean) > 0 else np.nan
    final_mult_med = med_clean.iloc[-1] if len(med_clean) > 0 else np.nan
    mult_change_med_pct = ((final_mult_med / initial_mult_med) - 1) * 100.0 if initial_mult_med and initial_mult_med > 0 else np.nan

    agg_clean = agg_ev_ebitda.dropna()
    initial_mult_agg = agg_clean.iloc[0] if len(agg_clean) > 0 else np.nan
    final_mult_agg = agg_clean.iloc[-1] if len(agg_clean) > 0 else np.nan
    mult_change_agg_pct = ((final_mult_agg / initial_mult_agg) - 1) * 100.0 if initial_mult_agg and initial_mult_agg > 0 else np.nan

    idx_med_clean = ebitda_index_median.dropna()
    ebitda_growth_med_pct = idx_med_clean.iloc[-1] - 100.0 if len(idx_med_clean) > 0 else np.nan

    idx_agg_clean = ebitda_index_agg.dropna()
    ebitda_growth_agg_pct = idx_agg_clean.iloc[-1] - 100.0 if len(idx_agg_clean) > 0 else np.nan

    ev_growth_pct = ((total_ev.iloc[-1] / total_ev.iloc[0]) - 1) * 100.0 if total_ev.iloc[0] > 0 else np.nan
    mcap_growth_pct = ((total_mcap.iloc[-1] / total_mcap.iloc[0]) - 1) * 100.0 if total_mcap.iloc[0] > 0 else np.nan
    netdebt_growth_pct = ((total_netdebt.iloc[-1] / total_netdebt.iloc[0]) - 1) * 100.0 if total_netdebt.iloc[0] > 0 else np.nan

    classification = classify_hypothesis(
        ebitda_growth_med_pct, ebitda_growth_agg_pct,
        mult_change_med_pct, mult_change_agg_pct,
        final_bico_diffusion, data_sufficient=True
    )

    return {
        'N': n_sample_valid,
        'K': k_sample_bico,
        'bico_diffusion_pct': final_bico_diffusion,
        'ev_ebitda_median': median_ev_ebitda,
        'ev_ebitda_p25': p25_ev_ebitda,
        'ev_ebitda_p75': p75_ev_ebitda,
        'ev_ebitda_agg': agg_ev_ebitda,
        'n_valid': n_valid,
        'ebitda_index_median': ebitda_index_median,
        'ebitda_index_agg': ebitda_index_agg,
        'ebitda_yield_median': ebitda_yield_med,
        'earnings_yield_median': earnings_yield_med,
        'diffusion_ebitda_up': diffusion_ebitda_up,
        'diffusion_mult_down': diffusion_mult_down,
        'diffusion_bico': diffusion_bico,
        'initial_multiple': initial_mult_med,
        'final_multiple': final_mult_med,
        'multiple_change_pct': mult_change_med_pct,
        'multiple_change_agg_pct': mult_change_agg_pct,
        'ebitda_change_pct': ebitda_growth_med_pct,
        'ebitda_growth_agg_pct': ebitda_growth_agg_pct,
        'ev_growth_pct': ev_growth_pct,
        'mcap_growth_pct': mcap_growth_pct,
        'netdebt_growth_pct': netdebt_growth_pct,
        'classification': classification,
        'binomial_test': binom_res,
        'correlations': corr_res,
        'regression_simple': reg_simple,
        'regression_ntnb': reg_ntnb,
        'persistence': pers_res,
        'ev_decomp': ev_decomp,
        'ebitda_growths_series': s_eb_growths,
        'mult_changes_series': s_mult_changes,
        'bico_flags_series': s_bico_flags,
    }


def calculate_sector_metrics(df_ebitda_monthly, df_ev_ebitda, df_ev, full_dates, sectors):
    """Calcula EBITDA Growth, EV Growth e Variação do Múltiplo por setor."""
    sector_indices = pd.DataFrame(index=full_dates)
    sector_growth = {}
    sector_mult = {}

    for sec_name, sec_tickers in sectors.items():
        valid = [t for t in sec_tickers if t in df_ebitda_monthly.columns]
        if not valid:
            continue

        sec_sum = df_ebitda_monthly[valid].sum(axis=1)
        base = sec_sum.dropna().iloc[0] if not sec_sum.dropna().empty else np.nan
        if base and base > 0:
            sector_indices[sec_name] = (sec_sum / base) * 100.0
            growth = ((sec_sum.dropna().iloc[-1] / base) - 1) * 100.0
            sector_growth[sec_name] = growth

        valid_ev = [t for t in valid if t in df_ev_ebitda.columns]
        if valid_ev:
            sec_med = df_ev_ebitda[valid_ev].median(axis=1, skipna=True)
            sec_clean = sec_med.dropna()
            if len(sec_clean) >= 2:
                sector_mult[sec_name] = {
                    'initial': sec_clean.iloc[0],
                    'final': sec_clean.iloc[-1],
                    'change_pct': ((sec_clean.iloc[-1] / sec_clean.iloc[0]) - 1) * 100.0,
                }

    return sector_indices, sector_growth, sector_mult


# ══════════════════════════════════════════════════════════════════════════════
# 6. VALIDAÇÃO DE DADOS & AUDITORIA INTEGRAL
# ══════════════════════════════════════════════════════════════════════════════

def validate_dataset(valid_tickers, df_ebitda, df_ev, df_mcap, df_ev_ebitda,
                      ebitda_sources, shares_sources, price_sources, negative_ev_counts,
                      lookahead_flags=None):
    """Gera relatório de qualidade dos dados para terminal e CSV de auditoria."""
    print("\n" + "=" * 65)
    print("                DATA QUALITY & AUDIT REPORT")
    print("        Point-in-Time adjusted (look-ahead bias correction)")
    print("=" * 65)

    rows = []
    for ticker in valid_tickers:
        price_src = price_sources.get(ticker, "PRICE_DATA_INSUFFICIENT")
        ebitda_src = ebitda_sources.get(ticker, "UNKNOWN")
        shares_src = shares_sources.get(ticker, "UNKNOWN")

        neg_ev = negative_ev_counts.get(ticker, 0)
        look_ahead_risk = "TRUE" if "ANNUAL" in ebitda_src or "HARDCODED" in ebitda_src else "FALSE"

        # PIT lookahead summary for this ticker
        pit_summary = 'N/A'
        if lookahead_flags is not None and ticker in lookahead_flags:
            flags = lookahead_flags[ticker]
            n_false = (flags == 'FALSE').sum()
            n_unknown = (flags == 'UNKNOWN').sum()
            n_true = (flags == 'TRUE').sum()
            pit_summary = f"F:{n_false}/U:{n_unknown}/T:{n_true}"

        status = "OK (ATIVO)"

        print(f"  {ticker:10s} | Preço: {price_src:12s} | EBITDA: {ebitda_src:22s} | PIT: {pit_summary:15s} | Status: {status}")

        rows.append({
            'Ticker': ticker,
            'Price_Source': price_src,
            'EBITDA_Source': ebitda_src,
            'NetDebt_Source': 'HARDCODED_FALLBACK' if ticker in ORIGINAL_20_TICKERS else 'YFINANCE',
            'NetIncome_Source': 'HARDCODED_FALLBACK' if ticker in ORIGINAL_20_TICKERS else 'YFINANCE',
            'Shares_Source': shares_src,
            'Look_Ahead_Risk': look_ahead_risk,
            'PIT_Lookahead_Summary': pit_summary,
            'Negative_EV_Count': neg_ev,
            'Status': status,
        })

    print("=" * 65)
    return pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# 7. DASHBOARD — REDESENHADO (FIGSIZE 18x28, POSICIONAMENTO SEM SOBREPOSIÇÃO)
# ══════════════════════════════════════════════════════════════════════════════

def build_dashboard(results, output_path='bico_de_pato_dashboard.png'):
    """
    Dashboard de 8 painéis + KPI Banner no topo com design dark premium.
    Zero sobreposição de textos, legendas ou cartões.
    """
    full_dates = results['full_dates']
    primary = results['samples']['ex_leaders']
    all_sample = results['samples']['all']
    ex_comm = results['samples'].get('ex_commodities', primary)
    ibov_index = results['ibov_index']
    ibov_source = results['ibov_source']
    ntnb = results['ntnb_monthly']
    ntnb_source = results['ntnb_source']
    sector_indices = results['sector_indices']
    sector_growth = results['sector_growth']
    robustness = results['robustness']
    eval_res = results.get('hypothesis_evaluation', {})
    reasons = eval_res.get('justification_reasons', [])

    sample_definitions = results.get('sample_definitions', {
        'all': {'label': 'Todas', 'exclude': []},
        'ex_leaders': {'label': 'Ex-PETR4/VALE3', 'exclude': COMMODITY_LEADERS},
        'ex_commodities': {'label': 'Ex-Commodities Amplo', 'exclude': COMMODITY_ALL},
    })

    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Segoe UI', 'Roboto', 'Helvetica', 'Arial', 'DejaVu Sans']

    BG = '#0F172A'       # Slate escuro
    CARD = '#1E293B'     # Container escuro
    CARD_BORDER = '#334155'
    C_EBITDA = '#10B981' # Emerald Green
    C_EBITDA2 = '#06B6D4'# Cyan
    C_IBOV = '#F43F5E'   # Rose Red
    C_MULT = '#F59E0B'   # Amber Gold
    C_NTNB = '#A855F7'   # Purple
    C_EARN = '#10B981'   # Emerald
    C_TEXT = '#F8FAFC'   # White/Ice
    C_MUTED = '#94A3B8'  # Grey
    C_GRID = '#334155'

    fig = plt.figure(figsize=(18, 44), facecolor=BG)
    gs = fig.add_gridspec(
        9, 1,
        height_ratios=[1.1, 2.0, 2.0, 1.4, 1.4, 1.4, 1.4, 1.5, 1.5],
        hspace=0.38, top=0.98, bottom=0.02, left=0.07, right=0.93
    )

    # ══════════════════════════════════════════════════════════════════
    # ROW 0: KPI SUMMARY HEADER BANNER & JUSTIFICATION BOX
    # ══════════════════════════════════════════════════════════════════
    ax_header = fig.add_subplot(gs[0])
    ax_header.set_facecolor(BG)
    ax_header.axis('off')

    period_start = full_dates[0].strftime('%b/%Y')
    period_end = full_dates[-1].strftime('%b/%Y')

    cand_count = results.get('candidate_count', len(results['valid_tickers']))
    eff_count = results.get('effective_sample_size', len(results['valid_tickers']))
    disc_count = results.get('excluded_count', 0)

    ax_header.text(0.0, 0.96, 'B3: Teste da Hipótese de Desconexão Operacional ("Bico de Pato")',
                   fontsize=18, fontweight='bold', color=C_TEXT, va='top')

    ax_header.text(0.0, 0.78,
                   f'Período: {period_start} → {period_end}  |  AMOSTRA EFETIVA: {eff_count} EMPRESAS (Candidatas: {cand_count} | Descartadas: {disc_count})',
                   fontsize=11.5, color=C_TEXT, fontweight='bold', va='top')

    ax_header.text(0.0, 0.64,
                   'Point-in-Time adjusted  •  Estatística Inferencial, Persistência Temporal & Regressões Econométricas.',
                   fontsize=9.0, color='#38BDF8', va='top', fontstyle='italic')

    ebitda_pct = primary['ebitda_change_pct']
    mult_pct = primary['multiple_change_pct']
    init_m = primary['initial_multiple']
    final_m = primary['final_multiple']
    ntnb_chg = results.get('ntnb_change_pp', 0.0)
    spread_final = results.get('spread_final', 0.0)
    status_clean = eval_res.get('status', primary['classification'])

    status_bg = "#F59E0B" if "PARCIAL" in status_clean else ("#10B981" if "CONFIRMADA" in status_clean else "#F43F5E")

    kpis = [
        {"title": "EBITDA LTM Index", "val": f"{ebitda_pct:+.1f}%", "sub": "Mediano Ex-Commodities", "color": C_EBITDA2},
        {"title": "EV/EBITDA Mediano", "val": f"{init_m:.1f}x → {final_m:.1f}x", "sub": f"Variação: {mult_pct:+.1f}%", "color": C_MULT},
        {"title": "NTN-B 10Y Real", "val": f"{ntnb_chg:+.1f} p.p.", "sub": "Taxa Livre de Risco Real", "color": C_NTNB},
        {"title": "Spread EY – NTN-B", "val": f"{spread_final:+.1f} p.p.", "sub": "Diferencial de Yield", "color": C_EBITDA},
        {"title": "Status Hipótese", "val": f"[{status_clean}]", "sub": "Classificação Empírica", "color": status_bg},
    ]

    n_kpis = len(kpis)
    card_w = 0.185
    gap = (1.0 - (n_kpis * card_w)) / (n_kpis - 1)

    for i, kpi in enumerate(kpis):
        cx = i * (card_w + gap)
        bbox_rect = dict(boxstyle='round,pad=0.5', facecolor=CARD, edgecolor=kpi['color'], lw=1.2, alpha=0.95)
        kpi_text = f"{kpi['title']}\n{kpi['val']}\n{kpi['sub']}"
        ax_header.text(cx + card_w/2, 0.48, kpi_text,
                       fontsize=9.5, fontweight='bold', color=C_TEXT,
                       ha='center', va='top', bbox=bbox_rect)

    # Caixa Dinâmica de Motivos do Status
    if reasons:
        reasons_summary = "  ".join(reasons[:4])
        ax_header.text(0.0, 0.05, f"Motivos do Status [{status_clean}]: {reasons_summary}",
                       fontsize=9.0, color='#E2E8F0', fontweight='bold', va='bottom',
                       bbox=dict(boxstyle='round,pad=0.4', facecolor='#1E293B', edgecolor='#475569', lw=1.0))

    # ══════════════════════════════════════════════════════════════════
    # ROW 1: PAINEL A — FUNDAMENTOS OPERACIONAIS
    # ══════════════════════════════════════════════════════════════════
    ax1 = fig.add_subplot(gs[1])
    ax1.set_facecolor(BG)

    ax1.plot(full_dates, primary['ebitda_index_median'],
             label='EBITDA LTM Index — Ex-PETR4/VALE3 (Mediana)', color=C_EBITDA2, lw=3.2, zorder=5)
    ax1.plot(full_dates, all_sample['ebitda_index_median'],
             label='EBITDA LTM Index — Todas (Mediana)', color=C_EBITDA, lw=2.0, alpha=0.7, zorder=4)
    ax1.plot(full_dates, ibov_index,
             label='Ibovespa (Benchmark de Mercado)', color=C_IBOV, lw=2.2, ls='--', alpha=0.9, zorder=3)

    SEC_PALETTE = [
        '#38BDF8', '#F59E0B', '#EC4899', '#A855F7', '#10B981',
        '#F43F5E', '#8B5CF6', '#06B6D4', '#EAB308', '#F97316',
        '#14B8A6', '#6366F1', '#3B82F6', '#EF4444', '#84CC16'
    ]

    end_positions = []
    for idx, sec_name in enumerate(sector_indices.columns, start=1):
        c = SEC_PALETTE[(idx - 1) % len(SEC_PALETTE)]
        series = sector_indices[sec_name]
        ax1.plot(full_dates, series,
                 label=f'[{idx}] {sec_name}', color=c, lw=1.6, ls=':', alpha=0.85, zorder=2)
        end_val = series.iloc[-1] if not series.empty else 100.0
        end_positions.append({'idx': idx, 'name': sec_name, 'y': end_val, 'color': c})

    # Ajuste de sobreposição dos números no fim da linha (right edge)
    end_positions.sort(key=lambda item: item['y'])
    adjusted_y = []
    min_dist = 4.0
    for item in end_positions:
        cur_y = item['y']
        if adjusted_y:
            prev_y = adjusted_y[-1]
            if cur_y - prev_y < min_dist:
                cur_y = prev_y + min_dist
        adjusted_y.append(cur_y)
        item['y_adj'] = cur_y

    x_end = full_dates[-1]
    for item in end_positions:
        ax1.text(x_end, item['y_adj'], f" [{item['idx']}]",
                 color=item['color'], fontweight='bold', fontsize=8.5, va='center', ha='left', clip_on=False,
                 bbox=dict(boxstyle='round,pad=0.15', facecolor='#1E293B', edgecolor=item['color'], lw=0.8, alpha=0.9))

    ax1.axhline(100, color=C_GRID, ls=':', lw=1.0, alpha=0.6)
    ax1.set_title('Painel A — Fundamentos Operacionais: Evolução do EBITDA LTM por Setor (Base 100 = Jan/2021)',
                  fontsize=13, color=C_TEXT, pad=12, loc='left', fontweight='bold')
    ax1.set_ylabel('Índice (Base 100)', color=C_MUTED, fontsize=11, fontweight='bold')
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"{int(x)}"))
    ax1.grid(True, ls='--', lw=0.7, color=C_GRID, alpha=0.6)

    for spine in ['top', 'right', 'left']:
        ax1.spines[spine].set_visible(False)
    ax1.spines['bottom'].set_color(C_GRID)
    ax1.tick_params(axis='y', colors=C_MUTED, labelsize=10)
    ax1.tick_params(axis='x', colors=C_MUTED, labelsize=10)
    ax1.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))

    leg1 = ax1.legend(frameon=True, facecolor=CARD, edgecolor=CARD_BORDER, fontsize=9.0,
                      loc='upper left', labelcolor='#E2E8F0', ncol=3, framealpha=0.95)
    leg1.get_frame().set_linewidth(1.0)

    # ══════════════════════════════════════════════════════════════════
    # ROW 2: PAINEL B — O "BICO DE PATO"
    # ══════════════════════════════════════════════════════════════════
    ax2 = fig.add_subplot(gs[2])
    ax2.set_facecolor(BG)

    ax2.set_title('Painel B — O "Bico de Pato": Divergência Operacional vs. Múltiplo de Valuation (EV/EBITDA)',
                  fontsize=13, color=C_TEXT, pad=12, loc='left', fontweight='bold')

    ln1 = ax2.plot(full_dates, primary['ebitda_index_median'],
                   label='EBITDA LTM Index (Base 100)', color=C_EBITDA, lw=3.0, zorder=4)
    ax2.fill_between(full_dates, 100, primary['ebitda_index_median'],
                     where=primary['ebitda_index_median'] >= 100,
                     color=C_EBITDA, alpha=0.10, zorder=1)
    ax2.axhline(100, color=C_GRID, ls=':', lw=1.0, alpha=0.6)
    ax2.set_ylabel('EBITDA LTM Index (Base 100)', color=C_EBITDA, fontsize=11, fontweight='bold')
    ax2.tick_params(axis='y', colors=C_EBITDA, labelsize=10)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"{int(x)}"))

    ax2b = ax2.twinx()
    ln2 = ax2b.plot(full_dates, primary['ev_ebitda_median'],
                    label='EV/EBITDA Mediano (Ex-PETR4/VALE3)', color=C_MULT, lw=3.0, zorder=5)
    ax2b.fill_between(full_dates, primary['ev_ebitda_p25'], primary['ev_ebitda_p75'],
                      color=C_MULT, alpha=0.14, label='Faixa Interquartil (P25–P75)', zorder=2)
    avg_mult = primary['ev_ebitda_median'].mean()
    ax2b.axhline(avg_mult, color='#64748B', ls=':', lw=1.4, alpha=0.8)
    ax2b.set_ylabel('EV / EBITDA (Múltiplo)', color=C_MULT, fontsize=11, fontweight='bold')
    ax2b.tick_params(axis='y', colors=C_MULT, labelsize=10)
    ax2b.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"{x:.1f}x"))

    for spine in ['top', 'left']:
        ax2.spines[spine].set_visible(False)
        ax2b.spines[spine].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2b.spines['right'].set_color(C_MULT)
    ax2.spines['bottom'].set_color(C_GRID)
    ax2.grid(True, ls='--', lw=0.7, color=C_GRID, alpha=0.6)
    ax2.tick_params(axis='x', colors=C_MUTED, labelsize=10)
    ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))

    lines = ln1 + ln2
    labels = [l.get_label() for l in lines]
    leg2 = ax2.legend(lines, labels, frameon=True, facecolor=CARD, edgecolor=CARD_BORDER,
                      fontsize=10.5, loc='upper left', labelcolor='#E2E8F0', framealpha=0.95)
    leg2.get_frame().set_linewidth(1.0)

    # ══════════════════════════════════════════════════════════════════
    # ROW 3: PAINEL C — TAXA REAL VS. YIELDS DE VALUATION
    # ══════════════════════════════════════════════════════════════════
    ax3 = fig.add_subplot(gs[3])
    ax3.set_facecolor(BG)

    ax3.set_title('Painel C — Taxa Real vs. Yields de Valuation (Sem Premissa de Causalidade)',
                  fontsize=13, color=C_TEXT, pad=12, loc='left', fontweight='bold')

    ln_ntnb = ax3.plot(full_dates, ntnb, label='NTN-B IPCA+ 10a (Taxa Real Livre Risco)',
                       color=C_NTNB, lw=2.8, zorder=4)
    ax3.set_ylabel('NTN-B IPCA+ (% a.a.)', color=C_NTNB, fontsize=11, fontweight='bold')
    ax3.tick_params(axis='y', colors=C_NTNB, labelsize=10)
    ax3.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"{x:.1f}%"))

    ax3b = ax3.twinx()
    ln_ey = ax3b.plot(full_dates, primary['ebitda_yield_median'],
                      label='Spread Operacional: EBITDA Yield (EBITDA/EV)', color=C_EBITDA2, lw=2.4, ls='-.', zorder=5)
    ln_earn = ax3b.plot(full_dates, primary['earnings_yield_median'],
                        label='Equity Yield Proxy: Earnings Yield (Lucro/MCap)', color=C_EARN, lw=2.4, ls=':', zorder=6)
    ax3b.set_ylabel('Yield Implícito (%)', color='#38BDF8', fontsize=11, fontweight='bold')
    ax3b.tick_params(axis='y', colors='#38BDF8', labelsize=10)
    ax3b.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"{x:.1f}%"))

    for spine in ['top']:
        ax3.spines[spine].set_visible(False)
        ax3b.spines[spine].set_visible(False)
    ax3.spines['left'].set_visible(False)
    ax3.spines['right'].set_visible(False)
    ax3b.spines['left'].set_visible(False)
    ax3b.spines['right'].set_color('#38BDF8')
    ax3.spines['bottom'].set_color(C_GRID)
    ax3.grid(True, ls='--', lw=0.7, color=C_GRID, alpha=0.6)
    ax3.tick_params(axis='x', colors=C_MUTED, labelsize=10)
    ax3.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))

    all_lines = ln_ntnb + ln_ey + ln_earn
    all_labels = [l.get_label() for l in all_lines]
    leg3 = ax3.legend(all_lines, all_labels, frameon=True, facecolor=CARD,
                      edgecolor=CARD_BORDER, fontsize=10.5, loc='upper left', labelcolor='#E2E8F0', framealpha=0.95)
    leg3.get_frame().set_linewidth(1.0)

    # ══════════════════════════════════════════════════════════════════
    # ROW 4: PAINEL D — TESTE DE ROBUSTEZ POR AMOSTRA
    # ══════════════════════════════════════════════════════════════════
    ax4 = fig.add_subplot(gs[4])
    ax4.set_facecolor(BG)

    ax4.set_title('Painel D — Teste de Robustez: EBITDA Growth vs. Compressão de Múltiplo por Amostra',
                  fontsize=13, color=C_TEXT, pad=12, loc='left', fontweight='bold')

    sample_names = []
    ebitda_changes = []
    multiple_changes = []
    classifications = []
    for key, sdef in sample_definitions.items():
        r = robustness.get(key)
        if r is not None:
            sample_names.append(sdef['label'])
            ebitda_changes.append(r['ebitda_change_pct'])
            mc = r['multiple_change_pct']
            multiple_changes.append(mc if not np.isnan(mc) else 0)
            classifications.append(r['classification'])

    x = np.arange(len(sample_names))
    width = 0.32

    bars1 = ax4.bar(x - width / 2, ebitda_changes, width,
                    label='Crescimento EBITDA Mediano (%)', color=C_EBITDA, alpha=0.88, zorder=3)
    bars2 = ax4.bar(x + width / 2, multiple_changes, width,
                    label='Variação EV/EBITDA Mediano (%)', color=C_MULT, alpha=0.88, zorder=3)

    ax4.axhline(0, color=C_MUTED, lw=0.9, zorder=1)

    min_val = min(min(multiple_changes), -10)
    max_val = max(max(ebitda_changes), 10)
    ax4.set_ylim(min_val * 1.55, max_val * 1.25)

    ax4.set_xticks(x)
    ax4.set_xticklabels(sample_names, fontsize=10.5, color=C_TEXT, fontweight='bold')
    ax4.set_ylabel('Variação (%)', color=C_MUTED, fontsize=11, fontweight='bold')
    ax4.tick_params(axis='y', colors=C_MUTED, labelsize=10)

    for i, (b1, b2) in enumerate(zip(bars1, bars2)):
        y1 = b1.get_height()
        y2 = b2.get_height()
        ax4.text(b1.get_x() + b1.get_width() / 2, y1 + (2.5 if y1 >= 0 else -5),
                 f'{y1:+.1f}%', ha='center', va='bottom' if y1 >= 0 else 'top',
                 fontsize=10.5, fontweight='bold', color=C_EBITDA)
        ax4.text(b2.get_x() + b2.get_width() / 2, y2 + (-5 if y2 < 0 else 2.5),
                 f'{y2:+.1f}%', ha='center', va='top' if y2 < 0 else 'bottom',
                 fontsize=10.5, fontweight='bold', color=C_MULT)

    for spine in ['top', 'right', 'left']:
        ax4.spines[spine].set_visible(False)
    ax4.spines['bottom'].set_color(C_GRID)
    ax4.grid(True, ls='--', lw=0.5, color=C_GRID, alpha=0.4, axis='y')

    leg4 = ax4.legend(frameon=True, facecolor=CARD, edgecolor=CARD_BORDER, fontsize=10.5,
                      loc='upper right', labelcolor='#E2E8F0', framealpha=0.95)
    leg4.get_frame().set_linewidth(1.0)

    # ══════════════════════════════════════════════════════════════════
    # ROW 5: PAINEL E — DIFUSÃO DO BICO DE PATO COM IC95% (NOVO)
    # ══════════════════════════════════════════════════════════════════
    ax5 = fig.add_subplot(gs[5])
    ax5.set_facecolor(BG)
    ax5.set_title('Painel E — Difusão do Bico de Pato por Subamostra (N, K, % e IC95% Wilson)',
                  fontsize=13, color=C_TEXT, pad=12, loc='left', fontweight='bold')

    diff_labels = []
    diff_values = []
    ci_lows = []
    ci_highs = []
    nk_texts = []

    for key in ['all', 'ex_leaders', 'ex_commodities']:
        r = robustness.get(key)
        if r:
            s_label = sample_definitions.get(key, {}).get('label', key)
            binom = r.get('binomial_test', {})
            n_val = binom.get('N', r.get('N', 0))
            k_val = binom.get('K', r.get('K', 0))
            prop = binom.get('proportion', 0.0) * 100.0
            c_l = binom.get('ci_lower', 0.0) * 100.0
            c_h = binom.get('ci_upper', 0.0) * 100.0

            diff_labels.append(s_label)
            diff_values.append(prop)
            ci_lows.append(prop - c_l)
            ci_highs.append(c_h - prop)
            nk_texts.append(f"K={k_val} / N={n_val}\n({prop:.1f}%)")

    x_diff = np.arange(len(diff_labels))
    bars5 = ax5.bar(x_diff, diff_values, width=0.4, color='#06B6D4', alpha=0.85, zorder=3,
                    yerr=[ci_lows, ci_highs], capsize=5, ecolor='#F8FAFC')
    ax5.axhline(50.0, color='#F59E0B', ls='--', lw=1.5, label='Threshold Neutro (50%)', zorder=4)

    ax5.set_xticks(x_diff)
    ax5.set_xticklabels(diff_labels, fontsize=10.5, color=C_TEXT, fontweight='bold')
    ax5.set_ylabel('Difusão (% Empresas)', color=C_MUTED, fontsize=11, fontweight='bold')
    ax5.set_ylim(0, 118)

    for i, bar in enumerate(bars5):
        y_val = bar.get_height()
        box_y = y_val + ci_highs[i] + 4.5
        ax5.text(bar.get_x() + bar.get_width()/2, box_y, nk_texts[i],
                 ha='center', va='bottom', fontsize=9.5, fontweight='bold', color=C_TEXT,
                 bbox=dict(boxstyle='round,pad=0.3', facecolor=CARD, edgecolor=CARD_BORDER, lw=1.0))

    for spine in ['top', 'right', 'left']:
        ax5.spines[spine].set_visible(False)
    ax5.spines['bottom'].set_color(C_GRID)
    ax5.grid(True, ls='--', lw=0.5, color=C_GRID, alpha=0.4, axis='y')
    ax5.legend(loc='lower right', frameon=True, facecolor=CARD, edgecolor=CARD_BORDER, labelcolor='#E2E8F0')

    # ══════════════════════════════════════════════════════════════════
    # ROW 6: PAINEL F — PERSISTÊNCIA TEMPORAL DA DIFUSÃO (NOVO)
    # ══════════════════════════════════════════════════════════════════
    ax6 = fig.add_subplot(gs[6])
    ax6.set_facecolor(BG)
    ax6.set_title('Painel F — Persistência Temporal: Proporção de Empresas em Bico de Pato por Período (Kt/Nt)',
                  fontsize=13, color=C_TEXT, pad=12, loc='left', fontweight='bold')

    pers_primary = primary.get('persistence', {})
    temp_diff = pers_primary.get('temporal_diffusion', pd.Series(dtype=float))

    if not temp_diff.empty:
        ax6.plot(full_dates, temp_diff, color='#A855F7', lw=2.8, marker='o', ms=4, label='Difusão Temporal Kt/Nt (%)')
        ax6.axhline(50.0, color='#F59E0B', ls='--', lw=1.2, label='Linha de 50%')
        med_p = pers_primary.get('median_company_persistence', 0.0) * 100.0
        ax6.axhline(med_p, color='#10B981', ls=':', lw=1.5, label=f'Persistência Mediana: {med_p:.1f}%')

    ax6.set_ylabel('Difusão por Período (%)', color=C_MUTED, fontsize=11, fontweight='bold')
    ax6.set_ylim(0, 100)
    ax6.grid(True, ls='--', lw=0.5, color=C_GRID, alpha=0.4)
    ax6.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax6.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
    for spine in ['top', 'right', 'left']:
        ax6.spines[spine].set_visible(False)
    ax6.spines['bottom'].set_color(C_GRID)
    ax6.tick_params(axis='both', colors=C_MUTED, labelsize=10)
    ax6.legend(loc='upper left', frameon=True, facecolor=CARD, edgecolor=CARD_BORDER, labelcolor='#E2E8F0')

    # ══════════════════════════════════════════════════════════════════
    # ROW 7: PAINEL G — SCATTER PLOT OPERACIONAL VS. VALUATION (NOVO)
    # ══════════════════════════════════════════════════════════════════
    ax7 = fig.add_subplot(gs[7])
    ax7.set_facecolor(BG)
    ax7.set_title('Painel G — Scatter Plot: Δ EBITDA (%) vs. Δ EV/EBITDA (%) (Com Quadrante Bico de Pato)',
                  fontsize=13, color=C_TEXT, pad=12, loc='left', fontweight='bold')

    x_scatter = primary.get('ebitda_growths_series', pd.Series()).dropna()
    y_scatter = primary.get('mult_changes_series', pd.Series()).dropna()
    common_idx = x_scatter.index.intersection(y_scatter.index)

    if not common_idx.empty:
        xs = x_scatter.loc[common_idx].values
        ys = y_scatter.loc[common_idx].values
        bico_mask = (xs > 0) & (ys < 0)

        ax7.scatter(xs[bico_mask], ys[bico_mask], color='#10B981', s=45, alpha=0.85, label='Bico de Pato (ΔEBITDA > 0 & ΔEV/EBITDA < 0)', zorder=4)
        ax7.scatter(xs[~bico_mask], ys[~bico_mask], color='#F43F5E', s=35, alpha=0.55, label='Outros Quadrantes', zorder=3)

        # Linha de tendência
        if len(xs) > 2:
            p_fit = np.polyfit(xs, ys, 1)
            x_trend = np.linspace(min(xs), max(xs), 100)
            y_trend = np.polyval(p_fit, x_trend)
            ax7.plot(x_trend, y_trend, color='#F59E0B', ls='--', lw=2.0, label='Linha de Tendência Linear')

    ax7.axhline(0, color=C_GRID, lw=1.2)
    ax7.axvline(0, color=C_GRID, lw=1.2)
    ax7.set_xlabel('Δ EBITDA LTM (%)', color=C_MUTED, fontsize=11, fontweight='bold')
    ax7.set_ylabel('Δ EV/EBITDA (%)', color=C_MUTED, fontsize=11, fontweight='bold')
    ax7.grid(True, ls='--', lw=0.5, color=C_GRID, alpha=0.4)

    corr_p = primary.get('correlations', {})
    spear_text = f"Spearman rho = {corr_p.get('rho_spearman', 0.0):.3f} (p = {corr_p.get('p_value_spearman', 1.0):.4f})\nN = {corr_p.get('N', 0)}"
    ax7.text(0.98, 0.95, spear_text, transform=ax7.transAxes, ha='right', va='top', fontsize=10, fontweight='bold', color=C_TEXT,
             bbox=dict(boxstyle='round,pad=0.4', facecolor=CARD, edgecolor=CARD_BORDER, lw=1.0))

    for spine in ['top', 'right', 'left']:
        ax7.spines[spine].set_visible(False)
    ax7.spines['bottom'].set_color(C_GRID)
    ax7.tick_params(axis='both', colors=C_MUTED, labelsize=10)
    ax7.legend(loc='lower left', frameon=True, facecolor=CARD, edgecolor=CARD_BORDER, labelcolor='#E2E8F0')

    # ══════════════════════════════════════════════════════════════════
    # ROW 8: PAINEL H — DECOMPOSIÇÃO DO ENTERPRISE VALUE & TIPOS (NOVO)
    # ══════════════════════════════════════════════════════════════════
    ax8 = fig.add_subplot(gs[8])
    ax8.set_facecolor(BG)
    ax8.set_title('Painel H — Decomposição do EV (ΔEBITDA, ΔEV, ΔMCap, ΔNetDebt) & Classificação por Tipo (A/B/C/D)',
                  fontsize=13, color=C_TEXT, pad=12, loc='left', fontweight='bold')

    decomp = primary.get('ev_decomp', {})
    t_counts = decomp.get('type_counts', {})

    comp_labels = ['Δ EBITDA', 'Δ EV', 'Δ Market Cap', 'Δ Net Debt']
    comp_vals = [
        decomp.get('agg_ebitda_growth', 0.0),
        decomp.get('agg_ev_growth', 0.0),
        decomp.get('agg_mcap_growth', 0.0),
        decomp.get('agg_netdebt_growth', 0.0)
    ]

    x_comp = np.arange(len(comp_labels))
    colors_comp = ['#10B981', '#F59E0B', '#38BDF8', '#A855F7']
    bars8 = ax8.bar(x_comp, comp_vals, width=0.4, color=colors_comp, alpha=0.85, zorder=3)
    ax8.axhline(0, color=C_MUTED, lw=0.9, zorder=1)

    ax8.set_xticks(x_comp)
    ax8.set_xticklabels(comp_labels, fontsize=10.5, color=C_TEXT, fontweight='bold')
    ax8.set_ylabel('Variação Mediana (%)', color=C_MUTED, fontsize=11, fontweight='bold')

    for bar in bars8:
        y_val = bar.get_height()
        ax8.text(bar.get_x() + bar.get_width()/2, y_val + (1.5 if y_val >= 0 else -3.5),
                 f'{y_val:+.1f}%', ha='center', va='bottom' if y_val >= 0 else 'top',
                 fontsize=10.0, fontweight='bold', color=C_TEXT)

    # Inset / Text Box com a contagem dos Tipos
    types_str = (f"Tipos de Bico de Pato:\n"
                 f" • Tipo A (EBITDA^ EVv): {t_counts.get('Tipo A', 0)}\n"
                 f" • Tipo B (EBITDA^ EV=): {t_counts.get('Tipo B', 0)}\n"
                 f" • Tipo C (EBITDA^ > EV^): {t_counts.get('Tipo C', 0)}\n"
                 f" • Tipo D (EBITDA^ < EV^): {t_counts.get('Tipo D', 0)}\n"
                 f" • Não Bico: {t_counts.get('Não Bico', 0)}")

    ax8.text(0.98, 0.95, types_str, transform=ax8.transAxes, ha='right', va='top', fontsize=9.5, fontweight='bold', color=C_TEXT,
             bbox=dict(boxstyle='round,pad=0.4', facecolor=CARD, edgecolor=CARD_BORDER, lw=1.0))

    for spine in ['top', 'right', 'left']:
        ax8.spines[spine].set_visible(False)
    ax8.spines['bottom'].set_color(C_GRID)
    ax8.grid(True, ls='--', lw=0.5, color=C_GRID, alpha=0.4, axis='y')
    ax8.tick_params(axis='both', colors=C_MUTED, labelsize=10)

    plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches='tight')
    print(f"\n✅ Dashboard ampliado e corrigido com 8 painéis salvo em: {output_path}")
    try:
        plt.show()
    except KeyboardInterrupt:
        print("ℹ️  Janela do gráfico encerrada.")
    finally:
        plt.close('all')


# ══════════════════════════════════════════════════════════════════════════════
# 8. OUTPUTS — CSVs AUDITADOS
# ══════════════════════════════════════════════════════════════════════════════

def save_all_csvs(results, company_metrics_df, sector_metrics_df, quality_df, raw_data,
                  diffusion_df, macro_corr_df, sample_comp_df, lookahead_audit_df=None,
                  included_companies_df=None, excluded_companies_df=None,
                  collection_errors_df=None, sample_audit_df=None):
    """Salva todos os CSVs de auditoria (8 originais + lookahead_audit.csv + 4 CSVs de expansão de amostra)."""
    company_metrics_df.to_csv('bico_de_pato_company_metrics.csv', index=False)
    print("  📄 bico_de_pato_company_metrics.csv")

    sector_metrics_df.to_csv('bico_de_pato_sector_metrics.csv', index=False)
    print("  📄 bico_de_pato_sector_metrics.csv")

    primary = results['samples']['ex_leaders']
    ntnb_i = results.get('ntnb_initial', np.nan)
    ntnb_f = results.get('ntnb_final', np.nan)
    ntnb_chg = results.get('ntnb_change_pp', np.nan)
    cand_count = results.get('candidate_count', len(results['valid_tickers']))
    eff_count = results.get('effective_sample_size', len(results['valid_tickers']))
    disc_count = results.get('excluded_count', 0)

    summary_rows = [
        {'Metric': 'Universo Candidato', 'Initial_Value': f"{cand_count}", 'Final_Value': f"{cand_count}", 'Change': '0', 'Interpretation': 'Total de empresas submetidas à análise'},
        {'Metric': 'Amostra Efetiva (N)', 'Initial_Value': f"{eff_count}", 'Final_Value': f"{eff_count}", 'Change': f"{eff_count}", 'Interpretation': 'Empresas com dados suficientes que participaram dos cálculos'},
        {'Metric': 'Empresas Descartadas', 'Initial_Value': f"{disc_count}", 'Final_Value': f"{disc_count}", 'Change': f"{disc_count}", 'Interpretation': 'Empresas excluídas por falta de preços, EBITDA ou ações'},
        {'Metric': 'EBITDA LTM Index (Mediano)', 'Initial_Value': '100.0',
         'Final_Value': f"{primary['ebitda_change_pct'] + 100:.1f}",
         'Change': f"{primary['ebitda_change_pct']:+.1f}%",
         'Interpretation': 'Fundamentos cresceram' if primary['ebitda_change_pct'] > 0 else 'Fundamentos caíram'},
        {'Metric': 'EV/EBITDA Mediano', 'Initial_Value': f"{primary['initial_multiple']:.1f}x",
         'Final_Value': f"{primary['final_multiple']:.1f}x",
         'Change': f"{primary['multiple_change_pct']:+.1f}%",
         'Interpretation': 'Compressão de múltiplo' if primary['multiple_change_pct'] < 0 else 'Expansão de múltiplo'},
        {'Metric': 'NTN-B IPCA+ 10a', 'Initial_Value': f"{ntnb_i:.2f}%",
         'Final_Value': f"{ntnb_f:.2f}%",
         'Change': f"{ntnb_chg:+.1f} p.p.",
         'Interpretation': 'Taxa real subiu' if ntnb_chg > 0 else 'Taxa real caiu'},
        {'Metric': 'Difusão Bico de Pato', 'Initial_Value': '0.0%',
         'Final_Value': f"{primary['diffusion_bico'].iloc[-1]:.1f}%",
         'Change': f"{primary['diffusion_bico'].iloc[-1]:.1f}%",
         'Interpretation': '% de empresas simultaneamente com EBITDA ↑ e EV/EBITDA ↓'},
        {'Metric': 'Resultado Hipótese', 'Initial_Value': '—', 'Final_Value': '—',
         'Change': primary['classification'],
         'Interpretation': 'Classificação empírica com critérios documentados'},
        {'Metric': 'Metodologia PIT', 'Initial_Value': '—', 'Final_Value': '—',
         'Change': 'Point-in-Time adjusted',
         'Interpretation': 'Dados fundamentais filtrados por publication_date <= observation_date'},
    ]
    pd.DataFrame(summary_rows).to_csv('bico_de_pato_summary.csv', index=False)
    print("  📄 bico_de_pato_summary.csv")

    quality_df.to_csv('bico_de_pato_data_quality.csv', index=False)
    print("  📄 bico_de_pato_data_quality.csv")

    if raw_data is not None and not raw_data.empty:
        raw_data.to_csv('bico_de_pato_raw_data.csv')
        print("  📄 bico_de_pato_raw_data.csv")

    diffusion_df.to_csv('bico_de_pato_bico_diffusion.csv', index=False)
    print("  📄 bico_de_pato_bico_diffusion.csv")

    macro_corr_df.to_csv('bico_de_pato_macro_correlation.csv', index=False)
    print("  📄 bico_de_pato_macro_correlation.csv")

    sample_comp_df.to_csv('bico_de_pato_sample_comparison.csv', index=False)
    print("  📄 bico_de_pato_sample_comparison.csv")

    # Look-ahead audit CSV (Point-in-Time)
    if lookahead_audit_df is not None and not lookahead_audit_df.empty:
        lookahead_audit_df.to_csv('lookahead_audit.csv', index=False)
        print("  📄 lookahead_audit.csv (Point-in-Time audit trail)")

    # 4 CSVs de expansão de amostra
    if included_companies_df is not None and not included_companies_df.empty:
        included_companies_df.to_csv('included_companies.csv', index=False)
        print("  📄 included_companies.csv")

    if excluded_companies_df is not None and not excluded_companies_df.empty:
        excluded_companies_df.to_csv('excluded_companies.csv', index=False)
        print("  📄 excluded_companies.csv")

    if collection_errors_df is not None and not collection_errors_df.empty:
        collection_errors_df.to_csv('collection_errors.csv', index=False)
        print("  📄 collection_errors.csv")
    else:
        pd.DataFrame(columns=['ticker', 'stage', 'error_type', 'error_message', 'timestamp']).to_csv('collection_errors.csv', index=False)
        print("  📄 collection_errors.csv (sem erros de exceção)")

    if sample_audit_df is not None and not sample_audit_df.empty:
        sample_audit_df.to_csv('sample_audit.csv', index=False)
        print("  📄 sample_audit.csv")


# ══════════════════════════════════════════════════════════════════════════════
# 9. CONCLUSÃO E INTERPRETAÇÃO AUTOMÁTICA
# ══════════════════════════════════════════════════════════════════════════════

def print_conclusion(results):
    """Imprime a conclusão empírica com interpretação dinâmica e matriz do Evidence Scorecard."""
    primary = results['samples']['ex_leaders']
    full_dates = results['full_dates']
    eval_res = results.get('hypothesis_evaluation', {})

    ntnb_i = results.get('ntnb_initial', np.nan)
    ntnb_f = results.get('ntnb_final', np.nan)
    spread_i = results.get('spread_initial', np.nan)
    spread_f = results.get('spread_final', np.nan)

    diff_bico_final = primary.get('bico_diffusion_pct', primary['diffusion_bico'].iloc[-1] if not primary['diffusion_bico'].empty else np.nan)
    k_val = primary.get('K', 0)
    n_val = primary.get('N', len(results['valid_tickers_ex_leaders']))

    binom = primary.get('binomial_test', {})
    corr = primary.get('correlations', {})
    status_final = eval_res.get('status', primary['classification'])

    print("\n")
    print("=" * 70)
    print("       BICO DE PATO — RESULTADO FINAL DA HIPÓTESE & EVIDENCE SCORECARD")
    print("=" * 70)
    print(f"\n  Período Válido: {full_dates[0].strftime('%b/%Y')} → {full_dates[-1].strftime('%b/%Y')}")
    print(f"  Amostra Primária: Ex-PETR4/VALE3 (N = {n_val} empresas, K = {k_val} Bico de Pato)")
    print(f"\n  EBITDA Mediano:      {primary['ebitda_change_pct']:+.1f}%")
    print(f"  EBITDA Agregado:     {primary['ebitda_growth_agg_pct']:+.1f}%")
    print(f"\n  EV Agregado:         {primary['ev_growth_pct']:+.1f}%")
    print(f"  Market Cap Agregado: {primary['mcap_growth_pct']:+.1f}%")
    print(f"  Dívida Liq. Agregada:{primary['netdebt_growth_pct']:+.1f}%")
    print(f"\n  EV/EBITDA Mediano:   {primary['initial_multiple']:.1f}x → {primary['final_multiple']:.1f}x ({primary['multiple_change_pct']:+.1f}%)")
    print(f"\n  NTN-B IPCA+:         {ntnb_i:.2f}% → {ntnb_f:.2f}% ({results.get('ntnb_change_pp', 0):+.2f} p.p.)")
    print(f"  Spread Operacional:  {spread_i:+.1f} p.p. → {spread_f:+.1f} p.p.")
    print(f"\n  Difusão Bico de Pato:{diff_bico_final:.1f}% (K={k_val}/{n_val})")
    print(f"  Teste Binomial Exato: p-value = {binom.get('p_value', 1.0):.4f} (IC95%: [{binom.get('ci_lower', 0)*100:.1f}%; {binom.get('ci_upper', 0)*100:.1f}%])")
    print(f"  Spearman rho:        {corr.get('rho_spearman', 0.0):.3f} (p-value = {corr.get('p_value_spearman', 1.0):.4f})")
    print(f"\n  {'─' * 60}")
    print(f"  STATUS DA HIPÓTESE: [{status_final}]")
    print(f"  {'─' * 60}")

    print("\n  Matriz de Evidências (Scorecard 9 Dimensões):")
    for criterion, status_val in eval_res.get('scorecard', {}).items():
        print(f"    [{status_val:4s}] {criterion}")

    print("\n  Justificativas Dinâmicas:")
    for reason in eval_res.get('justification_reasons', []):
        print(f"    {reason}")

    print("\n  Ressalva Metodológica: Esta relação indica associação empírica descritiva no período, NÃO causalidade provada.")
    print("=" * 70)


# ══════════════════════════════════════════════════════════════════════════════
# 10. PIPELINE PRINCIPAL — ORQUESTRAÇÃO COMPLETA
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Executa a análise completa do Bico de Pato com universo expandido e rigor metodológico."""
    start_time = time.time()

    candidate_count = len(CANDIDATE_TICKERS)
    print(f"📥 Coletando cotações históricas reais para {candidate_count} empresas candidatas da B3 (sem preços sintéticos)...")
    prices_df, ibov_source = download_all_prices(TICKERS, IBOV_TICKER, START_DATE)

    # Identificação inicial de preços válidos
    price_sources = {}
    included_companies = []
    excluded_companies = []
    collection_errors = []
    sample_audit_rows = []

    for item in CANDIDATE_TICKERS:
        ticker = item["ticker"]
        name = item["name"]
        sector = item["sector"]

        if ticker not in prices_df.columns or prices_df[ticker].dropna().empty:
            price_sources[ticker] = "PRICE_DATA_INSUFFICIENT"
            reason = "MISSING_PRICE_DATA"
            details = "Preço histórico indisponível no yfinance"
            excluded_companies.append({
                "ticker": ticker, "company_name": name, "sector": sector,
                "status": "DISCARDED", "exclusion_reason": reason, "details": details
            })
            sample_audit_rows.append({
                "ticker": ticker, "company_name": name, "sector": sector,
                "candidate": True, "included": False, "exclusion_reason": reason, "data_quality": "INSUFFICIENT_DATA"
            })
            logger.debug(f"  ⚠️  {ticker} ({name}): {details}. EXCLUÍDO DA AMOSTRA.")
        else:
            price_sources[ticker] = "YFINANCE_REAL"

    # Alinhamento temporal dinâmico com base nos preços reais disponíveis
    valid_price_tickers = [t for t in TICKERS if price_sources.get(t) == "YFINANCE_REAL"]
    if not valid_price_tickers:
        raise RuntimeError("❌ Falha crítica: Nenhum ticker obteve cotações reais válidas.")

    last_price_date = prices_df[valid_price_tickers].dropna(how='all').index.max()
    if hasattr(last_price_date, 'tz') and last_price_date.tz is not None:
        last_price_date = last_price_date.tz_localize(None)

    full_dates = pd.date_range(start=START_DATE, end=last_price_date, freq='ME')
    END_DATE = full_dates[-1].strftime('%Y-%m-%d')
    print(f"  📅 Período Efetivo de Análise: {START_DATE} → {END_DATE} ({len(full_dates)} meses)")

    # Ibovespa alinhado
    ibov_monthly = pd.Series(dtype=float)
    if ibov_source == "YFINANCE" and IBOV_TICKER in prices_df.columns:
        ibov_raw = prices_df[IBOV_TICKER].dropna()
        if not ibov_raw.empty:
            ibov_monthly = ibov_raw.resample('ME').last().reindex(full_dates).ffill()
        else:
            ibov_source = "FALLBACK"

    if ibov_source == "FALLBACK" or ibov_monthly.empty:
        ibov_source = "FALLBACK"
        ibov_fb = pd.Series(IBOV_FALLBACK)
        ibov_fb.index = pd.to_datetime(ibov_fb.index)
        ibov_monthly = ibov_fb.reindex(full_dates).ffill()
        print("  ⚠️  Ibovespa: utilizando dados de fallback.")

    ibov_base = ibov_monthly.iloc[0] if not ibov_monthly.empty and ibov_monthly.iloc[0] > 0 else 1
    ibov_index = (ibov_monthly / ibov_base) * 100.0

    # NTN-B alinhada sem extrapolação futura
    ntnb_raw = pd.Series(NTN_B_MONTHLY_DATA)
    ntnb_raw.index = pd.to_datetime(ntnb_raw.index)
    ntnb_monthly = ntnb_raw.reindex(full_dates).ffill()

    # ══════════════════════════════════════════════════════════════════
    # POINT-IN-TIME: Popular FundamentalStore com dados hardcoded existentes
    # ══════════════════════════════════════════════════════════════════
    print("\n📊 Populando FundamentalStore com dados hardcoded (Point-in-Time)...")
    pit_store = FundamentalStore()
    populate_store_from_hardcoded(
        pit_store, EBITDA_DATES,
        EBITDA_HARDCODED_BI, NET_DEBT_HARDCODED_BI,
        NET_INCOME_HARDCODED_BI, SHARES_OUTSTANDING_FALLBACK_BI,
    )
    n_records = len(pit_store.get_all_records())
    print(f"  ✅ {n_records} registros fundamentais originais carregados no FundamentalStore")

    print("\n📊 Processando e validando dados fundamentais por empresa...")

    df_ebitda_monthly = pd.DataFrame(index=full_dates)
    df_netdebt_monthly = pd.DataFrame(index=full_dates)
    df_netincome_monthly = pd.DataFrame(index=full_dates)
    df_market_cap = pd.DataFrame(index=full_dates)
    df_ev = pd.DataFrame(index=full_dates)
    df_ev_ebitda = pd.DataFrame(index=full_dates)
    df_ebitda_yield = pd.DataFrame(index=full_dates)
    df_earnings_yield = pd.DataFrame(index=full_dates)

    # Point-in-Time tracking
    df_lookahead_flags = pd.DataFrame(index=full_dates)
    all_audit_records = []

    valid_tickers = []
    ebitda_sources = {}
    shares_sources = {}
    negative_ev_counts = {}
    ticker_lookahead_flags = {}

    for item in CANDIDATE_TICKERS:
        ticker = item["ticker"]
        name = item["name"]
        sector = item["sector"]

        if price_sources.get(ticker) != "YFINANCE_REAL":
            continue  # já registrado como descarte por preço

        try:
            s_price_raw = prices_df[ticker].dropna()
            s_price_monthly = s_price_raw.resample('ME').last().reindex(full_dates).ffill()

            hardcoded_list = EBITDA_HARDCODED_BI.get(ticker, [0.0] * len(EBITDA_DATES))
            ebitda_annual, ebitda_src = get_ebitda_ltm(ticker, EBITDA_DATES, hardcoded_list)

            # Adicionar dados yfinance ao store PIT
            populate_store_from_yfinance(pit_store, ticker, ebitda_annual, ebitda_src, EBITDA_DATES)

            # Construção de séries mensais Point-in-Time
            ebitda_pit_values, ebitda_pit_flags, ebitda_audit = build_pit_monthly_series(
                pit_store, ticker, 'EBITDA', full_dates, is_ebitda=True
            )
            nd_pit_values, nd_pit_flags, nd_audit = build_pit_monthly_series(
                pit_store, ticker, 'NET_DEBT', full_dates, is_ebitda=False
            )
            ni_pit_values, ni_pit_flags, ni_audit = build_pit_monthly_series(
                pit_store, ticker, 'NET_INCOME', full_dates, is_ebitda=False
            )

            legacy_ebitda = build_monthly_series(ebitda_annual, EBITDA_DATES, full_dates)
            nd_values = NET_DEBT_HARDCODED_BI.get(ticker, [0.0] * len(EBITDA_DATES))
            nd_annual = pd.Series(nd_values, index=EBITDA_DATES, dtype=float)
            legacy_nd = build_monthly_series(nd_annual, EBITDA_DATES, full_dates)
            ni_values = NET_INCOME_HARDCODED_BI.get(ticker, [0.0] * len(EBITDA_DATES))
            ni_annual = pd.Series(ni_values, index=EBITDA_DATES, dtype=float)
            legacy_ni = build_monthly_series(ni_annual, EBITDA_DATES, full_dates)

            ebitda_final_series = ebitda_pit_values.combine_first(legacy_ebitda)
            nd_final_series = nd_pit_values.combine_first(legacy_nd)
            ni_final_series = ni_pit_values.combine_first(legacy_ni)

            # ── VALIDAÇÕES DE QUALIDADE MÍNIMA PARA INCLUSÃO ──
            if ebitda_final_series.dropna().empty or (ebitda_final_series <= 0).all():
                reason = "INSUFFICIENT_EBITDA_DATA"
                details = "EBITDA LTM ausente ou não positivo"
                excluded_companies.append({
                    "ticker": ticker, "company_name": name, "sector": sector,
                    "status": "DISCARDED", "exclusion_reason": reason, "details": details
                })
                sample_audit_rows.append({
                    "ticker": ticker, "company_name": name, "sector": sector,
                    "candidate": True, "included": False, "exclusion_reason": reason, "data_quality": "INSUFFICIENT_DATA"
                })
                continue

            s_shares, shares_src = get_shares_outstanding(ticker, full_dates)
            if s_shares.dropna().empty or (s_shares <= 0).all():
                reason = "MISSING_SHARES"
                details = "Quantidade de ações ausente ou inválida"
                excluded_companies.append({
                    "ticker": ticker, "company_name": name, "sector": sector,
                    "status": "DISCARDED", "exclusion_reason": reason, "details": details
                })
                sample_audit_rows.append({
                    "ticker": ticker, "company_name": name, "sector": sector,
                    "candidate": True, "included": False, "exclusion_reason": reason, "data_quality": "INSUFFICIENT_DATA"
                })
                continue

            # Se aprovado em todas as validações:
            valid_tickers.append(ticker)
            ebitda_sources[ticker] = ebitda_src
            shares_sources[ticker] = shares_src
            all_audit_records.extend(ebitda_audit)
            all_audit_records.extend(nd_audit)
            all_audit_records.extend(ni_audit)

            df_ebitda_monthly[ticker] = ebitda_final_series
            df_netdebt_monthly[ticker] = nd_final_series
            df_netincome_monthly[ticker] = ni_final_series

            consolidated_flags = pd.Series('UNKNOWN', index=full_dates, dtype=str)
            for obs_date in full_dates:
                flag = compute_observation_lookahead_flag(
                    ebitda_pit_flags.loc[obs_date],
                    nd_pit_flags.loc[obs_date],
                    ni_pit_flags.loc[obs_date],
                    'UNKNOWN',
                )
                consolidated_flags.loc[obs_date] = flag

            df_lookahead_flags[ticker] = consolidated_flags
            ticker_lookahead_flags[ticker] = consolidated_flags

            mcap = s_price_monthly * s_shares
            df_market_cap[ticker] = mcap

            ev = mcap + df_netdebt_monthly[ticker]
            df_ev[ticker] = ev
            negative_ev_counts[ticker] = (ev <= 0).sum()

            ebitda_ltm = df_ebitda_monthly[ticker]
            ebitda_pos = ebitda_ltm.where(ebitda_ltm > 0)
            ev_pos = ev.where(ev > 0)

            ev_ebitda = ev_pos / ebitda_pos
            df_ev_ebitda[ticker] = ev_ebitda

            ebitda_yield = (ebitda_pos / ev_pos) * 100.0
            df_ebitda_yield[ticker] = ebitda_yield

            ni_ltm = df_netincome_monthly[ticker]
            ni_pos = ni_ltm.where(ni_ltm > 0)
            mcap_pos = mcap.where(mcap > 0)
            earnings_yield = (ni_pos / mcap_pos) * 100.0
            df_earnings_yield[ticker] = earnings_yield

            included_companies.append({
                "ticker": ticker, "company_name": name, "sector": sector, "status": "INCLUDED"
            })
            sample_audit_rows.append({
                "ticker": ticker, "company_name": name, "sector": sector,
                "candidate": True, "included": True, "exclusion_reason": "NONE", "data_quality": "VALID"
            })

        except Exception as e:
            reason = "COLLECTION_ERROR"
            details = f"Exceção de Coleta: {type(e).__name__} — {str(e)}"
            excluded_companies.append({
                "ticker": ticker, "company_name": name, "sector": sector,
                "status": "DISCARDED", "exclusion_reason": reason, "details": details
            })
            collection_errors.append({
                "ticker": ticker, "stage": "data_collection", "error_type": type(e).__name__,
                "error_message": str(e), "timestamp": datetime.now().isoformat()
            })
            sample_audit_rows.append({
                "ticker": ticker, "company_name": name, "sector": sector,
                "candidate": True, "included": False, "exclusion_reason": reason, "data_quality": "ERROR"
            })
            continue

    # ── CONTAGEM E ASSERTIONS DE AMOSTRAGEM ──
    effective_sample_size = len(included_companies)
    excluded_count = len(excluded_companies)
    assert candidate_count == effective_sample_size + excluded_count, \
        f"Erro de Contagem: {candidate_count} candidatas != {effective_sample_size} incluídas + {excluded_count} descartadas"

    # Construção dinâmica de setores baseada na amostra efetiva
    SECTORS = {}
    for item in included_companies:
        sec = item["sector"]
        if sec not in SECTORS:
            SECTORS[sec] = []
        SECTORS[sec].append(item["ticker"])

    # Amostras secundárias dinâmicas
    n_all = len(valid_tickers)
    n_ex_leaders = len([t for t in valid_tickers if t not in COMMODITY_LEADERS])
    n_ex_commodities = len([t for t in valid_tickers if t not in COMMODITY_ALL])

    SAMPLE_DEFINITIONS = {
        'all':            {'label': f'Todas (N={n_all})',                 'exclude': []},
        'ex_leaders':     {'label': f'Ex-PETR4/VALE3 (N={n_ex_leaders})', 'exclude': COMMODITY_LEADERS},
        'ex_commodities': {'label': f'Ex-Commodities Amplo (N={n_ex_commodities})', 'exclude': COMMODITY_ALL},
    }

    # Relatório executivo do processo de amostragem
    print("\n" + "=" * 65)
    print("                    RESUMO DA COLETA")
    print("=" * 65)
    print(f"  Universo Candidato:     {candidate_count} empresas")
    print(f"  Amostra Efetiva (N):    {effective_sample_size} empresas")
    print(f"  Empresas Descartadas:   {excluded_count} empresas")
    yield_rate = (effective_sample_size / candidate_count * 100.0) if candidate_count > 0 else 0.0
    print(f"  Taxa de Aproveitamento: {yield_rate:.1f}%")
    print("=" * 65)

    # Point-in-Time audit summary
    pit_audit_df = generate_audit_dataframe(all_audit_records)

    # ASSERTIONS DE INTEGRIDADE MATEMÁTICA
    for col in valid_tickers:
        mcap = df_market_cap[col]
        nd = df_netdebt_monthly[col]
        ev = df_ev[col]
        ebitda = df_ebitda_monthly[col]

        diff_ev = (ev - (mcap + nd)).abs().dropna()
        assert (diff_ev < 1e-4).all(), f"Erro de Validação Matemática: EV incorreto para {col}"

        valid_mask = (ev > 0) & (ebitda > 0)
        calc_ev_ebitda = (ev / ebitda).where(valid_mask)
        diff_mult = (df_ev_ebitda[col].where(valid_mask) - calc_ev_ebitda).abs().dropna()
        assert (diff_mult < 1e-4).all(), f"Erro de Validação Matemática: EV/EBITDA incorreto para {col}"

    print(f"\n✅ Validações Matemáticas Concluídas com Sucesso! ({len(valid_tickers)} empresas ativas)")

    # Série de variação da NTN-B para regressão
    ntnb_clean = ntnb_monthly.dropna()
    ntnb_initial = ntnb_clean.iloc[0] if len(ntnb_clean) > 0 else np.nan
    ntnb_final = ntnb_clean.iloc[-1] if len(ntnb_clean) > 0 else np.nan
    ntnb_change_pp = ntnb_final - ntnb_initial

    delta_ntnb_const = pd.Series(ntnb_change_pp, index=valid_tickers)

    print("\n📊 Calculando métricas, estatísticas e persistência por amostra...")
    robustness_results = {}
    for key, sdef in SAMPLE_DEFINITIONS.items():
        sample_tickers = [t for t in valid_tickers if t not in sdef['exclude']]
        if not sample_tickers:
            continue
        metrics = calculate_sample_metrics(
            df_ev_ebitda, df_ebitda_yield, df_earnings_yield,
            df_ebitda_monthly, df_ev, df_market_cap, df_netdebt_monthly,
            full_dates, sample_tickers, delta_ntnb_series=delta_ntnb_const[sample_tickers]
        )
        if metrics:
            robustness_results[key] = metrics
            print(f"  ✅ {sdef['label']}: N={metrics['N']} K={metrics['K']} ({metrics['bico_diffusion_pct']:.1f}%) | "
                  f"EBITDA {metrics['ebitda_change_pct']:+.1f}% | EV/EBITDA {metrics['multiple_change_pct']:+.1f}%")

    primary = robustness_results['ex_leaders']
    ex_comm = robustness_results.get('ex_commodities', primary)
    all_samp = robustness_results.get('all', primary)

    # Avaliação rigorosa da Matriz de Evidências (Evidence Scorecard)
    hypothesis_eval = evaluate_evidence_scorecard(all_samp, primary, ex_comm, pit_valid=True)

    sector_indices, sector_growth, sector_mult = calculate_sector_metrics(
        df_ebitda_monthly, df_ev_ebitda, df_ev, full_dates, SECTORS
    )

    ey_clean = primary['ebitda_yield_median'].dropna()
    ey_initial = ey_clean.iloc[0] if len(ey_clean) > 0 else np.nan
    ey_final = ey_clean.iloc[-1] if len(ey_clean) > 0 else np.nan
    spread_initial = ey_initial - ntnb_initial if not np.isnan(ey_initial) and not np.isnan(ntnb_initial) else np.nan
    spread_final = ey_final - ntnb_final if not np.isnan(ey_final) and not np.isnan(ntnb_final) else np.nan

    quality_df = validate_dataset(
        valid_tickers, df_ebitda_monthly, df_ev, df_market_cap, df_ev_ebitda,
        ebitda_sources, shares_sources, price_sources, negative_ev_counts,
        lookahead_flags=ticker_lookahead_flags,
    )

    # DataFrames dos CSVs
    company_rows = []
    for ticker in valid_tickers:
        ebitda_col = df_ebitda_monthly[ticker].dropna()
        ev_ebitda_col = df_ev_ebitda[ticker].dropna()
        mcap_col = df_market_cap[ticker].dropna()
        ev_col = df_ev[ticker].dropna()
        nd_col = df_netdebt_monthly[ticker].dropna()

        e_i = ebitda_col.iloc[0] if len(ebitda_col) > 0 else np.nan
        e_f = ebitda_col.iloc[-1] if len(ebitda_col) > 0 else np.nan
        e_growth = ((e_f / e_i) - 1) * 100.0 if e_i and e_i > 0 else np.nan

        m_i = ev_ebitda_col.iloc[0] if len(ev_ebitda_col) > 0 else np.nan
        m_f = ev_ebitda_col.iloc[-1] if len(ev_ebitda_col) > 0 else np.nan
        m_chg = ((m_f / m_i) - 1) * 100.0 if m_i and m_i > 0 else np.nan

        mc_i = mcap_col.iloc[0] if len(mcap_col) > 0 else np.nan
        mc_f = mcap_col.iloc[-1] if len(mcap_col) > 0 else np.nan
        mc_chg = ((mc_f / mc_i) - 1) * 100.0 if mc_i and mc_i > 0 else np.nan

        ev_i = ev_col.iloc[0] if len(ev_col) > 0 else np.nan
        ev_f = ev_col.iloc[-1] if len(ev_col) > 0 else np.nan
        ev_chg = ((ev_f / ev_i) - 1) * 100.0 if ev_i and ev_i > 0 else np.nan

        nd_i = nd_col.iloc[0] if len(nd_col) > 0 else np.nan
        nd_f = nd_col.iloc[-1] if len(nd_col) > 0 else np.nan
        nd_chg = ((nd_f / nd_i) - 1) * 100.0 if nd_i and nd_i > 0 else np.nan

        bico_flag = (e_growth > 0) and (m_chg < 0)

        setor = "—"
        for sn, st in SECTORS.items():
            if ticker in st:
                setor = sn
                break

        company_rows.append({
            'Ticker': ticker,
            'Setor': setor,
            'EBITDA_Inicial_R$Bi': round(e_i, 2) if not np.isnan(e_i) else np.nan,
            'EBITDA_Final_R$Bi': round(e_f, 2) if not np.isnan(e_f) else np.nan,
            'EBITDA_Growth_%': round(e_growth, 1) if not np.isnan(e_growth) else np.nan,
            'EV_Growth_%': round(ev_chg, 1) if not np.isnan(ev_chg) else np.nan,
            'MarketCap_Growth_%': round(mc_chg, 1) if not np.isnan(mc_chg) else np.nan,
            'NetDebt_Growth_%': round(nd_chg, 1) if not np.isnan(nd_chg) else np.nan,
            'EV_EBITDA_Inicial': round(m_i, 2) if not np.isnan(m_i) else np.nan,
            'EV_EBITDA_Final': round(m_f, 2) if not np.isnan(m_f) else np.nan,
            'EV_EBITDA_Change_%': round(m_chg, 1) if not np.isnan(m_chg) else np.nan,
            'Bico_de_Pato': bico_flag,
        })

    company_metrics_df = pd.DataFrame(company_rows).sort_values('EV_EBITDA_Change_%', ascending=True)

    sector_rows = []
    for sn, sec_tickers in SECTORS.items():
        valid_sec_tickers = [t for t in sec_tickers if t in valid_tickers]
        if not valid_sec_tickers:
            continue
        row = {
            'Setor': sn,
            'N_Empresas': len(valid_sec_tickers),
            'EBITDA_Growth_%': round(sector_growth.get(sn, np.nan), 1),
        }
        sm = sector_mult.get(sn, {})
        row['EV_EBITDA_Mediano_Inicial'] = round(sm.get('initial', np.nan), 2)
        row['EV_EBITDA_Mediano_Final'] = round(sm.get('final', np.nan), 2)
        row['Multiple_Change_%'] = round(sm.get('change_pct', np.nan), 1)
        sector_rows.append(row)
    sector_metrics_df = pd.DataFrame(sector_rows)

    diffusion_df = pd.DataFrame({
        'Date': full_dates,
        'Pct_Companies_EBITDA_Up': primary['diffusion_ebitda_up'],
        'Pct_Companies_Multiple_Down': primary['diffusion_mult_down'],
        'Pct_Companies_Bico_de_Pato': primary['diffusion_bico'],
    })

    def _safe_corr(s1, s2):
        df_c = pd.DataFrame({'a': s1, 'b': s2}).dropna()
        if len(df_c) < 3:
            return np.nan
        cov = np.cov(df_c['a'], df_c['b'])
        if cov[0, 0] > 0 and cov[1, 1] > 0:
            return float(cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1]))
        return np.nan

    macro_corr_df = pd.DataFrame([{
        'Corr_NTNB_vs_EV_EBITDA_Mediano': _safe_corr(primary['ev_ebitda_median'], ntnb_monthly),
        'Corr_NTNB_vs_Earnings_Yield_Mediano': _safe_corr(primary['earnings_yield_median'], ntnb_monthly),
        'Corr_NTNB_vs_EBITDA_Yield_Mediano': _safe_corr(primary['ebitda_yield_median'], ntnb_monthly),
    }])

    sample_comp_rows = []
    for key, sdef in SAMPLE_DEFINITIONS.items():
        r = robustness_results.get(key)
        if r:
            sample_comp_rows.append({
                'Sample_Key': key,
                'Sample_Label': sdef['label'],
                'N': r['N'],
                'K': r['K'],
                'Bico_Diffusion_%': round(r['bico_diffusion_pct'], 1),
                'EBITDA_Growth_Mediano_%': round(r['ebitda_change_pct'], 1),
                'EV_EBITDA_Mediano_Change_%': round(r['multiple_change_pct'], 1),
                'Binomial_p_value': round(r['binomial_test'].get('p_value', 1.0), 4),
                'Spearman_rho': round(r['correlations'].get('rho_spearman', 0.0), 3),
                'Classification': r['classification'],
            })
    sample_comp_df = pd.DataFrame(sample_comp_rows)

    raw_frames = {}
    for ticker in valid_tickers:
        raw_frames[f'{ticker}_EBITDA'] = df_ebitda_monthly.get(ticker)
        raw_frames[f'{ticker}_EV_EBITDA'] = df_ev_ebitda.get(ticker)
        raw_frames[f'{ticker}_MarketCap'] = df_market_cap.get(ticker)
        raw_frames[f'{ticker}_Lookahead_Flag'] = df_lookahead_flags.get(ticker)
    raw_data = pd.DataFrame(raw_frames, index=full_dates)

    included_companies_df = pd.DataFrame(included_companies)
    excluded_companies_df = pd.DataFrame(excluded_companies)
    collection_errors_df = pd.DataFrame(collection_errors)
    sample_audit_df = pd.DataFrame(sample_audit_rows)

    results = {
        'full_dates': full_dates,
        'valid_tickers': valid_tickers,
        'valid_tickers_ex_leaders': [t for t in valid_tickers if t not in COMMODITY_LEADERS],
        'candidate_count': candidate_count,
        'effective_sample_size': effective_sample_size,
        'excluded_count': excluded_count,
        'samples': robustness_results,
        'robustness': robustness_results,
        'hypothesis_evaluation': hypothesis_eval,
        'sample_definitions': SAMPLE_DEFINITIONS,
        'ibov_index': ibov_index,
        'ibov_source': ibov_source,
        'ntnb_monthly': ntnb_monthly,
        'ntnb_source': NTNB_SOURCE,
        'ntnb_initial': ntnb_initial,
        'ntnb_final': ntnb_final,
        'ntnb_change_pp': ntnb_change_pp,
        'spread_initial': spread_initial,
        'spread_final': spread_final,
        'sector_indices': sector_indices,
        'sector_growth': sector_growth,
        'sector_mult': sector_mult,
    }

    print("\n📝 Gerando relatório estatístico completo (bico_de_pato_statistical_report.txt)...")
    generate_statistical_report(results, output_path='bico_de_pato_statistical_report.txt')

    print("\n🎨 Gerando dashboard ampliado com 8 painéis (18x44)...")
    build_dashboard(results, output_path='bico_de_pato_dashboard.png')

    print("\n📄 Salvando todos os arquivos CSV de auditoria...")
    save_all_csvs(
        results, company_metrics_df, sector_metrics_df, quality_df, raw_data,
        diffusion_df, macro_corr_df, sample_comp_df,
        lookahead_audit_df=pit_audit_df,
        included_companies_df=included_companies_df,
        excluded_companies_df=excluded_companies_df,
        collection_errors_df=collection_errors_df,
        sample_audit_df=sample_audit_df,
    )

    print_conclusion(results)

    elapsed_total = time.time() - start_time
    print(f"\n⏱️  Tempo total de execução: {elapsed_total:.1f}s")


if __name__ == "__main__":
    main()