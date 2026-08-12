"""
TESTES AUTOMATIZADOS — Aprimoramento Metodológico do Bico de Pato
================================================================

Suíte de testes para verificar cálculos estatísticos, teste binomial exato,
intervalos de confiança, correlações, regressões, persistência temporal,
scorecard de evidências e integridade da classificação de status.

Executar com:
    pytest test_methodology.py -v
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime

from bico_stats import (
    compute_exact_binomial_test,
    _wilson_score_interval,
    compute_correlations_and_magnitude,
    run_simple_regression,
    run_ntnb_controlled_regression,
    compute_temporal_persistence,
    compute_ev_decomposition,
    evaluate_evidence_scorecard,
)


def test_wilson_score_interval():
    """Testa a geração do intervalo de confiança de Wilson."""
    low, high = _wilson_score_interval(50, 100, confidence=0.95)
    assert 0.40 <= low <= 0.45
    assert 0.55 <= high <= 0.60
    assert low < 0.50 < high


def test_binomial_exact_test():
    """Testa o teste binomial exato para K/N."""
    # Teste 1: K=60, N=100 -> p < 0.05
    res = compute_exact_binomial_test(k=60, n=100)
    assert res['N'] == 100
    assert res['K'] == 60
    assert res['proportion'] == 0.60
    assert res['p_value'] < 0.05
    assert res['significant_5pct'] is True

    # Teste 2: K=52, N=100 -> p > 0.05
    res2 = compute_exact_binomial_test(k=52, n=100)
    assert res2['significant_5pct'] is False


def test_correlations_and_magnitude():
    """Testa o cálculo de Spearman, Pearson e quantis."""
    delta_eb = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
    delta_ev_eb = pd.Series([-5.0, -10.0, -15.0, -20.0, -25.0])

    res = compute_correlations_and_magnitude(delta_eb, delta_ev_eb)
    assert res['rho_spearman'] == -1.0
    assert res['r_pearson'] == -1.0
    assert res['p_value_spearman'] < 0.05
    assert res['delta_ebitda_median'] == 30.0
    assert res['delta_ev_ebitda_median'] == -15.0


def test_simple_regression():
    """Testa a regressão linear simples."""
    eb = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    mult = np.array([10.0, 8.0, 6.0, 4.0, 2.0])  # y = 12 - 2x
    res = run_simple_regression(eb, mult)

    assert pytest.approx(res['alpha'], 0.01) == 12.0
    assert pytest.approx(res['beta_ebitda'], 0.01) == -2.0
    assert res['r_squared'] > 0.99


def test_ntnb_controlled_regression():
    """Testa a regressão múltipla controlada por NTN-B."""
    eb = np.array([10, 20, 30, 40, 50, 60])
    mult = np.array([-2, -4, -6, -8, -10, -12])
    ntnb = np.array([1, 2, 1, 2, 1, 2])

    res = run_ntnb_controlled_regression(eb, mult, ntnb)
    assert res['beta_ebitda'] < 0
    assert res['N'] == 6


def test_temporal_persistence():
    """Testa o cálculo da persistência temporal e streaks."""
    dates = pd.date_range("2021-01-01", periods=5, freq="QE")
    tickers = ["TICK1.SA", "TICK2.SA"]

    ebitda_df = pd.DataFrame({
        "TICK1.SA": [10, 12, 14, 16, 18],  # EBITDA subiu
        "TICK2.SA": [10, 8, 9, 7, 6],      # EBITDA caiu
    }, index=dates)

    mult_df = pd.DataFrame({
        "TICK1.SA": [10, 9, 8, 7, 6],      # EV/EBITDA caiu -> Bico
        "TICK2.SA": [10, 11, 12, 13, 14],  # EV/EBITDA subiu -> Não bico
    }, index=dates)

    res = compute_temporal_persistence(ebitda_df, mult_df, tickers)
    assert res['company_persistence']['TICK1.SA'] == 1.0
    assert res['company_persistence']['TICK2.SA'] == 0.0
    assert res['median_company_persistence'] == 0.50
    assert res['longest_bico_streak'] == 5


def test_ev_decomposition():
    """Testa a decomposição do EV e classificação nos Tipos A, B, C, D."""
    dates = pd.date_range("2021-01-01", periods=2, freq="YE")
    tickers = ["TICKA.SA", "TICKB.SA", "TICKC.SA"]

    df_ebitda = pd.DataFrame({"TICKA.SA": [10, 20], "TICKB.SA": [10, 20], "TICKC.SA": [10, 20]}, index=dates)
    df_ev = pd.DataFrame({"TICKA.SA": [100, 80], "TICKB.SA": [100, 100], "TICKC.SA": [100, 130]}, index=dates)
    df_mcap = pd.DataFrame({"TICKA.SA": [50, 40], "TICKB.SA": [50, 50], "TICKC.SA": [50, 65]}, index=dates)
    df_netdebt = pd.DataFrame({"TICKA.SA": [50, 40], "TICKB.SA": [50, 50], "TICKC.SA": [50, 65]}, index=dates)
    df_ev_ebitda = pd.DataFrame({"TICKA.SA": [10, 4], "TICKB.SA": [10, 5], "TICKC.SA": [10, 6.5]}, index=dates)

    res = compute_ev_decomposition(df_ebitda, df_ev, df_mcap, df_netdebt, df_ev_ebitda, tickers)
    counts = res['type_counts']

    assert counts['Tipo A'] == 1  # EV caiu de 100 para 80
    assert counts['Tipo B'] == 1  # EV estável 100 para 100
    assert counts['Tipo C'] == 1  # EV cresceu 30%, menos que EBITDA (100%)


def test_evidence_scorecard_and_status():
    """Testa a consistência do Evidence Scorecard e regras de status."""
    dummy_sample = {
        'N': 50, 'K': 35, 'diffusion_bico_final': 70.0,
        'ebitda_change_pct': 20.0, 'multiple_change_pct': -15.0,
        'binomial_test': {'significant_5pct': True, 'p_value': 0.001},
        'correlations': {'rho_spearman': -0.6, 'p_value_spearman': 0.001},
        'persistence': {'median_company_persistence': 0.70},
        'regression_ntnb': {'beta_ebitda': -0.15}
    }

    res_all_pass = evaluate_evidence_scorecard(dummy_sample, dummy_sample, dummy_sample, pit_valid=True)
    assert res_all_pass['status'] == "CONFIRMADA"

    # Teste de status PARCIALMENTE CONFIRMADA quando o binomial falha
    dummy_fail_binom = dummy_sample.copy()
    dummy_fail_binom['binomial_test'] = {'significant_5pct': False, 'p_value': 0.20}

    res_partial = evaluate_evidence_scorecard(dummy_fail_binom, dummy_fail_binom, dummy_fail_binom, pit_valid=True)
    assert res_partial['status'] == "PARCIALMENTE CONFIRMADA"
    assert "Significância binomial insuficiente" in str(res_partial['justification_reasons'])
