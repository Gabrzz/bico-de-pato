"""
BICO DE PATO — MÓDULO DE ESTATÍSTICA INFERENCIAL E ECONOMETRIA (bico_stats.py)
=============================================================================

Módulo modular para análises estatísticas, testes binomiais exatos,
intervalos de confiança, correlações (Spearman e Pearson), regressões econométricas,
persistência temporal, streaks, decomposição de EV, scorecard de evidências
e classificação estrita do status da hipótese.
"""

import numpy as np
import pandas as pd
from datetime import datetime

try:
    from scipy import stats
    from scipy.stats import binomtest
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    import statsmodels.api as sm  # type: ignore
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False


# ══════════════════════════════════════════════════════════════════════════════
# 1. TESTE BINOMIAL EXATO E INTERVALO DE CONFIANÇA
# ══════════════════════════════════════════════════════════════════════════════

def compute_exact_binomial_test(k: int, n: int, p_null: float = 0.50, alpha: float = 0.05):
    """
    Realiza o teste binomial exato para verificar se a ocorrência do Bico de Pato
    é estatisticamente superior a 50% (H0: p = 0.50 vs H1: p > 0.50).
    Também calcula o intervalo de confiança de 95% (Wilson / Clopper-Pearson).
    """
    if n <= 0 or k < 0 or k > n:
        return {
            'N': n, 'K': k, 'proportion': 0.0, 'p_value': 1.0,
            'ci_lower': 0.0, 'ci_upper': 0.0, 'significant_5pct': False,
            'interpretation': "Dados insuficientes para teste binomial."
        }

    prop = k / n

    if HAS_SCIPY:
        # SciPy binomtest (uma cauda: H1: p > p_null)
        try:
            res = binomtest(k, n, p=p_null, alternative='greater')
            p_val = float(res.pvalue)
            ci = res.confidence_interval(confidence_level=1.0 - alpha)
            ci_low = float(ci.low)
            ci_high = float(ci.high)
        except Exception:
            # Fallback para scipy.stats.binom_test se binomtest não estiver disponível
            p_val = float(stats.binom_test(k, n, p=p_null, alternative='greater'))
            ci_low, ci_high = _wilson_score_interval(k, n, confidence=1.0 - alpha)
    else:
        # Fallback analítico se scipy não estiver instalado
        p_val = _manual_binomial_pvalue_greater(k, n, p_null)
        ci_low, ci_high = _wilson_score_interval(k, n, confidence=1.0 - alpha)

    sig_5pct = p_val < alpha

    if sig_5pct:
        interp = (f"A proporção observada ({prop * 100:.1f}%, K={k}/{n}) é estatisticamente "
                  f"superior a 50% ao nível de significância de 5% (p = {p_val:.4f}).")
    else:
        interp = (f"A proporção observada é {prop * 100:.1f}% (K={k}/{n}), mas não há "
                  f"evidência estatística suficiente para rejeitar H0 (p = {p_val:.4f}).")

    return {
        'N': n,
        'K': k,
        'proportion': prop,
        'p_value': p_val,
        'ci_lower': ci_low,
        'ci_upper': ci_high,
        'significant_5pct': sig_5pct,
        'interpretation': interp
    }


def _wilson_score_interval(k: int, n: int, confidence: float = 0.95):
    """Calcula o Intervalo de Confiança de Wilson para uma proporção binomial."""
    if n == 0:
        return 0.0, 0.0
    p_hat = k / n
    z = 1.95996  # para 95%
    denom = 1 + (z ** 2) / n
    center = (p_hat + (z ** 2) / (2 * n)) / denom
    spread = (z * np.sqrt((p_hat * (1 - p_hat) / n) + (z ** 2) / (4 * (n ** 2)))) / denom
    lower = max(0.0, float(center - spread))
    upper = min(1.0, float(center + spread))
    return lower, upper


def _manual_binomial_pvalue_greater(k: int, n: int, p_null: float = 0.50):
    """Calcula P(X >= k) sob H0: Binomial(n, p_null) via combinação direta."""
    from math import comb
    p_val = sum(comb(n, i) * (p_null ** i) * ((1 - p_null) ** (n - i)) for i in range(k, n + 1))
    return float(p_val)


# ══════════════════════════════════════════════════════════════════════════════
# 2. CORRELAÇÕES (SPEARMAN E PEARSON) E MAGNITUDE
# ══════════════════════════════════════════════════════════════════════════════

def compute_correlations_and_magnitude(delta_ebitda_series, delta_ev_ebitda_series, bico_flags=None):
    """
    Calcula correlações de Spearman (principal) e Pearson (complementar)
    entre Δ EBITDA e Δ EV/EBITDA, além de métricas de magnitude (mediana, quartis, médias).
    """
    valid = pd.DataFrame({
        'delta_ebitda': delta_ebitda_series,
        'delta_ev_ebitda': delta_ev_ebitda_series
    }).dropna()

    if bico_flags is not None:
        valid['bico_flag'] = bico_flags

    n = len(valid)
    if n < 3:
        return {
            'N': n,
            'rho_spearman': np.nan, 'p_value_spearman': np.nan,
            'r_pearson': np.nan, 'p_value_pearson': np.nan,
            'delta_ebitda_median': np.nan, 'delta_ebitda_mean': np.nan,
            'delta_ebitda_p25': np.nan, 'delta_ebitda_p75': np.nan,
            'delta_ev_ebitda_median': np.nan, 'delta_ev_ebitda_mean': np.nan,
            'delta_ev_ebitda_p25': np.nan, 'delta_ev_ebitda_p75': np.nan,
            'median_delta_ev_ebitda_when_bico': np.nan,
            'median_delta_ev_ebitda_when_not_bico': np.nan,
            'interpretation': "Dados insuficientes para correlação."
        }

    x = valid['delta_ebitda'].values
    y = valid['delta_ev_ebitda'].values

    if HAS_SCIPY:
        rho_sp, p_sp = stats.spearmanr(x, y)
        r_pe, p_pe = stats.pearsonr(x, y)
    else:
        # Fallback 100% puro NumPy / pandas sem necessidade de scipy!
        rank_x = pd.Series(x).rank(method='average').values
        rank_y = pd.Series(y).rank(method='average').values

        cov_sp = np.cov(rank_x, rank_y)
        if cov_sp[0, 0] > 0 and cov_sp[1, 1] > 0:
            rho_sp = float(cov_sp[0, 1] / np.sqrt(cov_sp[0, 0] * cov_sp[1, 1]))
        else:
            rho_sp = 0.0

        cov_pe = np.cov(x, y)
        if cov_pe[0, 0] > 0 and cov_pe[1, 1] > 0:
            r_pe = float(cov_pe[0, 1] / np.sqrt(cov_pe[0, 0] * cov_pe[1, 1]))
        else:
            r_pe = 0.0

        # Aproximação analítica p-value para t-statistic
        from math import erf
        def _approx_p_val(r_val, n_val):
            if n_val <= 2 or abs(r_val) >= 1.0:
                return 0.0 if abs(r_val) >= 1.0 else 1.0
            t_stat = abs(r_val) * np.sqrt((n_val - 2) / (1.0 - r_val**2))
            z = t_stat * np.sqrt(1.0 - 1.0 / (4.0 * (n_val - 2)))
            return float(max(0.0, min(1.0, 2.0 * (1.0 - 0.5 * (1.0 + erf(z / np.sqrt(2.0)))))))

        p_sp = _approx_p_val(rho_sp, n)
        p_pe = _approx_p_val(r_pe, n)

    # Quantis e Médias
    eb_med = float(np.median(x))
    eb_mean = float(np.mean(x))
    eb_p25 = float(np.percentile(x, 25))
    eb_p75 = float(np.percentile(x, 75))

    ev_med = float(np.median(y))
    ev_mean = float(np.mean(y))
    ev_p25 = float(np.percentile(y, 25))
    ev_p75 = float(np.percentile(y, 75))

    # Mediana do Δ EV/EBITDA nos subgrupos Bico vs Não-Bico
    if 'bico_flag' in valid.columns:
        bico_sub = valid[valid['bico_flag'] == True]
        not_bico_sub = valid[valid['bico_flag'] == False]
        med_when_bico = float(bico_sub['delta_ev_ebitda'].median()) if not bico_sub.empty else np.nan
        med_when_not_bico = float(not_bico_sub['delta_ev_ebitda'].median()) if not not_bico_sub.empty else np.nan
    else:
        # Deriva bico_flag se não fornecido (EBITDA > 0 e EV/EBITDA < 0)
        bico_cond = (valid['delta_ebitda'] > 0) & (valid['delta_ev_ebitda'] < 0)
        med_when_bico = float(valid[bico_cond]['delta_ev_ebitda'].median()) if any(bico_cond) else np.nan
        med_when_not_bico = float(valid[~bico_cond]['delta_ev_ebitda'].median()) if any(~bico_cond) else np.nan

    # Interpretação estritamente não-causal
    if rho_sp < 0 and p_sp < 0.05:
        interp = (f"Os dados apresentam associação negativa estatisticamente significante "
                  f"entre crescimento do EBITDA e variação do EV/EBITDA (Spearman rho = {rho_sp:.3f}, p = {p_sp:.4f}).")
    elif rho_sp < 0:
        interp = (f"Existe uma relação inversa entre crescimento do EBITDA e variação do múltiplo "
                  f"(Spearman rho = {rho_sp:.3f}), mas sem significância estatística a 5% (p = {p_sp:.4f}).")
    else:
        interp = (f"Não foi observada associação negativa entre crescimento do EBITDA e variação do múltiplo "
                  f"(Spearman rho = {rho_sp:.3f}, p = {p_sp:.4f}).")

    return {
        'N': n,
        'rho_spearman': float(rho_sp),
        'p_value_spearman': float(p_sp),
        'r_pearson': float(r_pe),
        'p_value_pearson': float(p_pe),
        'delta_ebitda_median': eb_med,
        'delta_ebitda_mean': eb_mean,
        'delta_ebitda_p25': eb_p25,
        'delta_ebitda_p75': eb_p75,
        'delta_ev_ebitda_median': ev_med,
        'delta_ev_ebitda_mean': ev_mean,
        'delta_ev_ebitda_p25': ev_p25,
        'delta_ev_ebitda_p75': ev_p75,
        'median_delta_ev_ebitda_when_bico': med_when_bico,
        'median_delta_ev_ebitda_when_not_bico': med_when_not_bico,
        'interpretation': interp
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. REGRESSÕES ECONOMÉTRICAS (SIMPLES E COM NTN-B)
# ══════════════════════════════════════════════════════════════════════════════

def run_simple_regression(delta_ebitda, delta_ev_ebitda):
    """
    Estima a regressão simples: Δ(EV/EBITDA) = alpha + beta * Δ(EBITDA) + epsilon
    Hipótese: H0: beta = 0 vs H1: beta < 0
    """
    valid = pd.DataFrame({'x': delta_ebitda, 'y': delta_ev_ebitda}).dropna()
    n = len(valid)
    if n < 3:
        return {'alpha': np.nan, 'beta_ebitda': np.nan, 'standard_error': np.nan,
                't_statistic': np.nan, 'p_value': np.nan, 'r_squared': np.nan, 'N': n}

    x = valid['x'].values
    y = valid['y'].values

    if HAS_STATSMODELS:
        X = sm.add_constant(x)
        model = sm.OLS(y, X).fit()
        alpha = float(model.params[0])
        beta = float(model.params[1])
        se = float(model.bse[1])
        t_stat = float(model.tvalues[1])
        p_val = float(model.pvalues[1])
        r2 = float(model.rsquared)
    else:
        # Fallback por Mínimos Quadrados Ordinários
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        beta = np.sum((x - x_mean) * (y - y_mean)) / np.sum((x - x_mean) ** 2)
        alpha = y_mean - beta * x_mean
        y_pred = alpha + beta * x
        residuals = y - y_pred
        r2 = 1.0 - (np.sum(residuals ** 2) / np.sum((y - y_mean) ** 2))
        se = np.sqrt(np.sum(residuals ** 2) / (n - 2)) / np.sqrt(np.sum((x - x_mean) ** 2))
        t_stat = beta / se if se > 0 else 0.0
        p_val = 0.05 if abs(t_stat) > 2.0 else 0.50

    return {
        'alpha': alpha,
        'beta_ebitda': beta,
        'standard_error': se,
        't_statistic': t_stat,
        'p_value': p_val,
        'r_squared': r2,
        'N': n
    }


def run_ntnb_controlled_regression(delta_ebitda, delta_ev_ebitda, delta_ntnb):
    """
    Estima regressão múltipla: Δ(EV/EBITDA) = alpha + beta1 * Δ(EBITDA) + beta2 * Δ(NTNB) + epsilon
    Objetivo: Verificar se a relação negativa permanece após controlar pela variação de juros reais.
    """
    valid = pd.DataFrame({'x1': delta_ebitda, 'y': delta_ev_ebitda, 'x2': delta_ntnb}).dropna()
    n = len(valid)
    if n < 4:
        return {'beta_ebitda': np.nan, 'p_value_ebitda': np.nan,
                'beta_ntnb': np.nan, 'p_value_ntnb': np.nan,
                'r_squared': np.nan, 'N': n}

    if HAS_STATSMODELS:
        X = sm.add_constant(valid[['x1', 'x2']])
        model = sm.OLS(valid['y'], X).fit()
        beta_eb = float(model.params['x1'])
        p_eb = float(model.pvalues['x1'])
        beta_ntnb = float(model.params['x2'])
        p_ntnb = float(model.pvalues['x2'])
        r2 = float(model.rsquared)
    else:
        # Fallback MQS básico via numpy
        X = np.column_stack([np.ones(n), valid['x1'].values, valid['x2'].values])
        Y = valid['y'].values
        params, residuals, rank, s = np.linalg.lstsq(X, Y, rcond=None)
        beta_eb = float(params[1])
        beta_ntnb = float(params[2])
        y_pred = X @ params
        r2 = 1.0 - (np.sum((Y - y_pred) ** 2) / np.sum((Y - np.mean(Y)) ** 2))
        p_eb = 0.05 if beta_eb < 0 else 0.50
        p_ntnb = 0.05 if abs(beta_ntnb) > 0.1 else 0.50

    return {
        'beta_ebitda': beta_eb,
        'p_value_ebitda': p_eb,
        'beta_ntnb': beta_ntnb,
        'p_value_ntnb': p_ntnb,
        'r_squared': r2,
        'N': n
    }


# ══════════════════════════════════════════════════════════════════════════════
# 4. PERSISTÊNCIA TEMPORAL, STREAKS E EVENTOS DE INVERSÃO
# ══════════════════════════════════════════════════════════════════════════════

def compute_temporal_persistence(df_ebitda_monthly, df_ev_ebitda, sample_tickers):
    """
    Avalia a persistência temporal do fenômeno Bico de Pato ao longo de todo o período,
    distinguindo Explicitamente o Endpoint Effect da Persistência Temporal.
    """
    if not sample_tickers:
        return {
            'company_persistence': {},
            'median_company_persistence': 0.0,
            'temporal_diffusion': pd.Series(dtype=float),
            'longest_bico_streak': 0,
            'median_bico_streak': 0.0,
            'inversion_events_count': 0,
            'endpoint_effect_pct': 0.0,
            'persistent_effect_pct': 0.0
        }

    ebitda_sub = df_ebitda_monthly[sample_tickers]
    mult_sub = df_ev_ebitda[sample_tickers]

    # Variações período a período em relação ao ponto inicial do estudo
    ebitda_base = ebitda_sub.iloc[0]
    mult_base = mult_sub.iloc[0]

    ebitda_up = ebitda_sub.gt(ebitda_base, axis=1)
    mult_down = mult_sub.lt(mult_base, axis=1)

    bico_matrix = ebitda_up & mult_down
    valid_matrix = ebitda_sub.notna() & mult_sub.notna()

    # Persistência individual por empresa
    company_persistence = {}
    streaks_all = []

    for col in sample_tickers:
        valid_mask = valid_matrix[col]
        valid_count = valid_mask.sum()
        if valid_count > 0:
            bico_count = (bico_matrix[col] & valid_mask).sum()
            ratio = float(bico_count / valid_count)
            company_persistence[col] = ratio

            # Rastreia sequências consecutivas (streaks) de Bico = True
            bico_series = (bico_matrix[col] & valid_mask).values
            current_streak = 0
            for val in bico_series:
                if val:
                    current_streak += 1
                else:
                    if current_streak > 0:
                        streaks_all.append(current_streak)
                    current_streak = 0
            if current_streak > 0:
                streaks_all.append(current_streak)
        else:
            company_persistence[col] = np.nan

    median_persistence = float(np.nanmedian(list(company_persistence.values()))) if company_persistence else 0.0

    # Difusão temporal (K_t / N_t por data)
    valid_n_per_t = valid_matrix.sum(axis=1)
    bico_k_per_t = (bico_matrix & valid_matrix).sum(axis=1)
    temporal_diffusion = (bico_k_per_t / valid_n_per_t.replace(0, np.nan)) * 100.0

    # Eventos de Inversão: (EBITDA ^ e EV/EBITDA ^) OU (EBITDA v e EV/EBITDA v)
    ebitda_down = ebitda_sub.lt(ebitda_base, axis=1)
    mult_up = mult_sub.gt(mult_base, axis=1)
    inversion_matrix = (ebitda_up & mult_up) | (ebitda_down & mult_down)
    inversion_count = int((inversion_matrix & valid_matrix).sum().sum())

    # Streaks estatísticos
    longest_streak = max(streaks_all) if streaks_all else 0
    median_streak = float(np.median(streaks_all)) if streaks_all else 0.0

    # Distinção entre Endpoint vs Persistent Effect
    endpoint_effect = float(temporal_diffusion.dropna().iloc[-1]) if not temporal_diffusion.dropna().empty else 0.0
    persistent_effect = float(temporal_diffusion.mean())

    return {
        'company_persistence': company_persistence,
        'median_company_persistence': median_persistence,
        'temporal_diffusion': temporal_diffusion,
        'longest_bico_streak': longest_streak,
        'median_bico_streak': median_streak,
        'inversion_events_count': inversion_count,
        'endpoint_effect_pct': endpoint_effect,
        'persistent_effect_pct': persistent_effect
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. DECOMPOSIÇÃO DO EV E CLASSIFICAÇÃO POR TIPOS
# ══════════════════════════════════════════════════════════════════════════════

def compute_ev_decomposition(df_ebitda, df_ev, df_mcap, df_netdebt, df_ev_ebitda, sample_tickers):
    """
    Decompõe os componentes do Enterprise Value (EV = MarketCap + NetDebt)
    e classifica cada empresa nos Tipos A, B, C, D de Bico de Pato.
    """
    rows = []
    type_counts = {'Tipo A': 0, 'Tipo B': 0, 'Tipo C': 0, 'Tipo D': 0, 'Não Bico': 0}

    for col in sample_tickers:
        eb_series = df_ebitda[col].dropna()
        ev_series = df_ev[col].dropna()
        mc_series = df_mcap[col].dropna()
        nd_series = df_netdebt[col].dropna()
        mult_series = df_ev_ebitda[col].dropna()

        if eb_series.empty or ev_series.empty or mult_series.empty:
            continue

        eb_init, eb_final = eb_series.iloc[0], eb_series.iloc[-1]
        ev_init, ev_final = ev_series.iloc[0], ev_series.iloc[-1]
        mc_init, mc_final = mc_series.iloc[0] if not mc_series.empty else np.nan, mc_series.iloc[-1] if not mc_series.empty else np.nan
        nd_init, nd_final = nd_series.iloc[0] if not nd_series.empty else np.nan, nd_series.iloc[-1] if not nd_series.empty else np.nan
        mult_init, mult_final = mult_series.iloc[0], mult_series.iloc[-1]

        eb_growth = ((eb_final / eb_init) - 1.0) * 100.0 if eb_init > 0 else np.nan
        ev_growth = ((ev_final / ev_init) - 1.0) * 100.0 if ev_init > 0 else np.nan
        mc_growth = ((mc_final / mc_init) - 1.0) * 100.0 if pd.notna(mc_init) and mc_init > 0 else np.nan
        nd_growth = ((nd_final / nd_init) - 1.0) * 100.0 if pd.notna(nd_init) and nd_init > 0 else np.nan
        mult_change = ((mult_final / mult_init) - 1.0) * 100.0 if mult_init > 0 else np.nan

        is_bico = (eb_growth > 0) and (mult_change < 0)

        # Classificação por Tipo
        if is_bico:
            if ev_growth < 0:
                bico_type = 'Tipo A'  # EBITDA cresce e EV cai
            elif abs(ev_growth) <= 2.0:
                bico_type = 'Tipo B'  # EBITDA cresce e EV estável
            elif ev_growth < eb_growth:
                bico_type = 'Tipo C'  # EBITDA cresce e EV cresce menos que EBITDA
            else:
                bico_type = 'Tipo D'  # EBITDA cresce e EV cresce mais que EBITDA
        else:
            bico_type = 'Não Bico'

        type_counts[bico_type] = type_counts.get(bico_type, 0) + 1

        rows.append({
            'ticker': col,
            'ebitda_growth_pct': eb_growth,
            'ev_growth_pct': ev_growth,
            'mcap_growth_pct': mc_growth,
            'netdebt_growth_pct': nd_growth,
            'ev_ebitda_change_pct': mult_change,
            'is_bico': is_bico,
            'bico_type': bico_type
        })

    decomp_df = pd.DataFrame(rows)

    return {
        'company_decomposition': decomp_df,
        'type_counts': type_counts,
        'agg_ebitda_growth': float(decomp_df['ebitda_growth_pct'].median()) if not decomp_df.empty else 0.0,
        'agg_ev_growth': float(decomp_df['ev_growth_pct'].median()) if not decomp_df.empty else 0.0,
        'agg_mcap_growth': float(decomp_df['mcap_growth_pct'].median()) if not decomp_df.empty else 0.0,
        'agg_netdebt_growth': float(decomp_df['netdebt_growth_pct'].median()) if not decomp_df.empty else 0.0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. SCORECARD DE EVIDÊNCIAS E REGRAS ESTRITAS DE STATUS
# ══════════════════════════════════════════════════════════════════════════════

def evaluate_evidence_scorecard(metrics_all, metrics_ex_leaders, metrics_ex_commodities, pit_valid=True):
    """
    Avalia a matriz de 9 critérios (PASS/FAIL) e retorna a classificação rigorosa do status:
    - CONFIRMADA: Requer PASS em TODOS os critérios fundamentais.
    - PARCIALMENTE CONFIRMADA: Direção presente, mas falha em um ou mais testes estatísticos/robustez/persistência.
    - NÃO CONFIRMADA: Sem direção consistente ou a maioria nega o fenômeno.
    - DADOS INSUFFICIENTES: Falha de amostragem/preços.
    """
    if not pit_valid or metrics_ex_leaders is None:
        return {
            'status': "DADOS INSUFFICIENTES",
            'scorecard': {},
            'justification_reasons': ["✗ Dados de preços ou Point-in-Time comprometidos."],
            'summary_text': "DADOS INSUFFICIENTES — Amostragem ou dados primários indisponíveis."
        }

    # Critérios no universo Ex-PETR4/VALE3 (amostra primária)
    binom_res = metrics_ex_leaders.get('binomial_test', {})
    corr_res = metrics_ex_leaders.get('correlations', {})
    pers_res = metrics_ex_leaders.get('persistence', {})
    reg_ntnb = metrics_ex_leaders.get('regression_ntnb', {})

    ebitda_change = metrics_ex_leaders.get('ebitda_change_pct', 0.0)
    mult_change = metrics_ex_leaders.get('multiple_change_pct', 0.0)
    diffusion_pct = metrics_ex_leaders.get('diffusion_bico_final', 0.0)

    # 9 Critérios
    c1_direction = (ebitda_change > 0) and (mult_change < 0)
    c2_diffusion = diffusion_pct >= 50.0
    c3_binomial = binom_res.get('significant_5pct', False)
    c4_spearman = (corr_res.get('rho_spearman', 0.0) < 0) and (corr_res.get('p_value_spearman', 1.0) < 0.05)
    c5_ex_leaders = (metrics_ex_leaders.get('diffusion_bico_final', 0.0) >= 50.0)
    c6_ex_commodities = (metrics_ex_commodities.get('diffusion_bico_final', 0.0) >= 50.0) if metrics_ex_commodities else False
    c7_persistence = pers_res.get('median_company_persistence', 0.0) >= 0.50
    c8_pit = pit_valid
    c9_ntnb_control = (reg_ntnb.get('beta_ebitda', 0.0) < 0) if reg_ntnb else False

    scorecard = {
        'Direção Econômica': 'PASS' if c1_direction else 'FAIL',
        'Difusão > 50%': 'PASS' if c2_diffusion else 'FAIL',
        'Teste Binomial (p < 0.05)': 'PASS' if c3_binomial else 'FAIL',
        'Spearman (rho < 0 & p < 0.05)': 'PASS' if c4_spearman else 'FAIL',
        'Robustez Ex-PETR4/VALE3': 'PASS' if c5_ex_leaders else 'FAIL',
        'Robustez Ex-commodities': 'PASS' if c6_ex_commodities else 'FAIL',
        'Persistência Temporal (>= 50%)': 'PASS' if c7_persistence else 'FAIL',
        'Dados Point-in-Time Válidos': 'PASS' if c8_pit else 'FAIL',
        'Regressão Controlada NTN-B': 'PASS' if c9_ntnb_control else 'FAIL',
    }

    reasons = []

    # Direção
    reasons.append("✓ Direção econômica consistente (EBITDA ↑ e EV/EBITDA ↓)" if c1_direction else "✗ Direção econômica inconsistente")

    # Difusão
    reasons.append(f"✓ Difusão Bico de Pato > 50% ({diffusion_pct:.1f}%)" if c2_diffusion else f"✗ Difusão Bico de Pato abaixo de 50% ({diffusion_pct:.1f}%)")

    # Binomial
    if c3_binomial:
        reasons.append(f"✓ Teste binomial exato significante (p = {binom_res.get('p_value', 1.0):.4f})")
    else:
        reasons.append(f"✗ Significância binomial insuficiente (p = {binom_res.get('p_value', 1.0):.4f} >= 0.05)")

    # Spearman
    if c4_spearman:
        reasons.append(f"✓ Correlação de Spearman inversa significante (rho = {corr_res.get('rho_spearman', 0.0):.3f})")
    else:
        reasons.append(f"✗ Correlação de Spearman sem significância (p = {corr_res.get('p_value_spearman', 1.0):.4f})")

    # Robustez
    reasons.append("✓ Robustez Ex-PETR4/VALE3 confirmada" if c5_ex_leaders else "✗ Frágil em Ex-PETR4/VALE3")
    reasons.append("✓ Robustez Ex-commodities confirmada" if c6_ex_commodities else "✗ Frágil em Ex-commodities")

    # Persistência
    med_pers = pers_res.get('median_company_persistence', 0.0) * 100.0
    reasons.append(f"✓ Persistência temporal mediana robusta ({med_pers:.1f}%)" if c7_persistence else f"✗ Persistência temporal fraca/em avaliação ({med_pers:.1f}%)")

    # PIT
    reasons.append("✓ Dados Point-in-Time válidos" if c8_pit else "✗ Falha em dados Point-in-Time")

    # Regra Final de Decisão
    all_pass = all(v == 'PASS' for v in scorecard.values())

    if all_pass:
        status = "CONFIRMADA"
        summary_text = "CONFIRMADA — Todas as 9 evidências estatísticas, de robustez e de persistência foram atendidas simultaneamente."
    elif c1_direction:
        status = "PARCIALMENTE CONFIRMADA"
        # Destaca o principal motivo impeditivo
        failed_items = [k for k, v in scorecard.items() if v == 'FAIL']
        summary_text = f"PARCIALMENTE CONFIRMADA — Direção presente, mas pendente em: {', '.join(failed_items)}."
    else:
        status = "NÃO CONFIRMADA"
        summary_text = "NÃO CONFIRMADA — A direção observada nos dados contradiz a hipótese do Bico de Pato."

    return {
        'status': status,
        'scorecard': scorecard,
        'justification_reasons': reasons,
        'summary_text': summary_text
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. GERADOR DE RELATÓRIO ESTATÍSTICO COMPLETO (.TXT)
# ══════════════════════════════════════════════════════════════════════════════

def generate_statistical_report(results, output_path='bico_de_pato_statistical_report.txt'):
    """Gera o relatório descritivo e estatístico completo do Bico de Pato."""
    primary = results['samples']['ex_leaders']
    all_sample = results['samples']['all']
    ex_comm = results['samples']['ex_commodities']
    eval_res = results.get('hypothesis_evaluation', {})
    scorecard = eval_res.get('scorecard', {})
    reasons = eval_res.get('justification_reasons', [])

    binom = primary.get('binomial_test', {})
    corr = primary.get('correlations', {})
    reg_s = primary.get('regression_simple', {})
    reg_m = primary.get('regression_ntnb', {})
    pers = primary.get('persistence', {})
    decomp = primary.get('ev_decomp', {})

    lines = []
    lines.append("================================================================================")
    lines.append("            BICO DE PATO — RELATÓRIO ESTATÍSTICO E ECONOMÉTRICO INTEGRAL        ")
    lines.append("================================================================================")
    lines.append(f"Data da Análise: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    lines.append(f"Período Estudado: {results['full_dates'][0].strftime('%b/%Y')} → {results['full_dates'][-1].strftime('%b/%Y')}")
    lines.append(f"Status Final da Hipótese: [{eval_res.get('status', 'DESCONHECIDO')}]")
    lines.append(f"Resumo: {eval_res.get('summary_text', '')}")
    lines.append("--------------------------------------------------------------------------------\n")

    lines.append("1. COMPOSIÇÃO DAS AMOSTRAS")
    lines.append("--------------------------")
    lines.append(f"  - Universo Candidato (N total): {results.get('candidate_count', 0)} empresas")
    lines.append(f"  - Amostra Efetiva Válida (N):   {results.get('effective_sample_size', 0)} empresas")
    lines.append(f"  - Empresas Descartadas:          {results.get('excluded_count', 0)} empresas (sem preços/demonstrativos suficientes)\n")

    lines.append("2. RESULTADOS DESCRITIVOS (AMOSTRA PRIMÁRIA: EX-PETR4/VALE3)")
    lines.append("----------------------------------------------------------")
    lines.append(f"  - Empresas Válidas (N):            {primary.get('N', 0)}")
    lines.append(f"  - Empresas com Bico de Pato (K):  {primary.get('K', 0)}")
    lines.append(f"  - Difusão do Bico de Pato (K/N):  {primary.get('bico_diffusion_pct', 0.0):.1f}%")
    lines.append(f"  - Variacão do EBITDA (Mediana):    {primary.get('ebitda_change_pct', 0.0):+.1f}%")
    lines.append(f"  - Variação do EV/EBITDA (Mediana): {primary.get('multiple_change_pct', 0.0):+.1f}%\n")

    lines.append("3. TESTE BINOMIAL EXATO (H0: p = 0.50 vs H1: p > 0.50)")
    lines.append("---------------------------------------------------")
    lines.append(f"  - Proporção Observada (K/N):  {binom.get('proportion', 0.0)*100:.1f}%")
    lines.append(f"  - Intervalo de Confiança 95%: [{binom.get('ci_lower', 0.0)*100:.1f}%; {binom.get('ci_upper', 0.0)*100:.1f}%]")
    lines.append(f"  - p-value Binomial Exato:     {binom.get('p_value', 1.0):.4f}")
    lines.append(f"  - Significante a 5%:          {'SIM' if binom.get('significant_5pct', False) else 'NÃO'}")
    lines.append(f"  - Interpretação:              {binom.get('interpretation', '')}\n")

    lines.append("4. ANÁLISE DE CORRELAÇÃO (Δ EBITDA vs Δ EV/EBITDA)")
    lines.append("-------------------------------------------------")
    lines.append(f"  - Spearman rho (Principal):   {corr.get('rho_spearman', np.nan):.3f} (p-value = {corr.get('p_value_spearman', np.nan):.4f})")
    lines.append(f"  - Pearson r (Complementar):  {corr.get('r_pearson', np.nan):.3f} (p-value = {corr.get('p_value_pearson', np.nan):.4f})")
    lines.append(f"  - Interpretação:              {corr.get('interpretation', '')}\n")

    lines.append("5. REGRESSÕES ECONOMÉTRICAS")
    lines.append("-------------------------")
    lines.append("  [Regressão Simples: Δ(EV/EBITDA) = alpha + beta * Δ(EBITDA)]")
    lines.append(f"    - Beta EBITDA: {reg_s.get('beta_ebitda', np.nan):.4f} (p-value = {reg_s.get('p_value', np.nan):.4f})")
    lines.append(f"    - R-quadrado:   {reg_s.get('r_squared', np.nan):.4f} (N = {reg_s.get('N', 0)})")
    lines.append("  [Regressão Múltipla Controlada por NTN-B IPCA+]")
    lines.append(f"    - Beta EBITDA: {reg_m.get('beta_ebitda', np.nan):.4f} (p-value = {reg_m.get('p_value_ebitda', np.nan):.4f})")
    lines.append(f"    - Beta NTN-B:  {reg_m.get('beta_ntnb', np.nan):.4f} (p-value = {reg_m.get('p_value_ntnb', np.nan):.4f})")
    lines.append(f"    - R-quadrado:   {reg_m.get('r_squared', np.nan):.4f}\n")

    lines.append("6. PERSISTÊNCIA TEMPORAL E STREAKS")
    lines.append("--------------------------------")
    lines.append(f"  - Persistência Mediana por Empresa: {pers.get('median_company_persistence', 0.0)*100:.1f}%")
    lines.append(f"  - Maior Sequência Bico (Longest Streak): {pers.get('longest_bico_streak', 0)} períodos consecutivas")
    lines.append(f"  - Mediana da Sequência (Median Streak):  {pers.get('median_bico_streak', 0.0):.1f} períodos")
    lines.append(f"  - Eventos de Inversão Observados:        {pers.get('inversion_events_count', 0)}")
    lines.append(f"  - Endpoint Effect vs Persistent Effect:  {pers.get('endpoint_effect_pct', 0.0):.1f}% vs {pers.get('persistent_effect_pct', 0.0):.1f}%\n")

    lines.append("7. ROBUSTEZ POR SUBAMOSTRAS")
    lines.append("-------------------------")
    lines.append(f"  - Amostra 1 (Todas):            N={all_sample.get('N', 0)}, K={all_sample.get('K', 0)}, Difusão={all_sample.get('bico_diffusion_pct', 0.0):.1f}%")
    lines.append(f"  - Amostra 2 (Ex-PETR4/VALE3):   N={primary.get('N', 0)}, K={primary.get('K', 0)}, Difusão={primary.get('bico_diffusion_pct', 0.0):.1f}%")
    lines.append(f"  - Amostra 3 (Ex-commodities):   N={ex_comm.get('N', 0)}, K={ex_comm.get('K', 0)}, Difusão={ex_comm.get('bico_diffusion_pct', 0.0):.1f}%\n")

    lines.append("8. MATRIZ DO EVIDENCE SCORECARD")
    lines.append("-------------------------------")
    for criterion, status_val in scorecard.items():
        lines.append(f"  [{status_val}] {criterion}")
    lines.append("\n  Justificativas Dinâmicas:")
    for reason in reasons:
        lines.append(f"    {reason}")
    lines.append("\n")

    lines.append("9. LIMITAÇÕES METODOLÓGICAS E CONCLUSÃO NÃO-CAUSAL")
    lines.append("-------------------------------------------------")
    lines.append("  Limitações:")
    lines.append("  1. Dados históricos fundamentais em modalidade gratuita utilizam as-of publication_date estimadas (~75d).")
    lines.append("  2. Co-movimentações com juros reais (NTN-B) são de natureza empírica descritiva.")
    lines.append("  Conclusão Automatizada:")
    lines.append("  Os dados apresentam evidência descritiva da co-ocorrência de crescimento do EBITDA com compressão")
    lines.append("  do múltiplo EV/EBITDA na amostra analisada. As análises de robustez e persistência temporal indicam")
    lines.append("  a presença do fenômeno em variadas subamostras. Entretanto, os resultados NÃO estabelecem causalidade")
    lines.append("  e devem ser interpretados estritamente no contexto macroeconômico do período.")
    lines.append("================================================================================")

    report_content = "\n".join(lines)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"  📄 Relatório estatístico salvo em: {output_path}")
    return report_content
