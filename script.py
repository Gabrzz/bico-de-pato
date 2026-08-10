import time
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker

# ==========================================
# 1. CONFIGURAÇÕES GERAIS & AMOSTRA (EMPRESAS NÃO-FINANCEIRAS DA B3)
# ==========================================
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
IBOV_TICKER = "^BVSP"

# Mapeamento de Setores para Decomposição Setorial
SECTORS = {
    "Utilidades Públicas": ["ELET3.SA", "EQTL3.SA", "CPLE6.SA", "SBSP3.SA", "EGIE3.SA"],
    "Bens de Capital & Transp.": ["WEGE3.SA", "RENT3.SA", "RAIL3.SA", "EMBR3.SA"],
    "Consumo, Varejo & Saúde": ["ABEV3.SA", "MGLU3.SA", "LREN3.SA", "RADL3.SA", "HAPV3.SA"],
    "Materiais/Aliment. Ex-Líderes": ["GGBR4.SA", "CSNA3.SA", "SUZB3.SA", "JBSS3.SA"]
}

# ==========================================
# 2. DADOS FUNDAMENTAIS E MACROINFORMATIVOS (IN-CODE COM FALLBACKS)
# Períodos das demonstrações financeiras: [2020-12-31, 2021-12-31, 2022-12-31, 2023-12-31, 2024-12-31, 2025-12-31]
# ==========================================
EBITDA_DATES = pd.to_datetime(['2020-12-31', '2021-12-31', '2022-12-31', '2023-12-31', '2024-12-31', '2025-12-31'])

# 2.1 EBITDA LTM Consolidado (R$ Bilhões)
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
    "EMBR3.SA": [2.016, 2.331, 2.805, 4.487, 4.265, 5.248]
}

# 2.2 Dívida Líquida Consolidada (R$ Bilhões) — Valores negativos representam caixa líquido
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
    "EMBR3.SA": [8.5, 7.2, 6.8, 5.4, 4.8, 4.2]
}

# 2.3 Lucro Líquido LTM Consolidado (R$ Bilhões) — Para cálculo do Earnings Yield (1 / (P/L))
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
    "EMBR3.SA": [-3.620, 0.390, 0.780, 0.920, 1.180, 1.520]
}

# 2.4 Número Total de Ações em Circulação (Bilhões) — Usado como Fallback se yfinance falhar
SHARES_OUTSTANDING_FALLBACK_BI = {
    "PETR4.SA": 13.04,
    "VALE3.SA": 4.54,
    "GGBR4.SA": 1.72,
    "CSNA3.SA": 1.33,
    "SUZB3.SA": 1.30,
    "JBSS3.SA": 2.22,
    "ELET3.SA": 2.30,
    "EQTL3.SA": 1.15,
    "CPLE6.SA": 2.94,
    "SBSP3.SA": 0.684,
    "EGIE3.SA": 0.815,
    "ABEV3.SA": 15.73,
    "MGLU3.SA": 0.67,
    "LREN3.SA": 1.00,
    "RADL3.SA": 1.72,
    "HAPV3.SA": 7.53,
    "WEGE3.SA": 4.19,
    "RENT3.SA": 1.06,
    "RAIL3.SA": 1.85,
    "EMBR3.SA": 0.74
}

# 2.5 Taxa Real de Juros NTN-B 10Y (IPCA+ % a.a.) — Série Mensal de Fechamentos ANBIMA (2021 a 2026)
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
    '2026-01-31': 7.35
}

# ==========================================
# 3. FUNÇÃO PARA BUSCA DINÂMICA DE SHARES OUTSTANDING VIA YFINANCE
# ==========================================
def fetch_shares_history(ticker: str, full_dates: pd.DatetimeIndex) -> pd.Series:
    """
    Busca dinamicamente a série histórica de ações em circulação via yfinance (get_shares_full).
    Reinterpreta no horizonte full_dates (ffill/bfill) para evitar congelar shares no valor presente.
    Recorre a t.info (com retry/backoff) ou ao fallback in-code se indisponível.
    """
    fallback_val = SHARES_OUTSTANDING_FALLBACK_BI.get(ticker, 1.0)
    fallback_series = pd.Series(fallback_val, index=full_dates)
    
    try:
        t = yf.Ticker(ticker)
        # Tentativa 1: Histórico completo via get_shares_full()
        for attempt in range(2):
            try:
                shares_series = t.get_shares_full(start=START_DATE)
                if shares_series is not None and not shares_series.empty:
                    shares_series = shares_series.dropna()
                    if not shares_series.empty:
                        if shares_series.index.tz is not None:
                            shares_series.index = shares_series.index.tz_localize(None)
                        shares_series = shares_series / 1e9  # Converter para bilhões
                        
                        # Reindexar combinando com full_dates, ffill e bfill
                        combined_idx = shares_series.index.union(full_dates)
                        aligned_series = (
                            shares_series
                            .reindex(combined_idx)
                            .sort_index()
                            .ffill()
                            .bfill()
                            .reindex(full_dates)
                        )
                        if (aligned_series > 0).all():
                            return aligned_series
            except Exception:
                time.sleep(0.3)
        
        # Tentativa 2: Atributo info com retry e backoff
        for attempt in range(2):
            try:
                info_dict = t.info
                if info_dict and isinstance(info_dict, dict):
                    sh = info_dict.get('sharesOutstanding') or info_dict.get('impliedSharesOutstanding')
                    if sh and sh > 0:
                        return pd.Series(float(sh) / 1e9, index=full_dates)
            except Exception:
                time.sleep(0.5 * (attempt + 1))
                
    except Exception as e:
        print(f"  ℹ️ Notificação ({ticker}): Shares via yfinance indisponível ({e}). Usando fallback.")

    return fallback_series

# ==========================================
# 4. COLETA E RESILIÊNCIA DOS PREÇOS DOS ATIVOS & IBOVESPA
# ==========================================
def fetch_price_series(ticker: str, start_date: str) -> pd.Series:
    """
    Busca o histórico de preços de um ticker individualmente caso o download em lote falhe.
    Suporta busca em tickers alternativos (ex: CPLE6.SA -> CPLE3.SA).
    """
    candidate_tickers = [ticker]
    if ticker == "CPLE6.SA":
        candidate_tickers.append("CPLE3.SA")
    elif ticker == "ELET3.SA":
        candidate_tickers.append("ELET6.SA")

    for cand in candidate_tickers:
        for attempt in range(3):
            try:
                t = yf.Ticker(cand)
                hist = t.history(start=start_date, auto_adjust=False)
                if hist is not None and not hist.empty and 'Close' in hist.columns:
                    s_close = hist['Close'].dropna()
                    if not s_close.empty:
                        if s_close.index.tz is not None:
                            s_close.index = s_close.index.tz_localize(None)
                        return s_close
            except Exception:
                time.sleep(0.4 * (attempt + 1))
    return pd.Series(dtype=float)

print("📥 Coletando dados históricos de preços via yfinance...")
prices_df = pd.DataFrame()

try:
    download_data = yf.download([IBOV_TICKER] + TICKERS, start=START_DATE, auto_adjust=False, progress=False)['Close']
    if isinstance(download_data, pd.DataFrame) and not download_data.empty:
        prices_df = download_data
except Exception as e:
    print(f"⚠️ Erro no download em lote do yfinance: {e}")

# Tratamento do Ibovespa
if IBOV_TICKER in prices_df.columns and not prices_df[IBOV_TICKER].dropna().empty:
    ibov_monthly = prices_df[IBOV_TICKER].dropna().resample('ME').last()
else:
    # Proxy fixo do Ibovespa apenas para contingência da série de datas
    ibov_dates = pd.date_range(start=START_DATE, end='2026-01-31', freq='ME')
    ibov_simulated = [118873, 110035, 116634, 120891, 126216, 126802, 121801, 118780, 111037, 103500, 101915, 104822,
                      112143, 113161, 119999, 110526, 108335, 118082, 120187, 115742, 116560, 113143, 125666, 134185,
                      128159, 129020, 128158, 125924, 122098, 123906, 127652, 136000, 132000, 129000, 126000, 128500, 131000, 133500]
    ibov_monthly = pd.Series(ibov_simulated[:len(ibov_dates)], index=ibov_dates)

full_dates = ibov_monthly.index

# ==========================================
# 5. CONSTRUÇÃO E INTERPOLAÇÃO DAS SÉRIES MENSAIS DE BALANÇO & NTN-B
# ==========================================
df_ebitda_raw = pd.DataFrame(EBITDA_HARDCODED_BI, index=EBITDA_DATES)
df_netdebt_raw = pd.DataFrame(NET_DEBT_HARDCODED_BI, index=EBITDA_DATES)
df_netincome_raw = pd.DataFrame(NET_INCOME_HARDCODED_BI, index=EBITDA_DATES)

s_ntnb_raw = pd.Series(NTN_B_MONTHLY_DATA)
s_ntnb_raw.index = pd.to_datetime(s_ntnb_raw.index)

# Interpolador mensal linear contínuo sobre o calendário completo
df_ebitda_monthly = df_ebitda_raw.reindex(df_ebitda_raw.index.union(full_dates)).sort_index().interpolate(method='time').bfill().ffill().reindex(full_dates)
df_netdebt_monthly = df_netdebt_raw.reindex(df_netdebt_raw.index.union(full_dates)).sort_index().interpolate(method='time').bfill().ffill().reindex(full_dates)
df_netincome_monthly = df_netincome_raw.reindex(df_netincome_raw.index.union(full_dates)).sort_index().interpolate(method='time').bfill().ffill().reindex(full_dates)
s_ntnb_monthly = s_ntnb_raw.reindex(s_ntnb_raw.index.union(full_dates)).sort_index().interpolate(method='time').bfill().ffill().reindex(full_dates)

# ==========================================
# 6. CÁLCULO DE EV/EBITDA REAL, EBITDA YIELD E EARNINGS YIELD (EMPRESA A EMPRESA)
# ==========================================
print("📊 Calculando EV/EBITDA, EBITDA Yield e Earnings Yield com Shares dinâmicos...")
df_ev_ebitda_companies = pd.DataFrame(index=full_dates)
df_ebitda_yield_companies = pd.DataFrame(index=full_dates)
df_earnings_yield_companies = pd.DataFrame(index=full_dates)

valid_tickers = []

for ticker in TICKERS:
    # 1. Preço mensal da ação: tenta do lote e recorre à busca individual com fallback se falhar
    s_price_raw = None
    if ticker in prices_df.columns and not prices_df[ticker].dropna().empty:
        s_price_raw = prices_df[ticker].dropna()

    if s_price_raw is None or s_price_raw.empty:
        print(f"  🔄 Baixando cotações individuais para {ticker}...")
        s_price_raw = fetch_price_series(ticker, START_DATE)

    if s_price_raw is not None and not s_price_raw.empty:
        s_price = s_price_raw.resample('ME').last().reindex(full_dates).ffill().bfill()
        if s_price.isna().all():
            print(f"⚠️ Aviso: Não há cotações válidas para {ticker}. Excluindo do cálculo.")
            continue
    else:
        print(f"⚠️ Aviso: Falha ao obter cotações para {ticker} via yfinance (lote e individual). Excluindo do cálculo.")
        continue

    valid_tickers.append(ticker)

    # 2. Busca de Shares Outstanding dinâmico (Série temporal histórica por data)
    s_shares_bi = fetch_shares_history(ticker, full_dates)

    # Pequena pausa preventiva contra rate limiting do yfinance
    time.sleep(0.15)

    # 3. Market Cap = Preço * Total Ações no Tempo (R$ Bi)
    mcap = s_price * s_shares_bi

    # 4. Enterprise Value (EV) = Market Cap + Dívida Líquida (R$ Bi)
    net_debt = df_netdebt_monthly[ticker]
    ev = mcap + net_debt

    # 5. EV/EBITDA Real com Proteção contra EBITDA <= 0 (marcado como NaN)
    ebitda_ltm = df_ebitda_monthly[ticker]
    ebitda_positive = ebitda_ltm.where(ebitda_ltm > 0)  # Filtra EBITDA negativo ou nulo
    ev_ebitda = ev / ebitda_positive
    df_ev_ebitda_companies[ticker] = ev_ebitda

    # 6. EBITDA Yield Implícito Individual (%) = (EBITDA LTM / EV) * 100
    ebitda_yield = (ebitda_positive / ev) * 100.0
    df_ebitda_yield_companies[ticker] = ebitda_yield

    # 7. Earnings Yield (1 / (P/L)) = Lucro Líquido LTM / Market Cap (com Proteção para Lucro <= 0)
    net_income_ltm = df_netincome_monthly[ticker]
    net_income_positive = net_income_ltm.where(net_income_ltm > 0)  # Filtra prejuízos
    earnings_yield = (net_income_positive / mcap) * 100.0
    df_earnings_yield_companies[ticker] = earnings_yield

# Validação crítica para evitar erro silencioso se todos os downloads falharem
if not valid_tickers:
    raise RuntimeError("❌ Falha crítica: Nenhum ticker teve cotações válidas baixadas via yfinance. Verifique a conexão de rede ou limites de requisição.")

# Seleciona empresas não-financeiras ex-commodities válidas
non_commodity_tickers = [t for t in valid_tickers if t not in COMMODITY_LEADERS]

if not non_commodity_tickers:
    raise RuntimeError("❌ Falha crítica: Nenhuma empresa ex-commodities foi validada para o cálculo dos múltiplos.")

# Mediana Real e Faixa Interquartil (P25 e P75) da Amostra Ex-Commodities (desconsiderando NaNs)
ev_ebitda_median_real = df_ev_ebitda_companies[non_commodity_tickers].median(axis=1, skipna=True)
ev_ebitda_p25_real = df_ev_ebitda_companies[non_commodity_tickers].quantile(0.25, axis=1, numeric_only=True)
ev_ebitda_p75_real = df_ev_ebitda_companies[non_commodity_tickers].quantile(0.75, axis=1, numeric_only=True)

# EBITDA Yield Implícito (%) Mediano da Amostra = Mediana de (EBITDA / EV) empresa a empresa
ebitda_yield_median = df_ebitda_yield_companies[non_commodity_tickers].median(axis=1, skipna=True)

# Earnings Yield Implícito (%) Mediano da Amostra = Mediana do Earnings Yield (Lucro / Market Cap)
earnings_yield_median = df_earnings_yield_companies[non_commodity_tickers].median(axis=1, skipna=True)

# ==========================================
# 7. DECOMPOSIÇÃO SETORIAL & DIFUSÃO DA TESE (SÉRIE TEMPORAL MENSAL)
# ==========================================
df_ebitda_sectors = pd.DataFrame(index=full_dates)
sector_growth_dict = {}

for sector_name, sector_tickers in SECTORS.items():
    sec_valid = [t for t in sector_tickers if t in df_ebitda_monthly.columns]
    if sec_valid:
        # Soma simples do EBITDA do setor (R$ Bi)
        sector_ebitda_sum = df_ebitda_monthly[sec_valid].sum(axis=1)
        # Normalização em Base 100 (Jan/2021)
        df_ebitda_sectors[sector_name] = (sector_ebitda_sum / sector_ebitda_sum.iloc[0]) * 100.0
        
        # Cálculo dinâmico da variação percentual acumulada
        pct_return = ((sector_ebitda_sum.iloc[-1] / sector_ebitda_sum.iloc[0]) - 1.0) * 100.0
        sector_growth_dict[sector_name] = pct_return

# Normalização Individual em Base 100 para Agregação
df_ebitda_norm_all = pd.DataFrame(index=full_dates)
for col in valid_tickers:
    df_ebitda_norm_all[col] = (df_ebitda_monthly[col] / df_ebitda_monthly[col].iloc[0]) * 100.0

ebitda_total_index = df_ebitda_norm_all[valid_tickers].median(axis=1).rolling(3, min_periods=1).mean()
ebitda_ex_commodities_index = df_ebitda_norm_all[non_commodity_tickers].median(axis=1).rolling(3, min_periods=1).mean()
ibov_index = (ibov_monthly / ibov_monthly.iloc[0]) * 100.0

# Serie Temporal Mensal da Taxa de Difusão: % de empresas ex-commodities com EBITDA maior que Jan/2021 em cada mês
ebitda_jan2021 = df_ebitda_monthly[non_commodity_tickers].iloc[0]
diffusion_matrix = df_ebitda_monthly[non_commodity_tickers].gt(ebitda_jan2021, axis=1)
diffusion_series = (diffusion_matrix.sum(axis=1) / len(non_commodity_tickers)) * 100.0

latest_diffusion = diffusion_series.iloc[-1]
print(f"✅ Análise concluída: Difusão da tese atual em {latest_diffusion:.0f}% das empresas ex-commodities.")

# ==========================================
# 8. ESTRUTURA DO DASHBOARD (PAINEL TRIPLE MODERN DARK)
# ==========================================
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Segoe UI', 'Roboto', 'Helvetica', 'Arial', 'DejaVu Sans']

BG_COLOR = '#0F172A'          # Dark Slate background
PANEL_COLOR = '#1E293B'       # Card Container background
COLOR_EBITDA_TOTAL = '#10B981' # Emerald Green
COLOR_EBITDA_EX = '#06B6D4'    # Cyan / Teal
COLOR_IBOV = '#F43F5E'         # Rose Red
COLOR_MULTIPLE = '#F59E0B'     # Amber Gold
COLOR_NTNB = '#A855F7'         # Purple Accent
COLOR_EARNINGS_YIELD = '#10B981' # Emerald / Green Yield

fig, (ax1, ax2, ax3) = plt.subplots(
    nrows=3, ncols=1,
    figsize=(13.0, 12.0),
    sharex=True,
    gridspec_kw={'height_ratios': [2.0, 1.2, 1.2]},
    facecolor=BG_COLOR
)

for ax in [ax1, ax2, ax3]:
    ax.set_facecolor(BG_COLOR)

# ------------------------------------------
# PAINEL A (SUPERIOR): EBITDA LTM vs. IBOVESPA & DECOMPOSIÇÃO
# ------------------------------------------
ax1.plot(full_dates, ebitda_total_index, label='EBITDA LTM Consolidado (Total Sample)', color=COLOR_EBITDA_TOTAL, linewidth=2.2, alpha=0.8)
ax1.plot(full_dates, ebitda_ex_commodities_index, label='EBITDA LTM Consolidado (Ex-PETR4 & VALE3)', color=COLOR_EBITDA_EX, linewidth=3.0, zorder=5)
ax1.plot(full_dates, ibov_index, label='Ibovespa (Preço)', color=COLOR_IBOV, linewidth=2.2, linestyle='--', alpha=0.9, zorder=4)

# Plotagem das curvas setoriais individuais (df_ebitda_sectors)
SECTOR_STYLES = {
    "Utilidades Públicas": {'color': '#38BDF8', 'linestyle': ':'},
    "Bens de Capital & Transp.": {'color': '#F59E0B', 'linestyle': ':'},
    "Consumo, Varejo & Saúde": {'color': '#EC4899', 'linestyle': ':'},
    "Materiais/Aliment. Ex-Líderes": {'color': '#A855F7', 'linestyle': ':'}
}

for sec_name, s_sec in df_ebitda_sectors.items():
    style = SECTOR_STYLES.get(sec_name, {'color': '#94A3B8', 'linestyle': ':'})
    ax1.plot(full_dates, s_sec, label=f'Setor: {sec_name}', color=style['color'], linewidth=1.2, linestyle=style['linestyle'], alpha=0.55, zorder=3)

# Sombreado "Bico de Pato"
ax1.fill_between(
    full_dates, ebitda_ex_commodities_index, ibov_index,
    color=COLOR_EBITDA_EX, alpha=0.14, label='Desconexão Operacional ("Bico de Pato")', zorder=2
)

# Título Principal do Dashboard
fig.suptitle(
    'B3: Desconexão Operacional, EV/EBITDA Real & Custo de Capital (NTN-B)',
    x=0.07, y=0.97, ha='left', fontsize=16, fontweight='bold', color='#F8FAFC'
)
ax1.set_title(
    'Painel A: Evolução Acumulada da Geração de Caixa (Base 100 = Jan/2021) vs. Ibovespa',
    fontsize=10.5, color='#94A3B8', pad=10, loc='left'
)

ax1.grid(True, linestyle='--', linewidth=0.7, color='#334155', alpha=0.6)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.spines['left'].set_visible(False)
ax1.spines['bottom'].set_color('#334155')
ax1.tick_params(axis='y', colors='#94A3B8', labelsize=9.5)
ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"{int(x)}"))
ax1.set_ylabel('Índice (Base 100)', color='#94A3B8', fontsize=10)

leg1 = ax1.legend(frameon=True, facecolor=PANEL_COLOR, edgecolor='#334155', fontsize=8.5, loc='upper left', labelcolor='#E2E8F0')
leg1.get_frame().set_linewidth(0.8)

# Card Informativo Dinâmico de Decomposição Setorial & Difusão Mensal
sector_text_lines = ["Decomposição Setorial (EBITDA Ex-Commodities):"]
for sec_name, pct_val in sector_growth_dict.items():
    sign = "+" if pct_val >= 0 else ""
    sector_text_lines.append(f"• {sec_name}: {sign}{pct_val:.1f}%")
sector_text_lines.append(f"• Difusão Atual: {latest_diffusion:.0f}% das empresas expandiram caixa")

sector_text = "\n".join(sector_text_lines)

ax1.text(
    0.985, 0.94, sector_text, transform=ax1.transAxes,
    fontsize=8.5, color='#F8FAFC', va='top', ha='right',
    bbox=dict(boxstyle='round,pad=0.5', facecolor=PANEL_COLOR, edgecolor='#334155', linewidth=0.8, alpha=0.95)
)

# ------------------------------------------
# PAINEL B (INTERMEDIÁRIO): EV/EBITDA REAL EMPRESA A EMPRESA
# ------------------------------------------
ax2.plot(full_dates, ev_ebitda_median_real, label='EV/EBITDA Mediano Real (Ex-Commodities)', color=COLOR_MULTIPLE, linewidth=2.6, zorder=4)
ax2.fill_between(full_dates, ev_ebitda_p25_real, ev_ebitda_p75_real, color=COLOR_MULTIPLE, alpha=0.15, label='Faixa Interquartil (P25 - P75)', zorder=2)

avg_mult = ev_ebitda_median_real.mean()
ax2.axhline(avg_mult, color='#64748B', linestyle=':', linewidth=1.4, label=f'Média do Período ({avg_mult:.1f}x)', zorder=3)

start_m = ev_ebitda_median_real.iloc[0]
end_m = ev_ebitda_median_real.iloc[-1]
last_date = full_dates[-1]

ax2.scatter([last_date], [end_m], color=COLOR_MULTIPLE, s=45, zorder=5)

ax2.set_title(
    'Painel B: Múltiplo EV/EBITDA Real Mediano (Market Cap + Dívida Líquida / EBITDA LTM)',
    fontsize=10.5, color='#F8FAFC', pad=8, loc='left', fontweight='bold'
)

ax2.grid(True, linestyle='--', linewidth=0.7, color='#334155', alpha=0.6)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.spines['left'].set_visible(False)
ax2.spines['bottom'].set_color('#334155')
ax2.tick_params(axis='y', colors='#94A3B8', labelsize=9.5)
ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"{x:.1f}x"))
ax2.set_ylabel('EV / EBITDA Real', color='#94A3B8', fontsize=10)

leg2 = ax2.legend(frameon=True, facecolor=PANEL_COLOR, edgecolor='#334155', fontsize=8.5, loc='upper right', labelcolor='#E2E8F0')
leg2.get_frame().set_linewidth(0.8)

# Anotação de Compressão
ax2.annotate(
    f'De {start_m:.1f}x → {end_m:.1f}x\n(Compressão Real)',
    xy=(last_date, end_m), xytext=(-100, 25), textcoords='offset points',
    arrowprops=dict(arrowstyle='->', color=COLOR_MULTIPLE, lw=1.1),
    fontsize=8.5, fontweight='bold', color='#F8FAFC',
    bbox=dict(boxstyle='round,pad=0.4', facecolor=PANEL_COLOR, edgecolor='#334155', linewidth=0.8)
)

# ------------------------------------------
# PAINEL C (INFERIOR): MACRO ARBITRAGEM (TAXA REAL NTN-B VS. EBITDA & EARNINGS YIELD)
# ------------------------------------------
# Eixo Esquerdo: Taxa Real NTN-B (%)
line_ntnb = ax3.plot(full_dates, s_ntnb_monthly, label='Taxa Real NTN-B 10 anos (IPCA+)', color=COLOR_NTNB, linewidth=2.5, zorder=4)
ax3.set_ylabel('NTN-B IPCA+ (% a.a.)', color=COLOR_NTNB, fontsize=9.5, fontweight='bold')
ax3.tick_params(axis='y', colors=COLOR_NTNB, labelsize=9.5)
ax3.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"{x:.1f}%"))

# Eixo Direito: EBITDA Yield Mediano (EBITDA / EV) e Earnings Yield (1 / P/L) da Bolsa (%)
ax3_twin = ax3.twinx()
line_ebitda_yield = ax3_twin.plot(full_dates, ebitda_yield_median, label='EBITDA Yield Implícito Mediano (EBITDA / EV)', color=COLOR_EBITDA_EX, linewidth=2.0, linestyle='-.', zorder=5)
line_earnings_yield = ax3_twin.plot(full_dates, earnings_yield_median, label='Earnings Yield Implícito Mediano — 1 / (P/L)', color=COLOR_EARNINGS_YIELD, linewidth=2.0, linestyle=':', zorder=6)

ax3_twin.set_ylabel('Yield Implícito (%)', color='#38BDF8', fontsize=9.5, fontweight='bold')
ax3_twin.tick_params(axis='y', colors='#38BDF8', labelsize=9.5)
ax3_twin.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"{x:.1f}%"))

ax3.set_title(
    'Painel C: Custo de Capital — Juros Reais de Longo Prazo vs. Yields da Bolsa (EBITDA & Earnings Yield)',
    fontsize=10.5, color='#F8FAFC', pad=8, loc='left', fontweight='bold'
)

ax3.grid(True, linestyle='--', linewidth=0.7, color='#334155', alpha=0.6)
ax3.spines['top'].set_visible(False)
ax3.spines['right'].set_visible(False)
ax3.spines['left'].set_visible(False)
ax3.spines['bottom'].set_color('#334155')
ax3_twin.spines['top'].set_visible(False)
ax3_twin.spines['right'].set_visible(False)
ax3_twin.spines['left'].set_visible(False)

# Legenda Combinada do Eixo Duplo
lines_comb = line_ntnb + line_ebitda_yield + line_earnings_yield
labels_comb = [l.get_label() for l in lines_comb]
leg3 = ax3.legend(lines_comb, labels_comb, frameon=True, facecolor=PANEL_COLOR, edgecolor='#334155', fontsize=8.2, loc='upper left', labelcolor='#E2E8F0')
leg3.get_frame().set_linewidth(0.8)

# Configuração Temporal Comum Eixo X
ax3.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b/%Y'))
ax3.tick_params(axis='x', colors='#94A3B8', labelsize=9.5, length=4, pad=6)

start_xlim = full_dates[0] - pd.Timedelta(days=15)
end_xlim = full_dates[-1] + pd.Timedelta(days=50)
ax3.set_xlim(start_xlim, end_xlim)

# Ajuste fino de layout
plt.subplots_adjust(top=0.92, bottom=0.06, left=0.07, right=0.92, hspace=0.25)

# Salvar e Exibir Imagem Final
output_filename = 'bico_de_pato_top25_b3.png'
plt.savefig(output_filename, dpi=300, facecolor=fig.get_facecolor(), bbox_inches='tight')
print(f"✅ Dashboard completo gerado com sucesso: {output_filename}")
try:
    plt.show()
except KeyboardInterrupt:
    print("ℹ️ Janela do gráfico encerrada.")
finally:
    plt.close('all')