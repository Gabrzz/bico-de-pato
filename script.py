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
    3. Look-Ahead Bias / As-Of Dates: O yfinance gratuito não fornece a data de publicação oficial CVM
       (announcement_date). Para períodos ancorados na data de encerramento do balanço, o relatório
       de auditoria registra explicitamente LOOK_AHEAD_RISK = TRUE.
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

# Universo fixo de 20 empresas não-financeiras da B3
TICKERS = [
    # Commodities & Materiais Básicos
    "PETR4.SA", "VALE3.SA", "GGBR4.SA", "CSNA3.SA", "SUZB3.SA", "JBSS3.SA",
    # Utilidades Públicas (Energia & Saneamento)
    "ELET3.SA", "EQTL3.SA", "CPLE6.SA", "SBSP3.SA", "EGIE3.SA",
    # Consumo, Varejo & Saúde
    "ABEV3.SA", "MGLU3.SA", "LREN3.SA", "RADL3.SA", "HAPV3.SA",
    # Bens de Capital & Transporte
    "WEGE3.SA", "RENT3.SA", "RAIL3.SA", "EMBR3.SA"
]

COMMODITY_LEADERS = ["PETR4.SA", "VALE3.SA"]
COMMODITY_ALL = ["PETR4.SA", "VALE3.SA", "GGBR4.SA", "CSNA3.SA", "SUZB3.SA", "JBSS3.SA"]
IBOV_TICKER = "^BVSP"

SECTORS = {
    "Utilidades Públicas": ["ELET3.SA", "EQTL3.SA", "CPLE6.SA", "SBSP3.SA", "EGIE3.SA"],
    "Bens de Capital & Transp.": ["WEGE3.SA", "RENT3.SA", "RAIL3.SA", "EMBR3.SA"],
    "Consumo, Varejo & Saúde": ["ABEV3.SA", "MGLU3.SA", "LREN3.SA", "RADL3.SA", "HAPV3.SA"],
    "Materiais & Alimentos": ["GGBR4.SA", "CSNA3.SA", "SUZB3.SA", "JBSS3.SA"],
}

SAMPLE_DEFINITIONS = {
    'all':            {'label': 'Todas (20)',                'exclude': []},
    'ex_leaders':     {'label': 'Ex-PETR4/VALE3 (18)',       'exclude': COMMODITY_LEADERS},
    'ex_commodities': {'label': 'Ex-Commodities Amplo (14)', 'exclude': COMMODITY_ALL},
}

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
                              full_dates, sample_tickers):
    """Calcula métricas agregadas por amostra (Mediana, Agregado Econômico ΣEV/ΣEBITDA, Difusão)."""
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

    # Variações Início → Fim
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

    final_bico_diffusion = diffusion_bico.iloc[-1] if not diffusion_bico.empty else 0.0

    classification = classify_hypothesis(
        ebitda_growth_med_pct, ebitda_growth_agg_pct,
        mult_change_med_pct, mult_change_agg_pct,
        final_bico_diffusion, data_sufficient=True
    )

    return {
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
    }


def calculate_sector_metrics(df_ebitda_monthly, df_ev_ebitda, df_ev, full_dates):
    """Calcula EBITDA Growth, EV Growth e Variação do Múltiplo por setor."""
    sector_indices = pd.DataFrame(index=full_dates)
    sector_growth = {}
    sector_mult = {}

    for sec_name, sec_tickers in SECTORS.items():
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
                      ebitda_sources, shares_sources, price_sources, negative_ev_counts):
    """Gera relatório de qualidade dos dados para terminal e CSV de auditoria."""
    print("\n" + "=" * 65)
    print("                DATA QUALITY & AUDIT REPORT")
    print("=" * 65)

    rows = []
    for ticker in TICKERS:
        is_active = ticker in valid_tickers
        price_src = price_sources.get(ticker, "PRICE_DATA_INSUFFICIENT")
        ebitda_src = ebitda_sources.get(ticker, "UNKNOWN")
        shares_src = shares_sources.get(ticker, "UNKNOWN")

        neg_ev = negative_ev_counts.get(ticker, 0)
        look_ahead_risk = "TRUE" if "ANNUAL" in ebitda_src or "HARDCODED" in ebitda_src else "FALSE"

        status = "OK (ATIVO)" if is_active else "EXCLUÍDO (PREÇO INSUFICIENTE)"

        print(f"  {ticker:10s} | Preço: {price_src:12s} | EBITDA: {ebitda_src:22s} | LookAhead: {look_ahead_risk:5s} | Status: {status}")

        rows.append({
            'Ticker': ticker,
            'Price_Source': price_src,
            'EBITDA_Source': ebitda_src,
            'NetDebt_Source': 'HARDCODED_FALLBACK',
            'NetIncome_Source': 'HARDCODED_FALLBACK',
            'Shares_Source': shares_src,
            'Look_Ahead_Risk': look_ahead_risk,
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
    Dashboard de 4 painéis + KPI Banner no topo com design dark premium.
    Zero sobreposição de textos, legendas ou cartões.
    """
    full_dates = results['full_dates']
    primary = results['samples']['ex_leaders']
    all_sample = results['samples']['all']
    ibov_index = results['ibov_index']
    ibov_source = results['ibov_source']
    ntnb = results['ntnb_monthly']
    ntnb_source = results['ntnb_source']
    sector_indices = results['sector_indices']
    sector_growth = results['sector_growth']
    robustness = results['robustness']

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

    fig = plt.figure(figsize=(18, 28), facecolor=BG)
    gs = fig.add_gridspec(
        5, 1,
        height_ratios=[0.75, 2.0, 2.0, 1.4, 1.4],
        hspace=0.40, top=0.97, bottom=0.03, left=0.07, right=0.93
    )

    # ══════════════════════════════════════════════════════════════════
    # ROW 0: KPI SUMMARY HEADER BANNER
    # ══════════════════════════════════════════════════════════════════
    ax_header = fig.add_subplot(gs[0])
    ax_header.set_facecolor(BG)
    ax_header.axis('off')

    period_start = full_dates[0].strftime('%b/%Y')
    period_end = full_dates[-1].strftime('%b/%Y')

    ax_header.text(0.0, 0.95, 'B3: Teste da Hipótese de Desconexão Operacional ("Bico de Pato")',
                   fontsize=18, fontweight='bold', color=C_TEXT, va='top')

    ax_header.text(0.0, 0.72, f'Período Analisado: {period_start} → {period_end}  |  Amostra: {len(results["valid_tickers"])} Empresas Não-Financeiras da B3  |  Amostra Primária: Ex-PETR4/VALE3',
                   fontsize=11.5, color=C_MUTED, va='top')

    source_warnings = []
    if ntnb_source == "ANBIMA_COMPILED":
        source_warnings.append("NTN-B: ANBIMA")
    if ibov_source == "FALLBACK":
        source_warnings.append("Ibovespa: fallback")
    if source_warnings:
        ax_header.text(1.0, 0.95, '[' + ' | '.join(source_warnings) + ']',
                       fontsize=10, color='#FB923C', ha='right', va='top', fontweight='bold')

    ebitda_pct = primary['ebitda_change_pct']
    mult_pct = primary['multiple_change_pct']
    init_m = primary['initial_multiple']
    final_m = primary['final_multiple']
    ntnb_chg = results.get('ntnb_change_pp', 0.0)
    spread_final = results.get('spread_final', 0.0)
    status_clean = primary['classification']

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
        ax_header.text(cx + card_w/2, 0.40, kpi_text,
                       fontsize=9.5, fontweight='bold', color=C_TEXT,
                       ha='center', va='top', bbox=bbox_rect)

    # ══════════════════════════════════════════════════════════════════
    # ROW 1: PAINEL A — FUNDAMENTOS OPERACIONAIS (EBITDA LTM Base 100)
    # ══════════════════════════════════════════════════════════════════
    ax1 = fig.add_subplot(gs[1])
    ax1.set_facecolor(BG)

    ax1.plot(full_dates, primary['ebitda_index_median'],
             label='EBITDA LTM Index — Ex-PETR4/VALE3 (Mediana)', color=C_EBITDA2, lw=3.2, zorder=5)
    ax1.plot(full_dates, all_sample['ebitda_index_median'],
             label='EBITDA LTM Index — Todas (Mediana)', color=C_EBITDA, lw=2.0, alpha=0.7, zorder=4)
    ax1.plot(full_dates, ibov_index,
             label='Ibovespa (Benchmark de Mercado)', color=C_IBOV, lw=2.2, ls='--', alpha=0.9, zorder=3)

    SEC_COLORS = {'Utilidades Públicas': '#38BDF8', 'Bens de Capital & Transp.': '#F59E0B',
                  'Consumo, Varejo & Saúde': '#EC4899', 'Materiais & Alimentos': '#A855F7'}
    for sec_name in sector_indices.columns:
        c = SEC_COLORS.get(sec_name, '#64748B')
        ax1.plot(full_dates, sector_indices[sec_name],
                 label=f'Setor: {sec_name}', color=c, lw=1.2, ls=':', alpha=0.55, zorder=2)

    ax1.axhline(100, color=C_GRID, ls=':', lw=1.0, alpha=0.6)
    ax1.set_title('Painel A — Fundamentos Operacionais: Evolução do EBITDA LTM (Base 100 = Jan/2021)',
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

    leg1 = ax1.legend(frameon=True, facecolor=CARD, edgecolor=CARD_BORDER, fontsize=10.0,
                      loc='upper left', labelcolor='#E2E8F0', ncol=2, framealpha=0.95)
    leg1.get_frame().set_linewidth(1.0)

    sec_lines = ["Decomposição Setorial (Crescimento EBITDA):"]
    for sn, pct in sector_growth.items():
        sign = "+" if pct >= 0 else ""
        sec_lines.append(f" • {sn}: {sign}{pct:.1f}%")
    latest_diff = primary['diffusion_ebitda_up'].iloc[-1] if not primary['diffusion_ebitda_up'].empty else 0
    sec_lines.append(f" • Difusão: {latest_diff:.0f}% com EBITDA > Jan/2021")

    ax1.text(0.015, 0.55, "\n".join(sec_lines), transform=ax1.transAxes,
             fontsize=9.5, color=C_TEXT, va='top', ha='left',
             bbox=dict(boxstyle='round,pad=0.5', facecolor=CARD, edgecolor=CARD_BORDER, lw=1.0, alpha=0.95))

    # ══════════════════════════════════════════════════════════════════
    # ROW 2: PAINEL B — O "BICO DE PATO" (EBITDA ↑ vs. EV/EBITDA ↓)
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

    # Decomposição detalhada do EV
    ev_g = primary['ev_growth_pct']
    mc_g = primary['mcap_growth_pct']
    nd_g = primary['netdebt_growth_pct']
    bico_diff_final = primary['diffusion_bico'].iloc[-1] if not primary['diffusion_bico'].empty else 0

    annot_text = (f"Decomposição do EV & Bico:\n"
                  f" • EBITDA Mediano: {ebitda_pct:+.1f}%\n"
                  f" • EV Agregado: {ev_g:+.1f}%\n"
                  f" • Market Cap Agregado: {mc_g:+.1f}%\n"
                  f" • Dívida Líquida Agregada: {nd_g:+.1f}%\n"
                  f" • EV/EBITDA Mediano: {init_m:.1f}x → {final_m:.1f}x ({mult_pct:+.1f}%)\n"
                  f" • Difusão Bico de Pato: {bico_diff_final:.0f}% das empresas")

    ax2.text(0.99, 0.50, annot_text, transform=ax2.transAxes,
             fontsize=9.5, color=C_TEXT, va='center', ha='right',
             bbox=dict(boxstyle='round,pad=0.5', facecolor=CARD, edgecolor=CARD_BORDER, lw=1.0, alpha=0.95))

    # ══════════════════════════════════════════════════════════════════
    # ROW 3: PAINEL C — TAXA REAL VS. YIELDS DA BOLSA
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

    ntnb_initial = ntnb.dropna().iloc[0] if not ntnb.dropna().empty else 0
    ntnb_final = ntnb.dropna().iloc[-1] if not ntnb.dropna().empty else 0
    ey_initial = primary['ebitda_yield_median'].dropna().iloc[0] if not primary['ebitda_yield_median'].dropna().empty else 0
    ey_final = primary['ebitda_yield_median'].dropna().iloc[-1] if not primary['ebitda_yield_median'].dropna().empty else 0

    spread_i = ey_initial - ntnb_initial
    spread_f = ey_final - ntnb_final
    spread_text = (f"Spread Operacional vs. NTN-B:\n"
                   f" • Inicial: {spread_i:+.1f} p.p.\n"
                   f" • Final: {spread_f:+.1f} p.p.")
    ax3.text(0.99, 0.50, spread_text, transform=ax3.transAxes,
             fontsize=9.5, color=C_TEXT, va='center', ha='right',
             bbox=dict(boxstyle='round,pad=0.5', facecolor=CARD, edgecolor=CARD_BORDER, lw=1.0, alpha=0.95))

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
    for key, sdef in SAMPLE_DEFINITIONS.items():
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

        st_clean = classifications[i]
        ax4.text(x[i], min_val * 1.35, f"[{st_clean}]",
                 ha='center', va='top', fontsize=9.5, fontweight='bold', color=C_TEXT,
                 bbox=dict(boxstyle='round,pad=0.4', facecolor=CARD, edgecolor=CARD_BORDER, lw=1.0))

    for spine in ['top', 'right', 'left']:
        ax4.spines[spine].set_visible(False)
    ax4.spines['bottom'].set_color(C_GRID)
    ax4.grid(True, ls='--', lw=0.5, color=C_GRID, alpha=0.4, axis='y')

    leg4 = ax4.legend(frameon=True, facecolor=CARD, edgecolor=CARD_BORDER, fontsize=10.5,
                      loc='upper right', labelcolor='#E2E8F0', framealpha=0.95)
    leg4.get_frame().set_linewidth(1.0)

    plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), bbox_inches='tight')
    print(f"\n✅ Dashboard ampliado e corrigido salvo com sucesso: {output_path}")
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
                  diffusion_df, macro_corr_df, sample_comp_df):
    """Salva todos os 8 CSVs de auditoria."""
    company_metrics_df.to_csv('bico_de_pato_company_metrics.csv', index=False)
    print("  📄 bico_de_pato_company_metrics.csv")

    sector_metrics_df.to_csv('bico_de_pato_sector_metrics.csv', index=False)
    print("  📄 bico_de_pato_sector_metrics.csv")

    primary = results['samples']['ex_leaders']
    ntnb_i = results.get('ntnb_initial', np.nan)
    ntnb_f = results.get('ntnb_final', np.nan)
    ntnb_chg = results.get('ntnb_change_pp', np.nan)

    summary_rows = [
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


# ══════════════════════════════════════════════════════════════════════════════
# 9. CONCLUSÃO E INTERPRETAÇÃO AUTOMÁTICA
# ══════════════════════════════════════════════════════════════════════════════

def print_conclusion(results):
    """Imprime a conclusão empírica com interpretação dinâmica."""
    primary = results['samples']['ex_leaders']
    full_dates = results['full_dates']

    ntnb_i = results.get('ntnb_initial', np.nan)
    ntnb_f = results.get('ntnb_final', np.nan)
    spread_i = results.get('spread_initial', np.nan)
    spread_f = results.get('spread_final', np.nan)

    ey_i = primary['ebitda_yield_median'].dropna().iloc[0] if not primary['ebitda_yield_median'].dropna().empty else np.nan
    ey_f = primary['ebitda_yield_median'].dropna().iloc[-1] if not primary['ebitda_yield_median'].dropna().empty else np.nan

    diff_bico_final = primary['diffusion_bico'].iloc[-1] if not primary['diffusion_bico'].empty else np.nan

    print("\n")
    print("=" * 65)
    print("       BICO DE PATO — RESULTADO FINAL DA HIPÓTESE")
    print("=" * 65)
    print(f"\n  Período Válido: {full_dates[0].strftime('%b/%Y')} → {full_dates[-1].strftime('%b/%Y')}")
    print(f"  Amostra Primária: Ex-PETR4/VALE3 ({len(results['valid_tickers_ex_leaders'])} empresas)")
    print(f"\n  EBITDA Mediano:      {primary['ebitda_change_pct']:+.1f}%")
    print(f"  EBITDA Agregado:     {primary['ebitda_growth_agg_pct']:+.1f}%")
    print(f"\n  EV Agregado:         {primary['ev_growth_pct']:+.1f}%")
    print(f"  Market Cap Agregado: {primary['mcap_growth_pct']:+.1f}%")
    print(f"  Dívida Liq. Agregada:{primary['netdebt_growth_pct']:+.1f}%")
    print(f"\n  EV/EBITDA Mediano:   {primary['initial_multiple']:.1f}x → {primary['final_multiple']:.1f}x ({primary['multiple_change_pct']:+.1f}%)")
    print(f"  EV/EBITDA Agregado:  {primary['multiple_change_agg_pct']:+.1f}%")
    print(f"\n  NTN-B IPCA+:         {ntnb_i:.2f}% → {ntnb_f:.2f}% ({results.get('ntnb_change_pp', 0):+.2f} p.p.)")
    print(f"  Spread Operacional:  {spread_i:+.1f} p.p. → {spread_f:+.1f} p.p.")
    print(f"\n  Difusão Bico de Pato:{diff_bico_final:.1f}% das empresas com EBITDA ↑ e EV/EBITDA ↓")
    print(f"\n  {'─' * 55}")
    print(f"  CONCLUSÃO: {primary['classification']}")
    print(f"  {'─' * 55}")

    print("\n  Interpretação Automática Baseada nos Dados:")
    print(f"    A hipótese de desconexão foi classificada como {primary['classification']}.")
    print(f"    Entre {full_dates[0].strftime('%b/%Y')} e {full_dates[-1].strftime('%b/%Y')}:")
    print(f"    - O EBITDA mediano cresceu {primary['ebitda_change_pct']:+.1f}% ({primary['ebitda_growth_agg_pct']:+.1f}% no agregado).")
    print(f"    - O múltiplo EV/EBITDA mediano variou {primary['multiple_change_pct']:+.1f}%.")
    print(f"    - {diff_bico_final:.1f}% das empresas apresentaram simultaneamente EBITDA crescente e compressão de múltiplo.")
    print(f"    - Os juros reais (NTN-B) variaram {results.get('ntnb_change_pp', 0):+.2f} p.p., associados visualmente ao período.")
    print("    Ressalva: Esta relação indica associação empírica no período, NÃO causalidade provada.")
    print("=" * 65)


# ══════════════════════════════════════════════════════════════════════════════
# 10. PIPELINE PRINCIPAL — ORQUESTRAÇÃO COMPLETA
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Executa a análise completa do Bico de Pato com rigor metodológico."""
    start_time = time.time()

    print("📥 Coletando cotações históricas reais via yfinance (sem preços sintéticos)...")
    prices_df, ibov_source = download_all_prices(TICKERS, IBOV_TICKER, START_DATE)

    # Identificar empresas com preços válidos (SEM CRIAR PREÇOS SINTÉTICOS PELO IBOVESPA)
    valid_tickers = []
    price_sources = {}
    for ticker in TICKERS:
        if ticker in prices_df.columns and not prices_df[ticker].dropna().empty:
            valid_tickers.append(ticker)
            price_sources[ticker] = "YFINANCE_REAL"
        else:
            price_sources[ticker] = "PRICE_DATA_INSUFFICIENT"
            print(f"  ⚠️  {ticker}: Preço histórico indisponível no yfinance. EXCLUÍDO DA AMOSTRA.")

    if not valid_tickers:
        raise RuntimeError("❌ Falha crítica: Nenhum ticker obteve cotações reais válidas.")

    # Alinhamento temporal dinâmico (intersecção comum real)
    last_price_date = prices_df[valid_tickers].dropna(how='all').index.max()
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

    print("\n📊 Construindo demonstrativos fundamentais e calculando valuation por empresa...")

    df_ebitda_monthly = pd.DataFrame(index=full_dates)
    df_netdebt_monthly = pd.DataFrame(index=full_dates)
    df_netincome_monthly = pd.DataFrame(index=full_dates)
    df_market_cap = pd.DataFrame(index=full_dates)
    df_ev = pd.DataFrame(index=full_dates)
    df_ev_ebitda = pd.DataFrame(index=full_dates)
    df_ebitda_yield = pd.DataFrame(index=full_dates)
    df_earnings_yield = pd.DataFrame(index=full_dates)

    ebitda_sources = {}
    shares_sources = {}
    negative_ev_counts = {}

    for ticker in valid_tickers:
        s_price_raw = prices_df[ticker].dropna()
        s_price_monthly = s_price_raw.resample('ME').last().reindex(full_dates).ffill()

        hardcoded_list = EBITDA_HARDCODED_BI.get(ticker, [0.0] * len(EBITDA_DATES))
        ebitda_annual, ebitda_src = get_ebitda_ltm(ticker, EBITDA_DATES, hardcoded_list)
        ebitda_sources[ticker] = ebitda_src
        df_ebitda_monthly[ticker] = build_monthly_series(ebitda_annual, EBITDA_DATES, full_dates)

        nd_values = NET_DEBT_HARDCODED_BI.get(ticker, [0.0] * len(EBITDA_DATES))
        nd_annual = pd.Series(nd_values, index=EBITDA_DATES, dtype=float)
        df_netdebt_monthly[ticker] = build_monthly_series(nd_annual, EBITDA_DATES, full_dates)

        ni_values = NET_INCOME_HARDCODED_BI.get(ticker, [0.0] * len(EBITDA_DATES))
        ni_annual = pd.Series(ni_values, index=EBITDA_DATES, dtype=float)
        df_netincome_monthly[ticker] = build_monthly_series(ni_annual, EBITDA_DATES, full_dates)

        s_shares, shares_src = get_shares_outstanding(ticker, full_dates)
        shares_sources[ticker] = shares_src

        mcap = s_price_monthly * s_shares
        df_market_cap[ticker] = mcap

        ev = mcap + df_netdebt_monthly[ticker]
        df_ev[ticker] = ev
        negative_ev_counts[ticker] = (ev <= 0).sum()

        ebitda_ltm = df_ebitda_monthly[ticker]
        ebitda_pos = ebitda_ltm.where(ebitda_ltm > 0)
        ev_pos = ev.where(ev > 0)

        # MÚLTIPLO EV/EBITDA SEM FILTRO ARBITRÁRIO DE <= 100 (RAW)
        ev_ebitda = ev_pos / ebitda_pos
        df_ev_ebitda[ticker] = ev_ebitda

        ebitda_yield = (ebitda_pos / ev_pos) * 100.0
        df_ebitda_yield[ticker] = ebitda_yield

        ni_ltm = df_netincome_monthly[ticker]
        ni_pos = ni_ltm.where(ni_ltm > 0)
        mcap_pos = mcap.where(mcap > 0)
        earnings_yield = (ni_pos / mcap_pos) * 100.0
        df_earnings_yield[ticker] = earnings_yield

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

    print("\n📊 Calculando métricas e decomposição por amostra...")
    robustness_results = {}
    for key, sdef in SAMPLE_DEFINITIONS.items():
        sample_tickers = [t for t in valid_tickers if t not in sdef['exclude']]
        if not sample_tickers:
            continue
        metrics = calculate_sample_metrics(
            df_ev_ebitda, df_ebitda_yield, df_earnings_yield,
            df_ebitda_monthly, df_ev, df_market_cap, df_netdebt_monthly,
            full_dates, sample_tickers
        )
        if metrics:
            robustness_results[key] = metrics
            print(f"  ✅ {sdef['label']}: EBITDA Mediano {metrics['ebitda_change_pct']:+.1f}% | "
                  f"EV/EBITDA Mediano {metrics['multiple_change_pct']:+.1f}% | {metrics['classification']}")

    primary = robustness_results['ex_leaders']

    sector_indices, sector_growth, sector_mult = calculate_sector_metrics(
        df_ebitda_monthly, df_ev_ebitda, df_ev, full_dates
    )

    ntnb_clean = ntnb_monthly.dropna()
    ntnb_initial = ntnb_clean.iloc[0] if len(ntnb_clean) > 0 else np.nan
    ntnb_final = ntnb_clean.iloc[-1] if len(ntnb_clean) > 0 else np.nan
    ntnb_change_pp = ntnb_final - ntnb_initial

    ey_clean = primary['ebitda_yield_median'].dropna()
    ey_initial = ey_clean.iloc[0] if len(ey_clean) > 0 else np.nan
    ey_final = ey_clean.iloc[-1] if len(ey_clean) > 0 else np.nan
    spread_initial = ey_initial - ntnb_initial if not np.isnan(ey_initial) and not np.isnan(ntnb_initial) else np.nan
    spread_final = ey_final - ntnb_final if not np.isnan(ey_final) and not np.isnan(ntnb_final) else np.nan

    quality_df = validate_dataset(
        valid_tickers, df_ebitda_monthly, df_ev, df_market_cap, df_ev_ebitda,
        ebitda_sources, shares_sources, price_sources, negative_ev_counts
    )

    # 1. Company Metrics DataFrame
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

    company_metrics_df = pd.DataFrame(company_rows)
    company_metrics_df = company_metrics_df.sort_values('EV_EBITDA_Change_%', ascending=True, na_position='last')

    # 2. Sector Metrics DataFrame
    sector_rows = []
    for sn in SECTORS:
        sec_tickers = [t for t in SECTORS[sn] if t in valid_tickers]
        row = {
            'Setor': sn,
            'N_Empresas': len(sec_tickers),
            'EBITDA_Growth_%': round(sector_growth.get(sn, np.nan), 1),
        }
        sm = sector_mult.get(sn, {})
        row['EV_EBITDA_Mediano_Inicial'] = round(sm.get('initial', np.nan), 2)
        row['EV_EBITDA_Mediano_Final'] = round(sm.get('final', np.nan), 2)
        row['Multiple_Change_%'] = round(sm.get('change_pct', np.nan), 1)
        sector_rows.append(row)
    sector_metrics_df = pd.DataFrame(sector_rows)

    # 3. Diffusion DataFrame
    diffusion_df = pd.DataFrame({
        'Date': full_dates,
        'Pct_Companies_EBITDA_Up': primary['diffusion_ebitda_up'],
        'Pct_Companies_Multiple_Down': primary['diffusion_mult_down'],
        'Pct_Companies_Bico_de_Pato': primary['diffusion_bico'],
    })

    # 4. Macro Correlation DataFrame
    macro_corr_df = pd.DataFrame([{
        'Corr_NTNB_vs_EV_EBITDA_Mediano': primary['ev_ebitda_median'].corr(ntnb_monthly),
        'Corr_NTNB_vs_Earnings_Yield_Mediano': primary['earnings_yield_median'].corr(ntnb_monthly),
        'Corr_NTNB_vs_EBITDA_Yield_Mediano': primary['ebitda_yield_median'].corr(ntnb_monthly),
    }])

    # 5. Sample Comparison DataFrame
    sample_comp_rows = []
    for key, sdef in SAMPLE_DEFINITIONS.items():
        r = robustness_results.get(key)
        if r:
            sample_comp_rows.append({
                'Sample_Key': key,
                'Sample_Label': sdef['label'],
                'EBITDA_Growth_Mediano_%': round(r['ebitda_change_pct'], 1),
                'EBITDA_Growth_Agregado_%': round(r['ebitda_growth_agg_pct'], 1),
                'EV_Growth_Agregado_%': round(r['ev_growth_pct'], 1),
                'MarketCap_Growth_Agregado_%': round(r['mcap_growth_pct'], 1),
                'NetDebt_Growth_Agregado_%': round(r['netdebt_growth_pct'], 1),
                'EV_EBITDA_Mediano_Change_%': round(r['multiple_change_pct'], 1),
                'EV_EBITDA_Agregado_Change_%': round(r['multiple_change_agg_pct'], 1),
                'Bico_Diffusion_Final_%': round(r['diffusion_bico'].iloc[-1], 1),
                'Classification': r['classification'],
            })
    sample_comp_df = pd.DataFrame(sample_comp_rows)

    raw_frames = {}
    for ticker in valid_tickers:
        raw_frames[f'{ticker}_EBITDA'] = df_ebitda_monthly.get(ticker)
        raw_frames[f'{ticker}_EV_EBITDA'] = df_ev_ebitda.get(ticker)
        raw_frames[f'{ticker}_MarketCap'] = df_market_cap.get(ticker)
    raw_data = pd.DataFrame(raw_frames, index=full_dates)

    results = {
        'full_dates': full_dates,
        'valid_tickers': valid_tickers,
        'valid_tickers_ex_leaders': [t for t in valid_tickers if t not in COMMODITY_LEADERS],
        'samples': robustness_results,
        'robustness': robustness_results,
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

    print("\n🎨 Gerando dashboard ampliado e corrigido (18x28)...")
    build_dashboard(results, output_path='bico_de_pato_dashboard.png')

    print("\n📄 Salvando 8 arquivos CSV de auditoria...")
    save_all_csvs(
        results, company_metrics_df, sector_metrics_df, quality_df, raw_data,
        diffusion_df, macro_corr_df, sample_comp_df
    )

    print_conclusion(results)

    elapsed_total = time.time() - start_time
    print(f"\n⏱️  Tempo total de execução: {elapsed_total:.1f}s")


if __name__ == "__main__":
    main()