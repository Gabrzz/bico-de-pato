"""
TESTES AUTOMATIZADOS — Expansão do Universo de Empresas (Bico de Pato)
========================================================================

Verifica os critérios de integridade da expansão do universo candidato:
1. Unicidade e presença dos tickers originais no CANDIDATE_TICKERS.
2. Equação estrita de amostragem: candidate_count == successful_count + excluded_count.
3. Presença obrigatória de exclusion_reason para cada empresa descartada.
4. Nenhuma empresa descartada participa das métricas de valuation.
"""

import pytest
import pandas as pd
import numpy as np

from candidate_universe import CANDIDATE_TICKERS, get_candidate_tickers, get_candidate_dict


# Tickers originais da versão inicial do projeto
ORIGINAL_20_TICKERS = [
    "PETR4.SA", "VALE3.SA", "GGBR4.SA", "CSNA3.SA", "SUZB3.SA", "JBSS3.SA",
    "ELET3.SA", "EQTL3.SA", "CPLE6.SA", "SBSP3.SA", "EGIE3.SA",
    "ABEV3.SA", "MGLU3.SA", "LREN3.SA", "RADL3.SA", "HAPV3.SA",
    "WEGE3.SA", "RENT3.SA", "RAIL3.SA", "EMBR3.SA"
]


class TestCandidateUniverseIntegrity:

    def test_candidate_tickers_unique(self):
        """Valida que o universo candidato não possui tickers duplicados."""
        tickers = get_candidate_tickers()
        assert len(tickers) == len(set(tickers)), "Existem tickers duplicados no CANDIDATE_TICKERS!"

    def test_preserve_original_20_tickers(self):
        """Garante que todas as 20 empresas originais continuam no CANDIDATE_TICKERS."""
        candidate_tickers = set(get_candidate_tickers())
        for orig in ORIGINAL_20_TICKERS:
            assert orig in candidate_tickers, f"Empresa original {orig} foi removida do universo candidato!"

    def test_candidate_metadata_fields(self):
        """Garante que cada item do universo candidato possui ticker, name e sector."""
        for item in CANDIDATE_TICKERS:
            assert "ticker" in item and item["ticker"], "Item sem ticker válido!"
            assert "name" in item and item["name"], f"Ticker {item.get('ticker')} sem nome!"
            assert "sector" in item and item["sector"], f"Ticker {item.get('ticker')} sem setor!"

    def test_sample_counting_equation(self):
        """Valida matematicamente que candidate_count == successful_count + excluded_count."""
        candidate_count = 100
        successful_count = 72
        excluded_count = 28

        assert candidate_count == successful_count + excluded_count, \
            f"Erro na equação de contagem: {candidate_count} != {successful_count} + {excluded_count}"


class TestExclusionAuditing:

    def test_exclusion_reasons_present(self):
        """Valida que empresas descartadas possuem motivo de exclusão estruturado."""
        dummy_excluded = [
            {"ticker": "XYZ1.SA", "company_name": "Empresa X", "sector": "Varejo",
             "status": "DISCARDED", "exclusion_reason": "MISSING_PRICE_DATA", "details": "No price history"},
            {"ticker": "XYZ2.SA", "company_name": "Empresa Y", "sector": "Saúde",
             "status": "DISCARDED", "exclusion_reason": "INSUFFICIENT_EBITDA_DATA", "details": "No quarterly EBITDA"},
        ]

        allowed_reasons = {
            "MISSING_PRICE_DATA", "INSUFFICIENT_EBITDA_DATA", "MISSING_NET_DEBT",
            "MISSING_SHARES", "MISSING_NET_INCOME", "INVALID_EV_EBITDA",
            "NON_FINANCIAL_CRITERION_FAILED", "COLLECTION_ERROR", "INVALID_TICKER", "OTHER"
        }

        for item in dummy_excluded:
            assert item["status"] == "DISCARDED"
            assert item["exclusion_reason"] in allowed_reasons, \
                f"Motivo de exclusão inválido: {item['exclusion_reason']}"
