"""
TESTES AUTOMATIZADOS — Point-in-Time / Look-Ahead Bias Correction
==================================================================

6 testes obrigatórios para garantir a integridade da correção de look-ahead bias.

Executar com:
    pytest test_point_in_time.py -v
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime

from point_in_time import (
    FundamentalRecord,
    FundamentalStore,
    check_lookahead,
    build_pit_monthly_series,
    compute_observation_lookahead_flag,
    populate_store_from_hardcoded,
)


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_store():
    """Cria um FundamentalStore com dados de teste realistas."""
    store = FundamentalStore()

    # EBITDA anual para PETR4.SA — dados publicados ~75 dias após period_end_date
    store.add_record(FundamentalRecord(
        ticker='PETR4.SA', metric='EBITDA', period='2022',
        period_end_date=datetime(2022, 12, 31),
        value=261.016,
        source='EBITDA_HARDCODED_BI 2022',
        publication_date=datetime(2023, 3, 16),  # ~75 dias depois
        data_source_type='HARDCODED',
        data_quality_flag='ESTIMATED_PUBLICATION_DATE',
    ))
    store.add_record(FundamentalRecord(
        ticker='PETR4.SA', metric='EBITDA', period='2023',
        period_end_date=datetime(2023, 12, 31),
        value=264.987,
        source='EBITDA_HARDCODED_BI 2023',
        publication_date=datetime(2024, 3, 15),  # ~75 dias depois
        data_source_type='HARDCODED',
        data_quality_flag='ESTIMATED_PUBLICATION_DATE',
    ))

    # Net Debt anual para PETR4.SA
    store.add_record(FundamentalRecord(
        ticker='PETR4.SA', metric='NET_DEBT', period='2022',
        period_end_date=datetime(2022, 12, 31),
        value=220.0,
        source='NET_DEBT_HARDCODED_BI 2022',
        publication_date=datetime(2023, 3, 16),
        data_source_type='HARDCODED',
        data_quality_flag='ESTIMATED_PUBLICATION_DATE',
    ))
    store.add_record(FundamentalRecord(
        ticker='PETR4.SA', metric='NET_DEBT', period='2023',
        period_end_date=datetime(2023, 12, 31),
        value=222.0,
        source='NET_DEBT_HARDCODED_BI 2023',
        publication_date=datetime(2024, 3, 15),
        data_source_type='HARDCODED',
        data_quality_flag='ESTIMATED_PUBLICATION_DATE',
    ))

    return store


@pytest.fixture
def store_with_quarterly():
    """Cria um store com dados trimestrais para testar EBITDA LTM."""
    store = FundamentalStore()

    # 4 trimestres de EBITDA para VALE3.SA
    quarters = [
        ('2023Q1', datetime(2023, 3, 31), 18.5, datetime(2023, 5, 30)),
        ('2023Q2', datetime(2023, 6, 30), 19.2, datetime(2023, 8, 29)),
        ('2023Q3', datetime(2023, 9, 30), 20.1, datetime(2023, 11, 28)),
        ('2023Q4', datetime(2023, 12, 31), 17.6, datetime(2024, 2, 28)),
    ]

    for period, ped, value, pub_date in quarters:
        store.add_record(FundamentalRecord(
            ticker='VALE3.SA', metric='EBITDA_QUARTERLY', period=period,
            period_end_date=ped,
            value=value,
            source=f'TEST_QUARTERLY {period}',
            publication_date=pub_date,
            data_source_type='YFINANCE',
            data_quality_flag='EXACT',
        ))

    return store


@pytest.fixture
def store_with_unknown():
    """Cria um store com dados sem publication_date."""
    store = FundamentalStore()

    store.add_record(FundamentalRecord(
        ticker='MGLU3.SA', metric='EBITDA', period='2023',
        period_end_date=datetime(2023, 12, 31),
        value=2.962,
        source='EBITDA_HARDCODED_BI 2023',
        publication_date=None,  # Desconhecida
        data_source_type='HARDCODED',
        data_quality_flag='UNKNOWN',
    ))

    return store


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 1: Dado publicado depois da observation_date NÃO pode ser utilizado
# ══════════════════════════════════════════════════════════════════════════════

class TestFutureDataExcluded:
    """Um dado publicado depois da observation_date NÃO pode ser utilizado."""

    def test_future_ebitda_excluded(self, sample_store):
        """EBITDA 2023 (publicado em 2024-03-15) NÃO pode ser usado em 2024-01-31."""
        observation_date = datetime(2024, 1, 31)
        available = sample_store.get_available_records('PETR4.SA', 'EBITDA', observation_date)

        # O dado de 2023 (pub 2024-03-15) NÃO deve aparecer
        periods = [r.period for r in available]
        assert '2023' not in periods, \
            "EBITDA 2023 (pub_date=2024-03-15) NÃO deveria estar disponível em 2024-01-31"

        # Mas o dado de 2022 (pub 2023-03-16) DEVE aparecer
        assert '2022' in periods, \
            "EBITDA 2022 (pub_date=2023-03-16) DEVERIA estar disponível em 2024-01-31"

    def test_future_net_debt_excluded(self, sample_store):
        """Net Debt 2023 (publicado em 2024-03-15) NÃO pode ser usado em 2024-02-28."""
        observation_date = datetime(2024, 2, 28)
        value, record = sample_store.get_net_debt_pit('PETR4.SA', observation_date)

        # Deve retornar o Net Debt de 2022, não o de 2023
        assert record is not None
        assert record.period == '2022', \
            f"Deveria usar Net Debt 2022, mas usou {record.period}"
        assert value == 220.0


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 2: Dado publicado antes da observation_date PODE ser utilizado
# ══════════════════════════════════════════════════════════════════════════════

class TestPastDataIncluded:
    """Um dado publicado antes da observation_date pode ser utilizado."""

    def test_past_ebitda_included(self, sample_store):
        """EBITDA 2023 (publicado em 2024-03-15) PODE ser usado em 2024-04-30."""
        observation_date = datetime(2024, 4, 30)
        available = sample_store.get_available_records('PETR4.SA', 'EBITDA', observation_date)

        periods = [r.period for r in available]
        assert '2023' in periods, \
            "EBITDA 2023 (pub_date=2024-03-15) DEVERIA estar disponível em 2024-04-30"

    def test_on_publication_date_included(self, sample_store):
        """Dado publicado EXATAMENTE na observation_date PODE ser usado (<=)."""
        observation_date = datetime(2024, 3, 15)
        available = sample_store.get_available_records('PETR4.SA', 'EBITDA', observation_date)

        periods = [r.period for r in available]
        assert '2023' in periods, \
            "EBITDA 2023 deveria estar disponível na própria data de publicação (2024-03-15)"


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 3: Dado sem publication_date recebe flag UNKNOWN
# ══════════════════════════════════════════════════════════════════════════════

class TestUnknownPublicationDate:
    """Dado com publication_date desconhecida recebe lookahead_flag = UNKNOWN."""

    def test_unknown_flag_assigned(self, store_with_unknown):
        """Registro sem publication_date deve retornar UNKNOWN."""
        records = store_with_unknown.get_all_records('MGLU3.SA', 'EBITDA')
        assert len(records) == 1

        record = records[0]
        flag = record.get_lookahead_flag(datetime(2024, 6, 30))
        assert flag == 'UNKNOWN', f"Flag deveria ser UNKNOWN, mas foi {flag}"

    def test_unknown_not_in_pit_clean(self, store_with_unknown):
        """Registro sem publication_date NÃO aparece nos resultados PIT limpos."""
        observation_date = datetime(2024, 6, 30)
        available = store_with_unknown.get_available_records('MGLU3.SA', 'EBITDA', observation_date)

        assert len(available) == 0, \
            "Registro sem publication_date NÃO deveria aparecer nos resultados PIT limpos"

    def test_unknown_in_audit(self, store_with_unknown):
        """Registro sem publication_date DEVE aparecer nos registros com unknown."""
        observation_date = datetime(2024, 6, 30)
        available, unknown = store_with_unknown.get_available_records_with_unknown(
            'MGLU3.SA', 'EBITDA', observation_date
        )

        assert len(available) == 0
        assert len(unknown) == 1, \
            "Registro sem publication_date deveria estar na lista 'unknown'"

    def test_consolidated_flag_unknown(self):
        """check_lookahead retorna UNKNOWN quando qualquer registro não tem pub_date."""
        record = FundamentalRecord(
            ticker='TEST', metric='EBITDA', period='2023',
            period_end_date=datetime(2023, 12, 31),
            value=10.0, source='test',
            publication_date=None,
            data_source_type='HARDCODED',
            data_quality_flag='UNKNOWN',
        )
        flag = check_lookahead([record], datetime(2024, 6, 30))
        assert flag == 'UNKNOWN'


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 4: EBITDA LTM usa somente os 4 trimestres mais recentes DISPONÍVEIS
# ══════════════════════════════════════════════════════════════════════════════

class TestEbitdaLtmPit:
    """O EBITDA LTM utiliza somente os 4 períodos mais recentes disponíveis naquela data."""

    def test_ltm_all_four_available(self, store_with_quarterly):
        """Com 4 trimestres disponíveis, LTM = soma dos 4."""
        # Observação em 2024-03-31 → todos os 4 trimestres publicados
        observation_date = datetime(2024, 3, 31)
        value, records, method = store_with_quarterly.get_ebitda_ltm_pit('VALE3.SA', observation_date)

        expected = 18.5 + 19.2 + 20.1 + 17.6  # 75.4
        assert value is not None
        assert abs(value - expected) < 0.01, \
            f"EBITDA LTM deveria ser {expected}, mas foi {value}"
        assert method == 'QUARTERLY_LTM_PIT'
        assert len(records) == 4

    def test_ltm_only_three_available(self, store_with_quarterly):
        """Com apenas 3 trimestres publicados, NÃO calcula LTM trimestral (< 4)."""
        # Observação em 2024-01-31 → Q4/23 ainda NÃO publicado (pub 2024-02-28)
        observation_date = datetime(2024, 1, 31)
        value, records, method = store_with_quarterly.get_ebitda_ltm_pit('VALE3.SA', observation_date)

        # Apenas Q1, Q2, Q3 de 2023 estão disponíveis (3 < 4)
        # Deve retornar UNAVAILABLE (sem dados anuais de fallback neste store)
        assert method in ('UNAVAILABLE', 'ANNUAL_PIT'), \
            f"Com apenas 3 trimestres disponíveis, método deveria ser UNAVAILABLE, mas foi {method}"

    def test_ltm_respects_publication_date(self, store_with_quarterly):
        """Q4/23 (pub 2024-02-28) NÃO entra no LTM de 2024-02-15."""
        observation_date = datetime(2024, 2, 15)
        available = store_with_quarterly.get_available_records(
            'VALE3.SA', 'EBITDA_QUARTERLY', observation_date
        )

        periods = [r.period for r in available]
        assert '2023Q4' not in periods, \
            "Q4/23 (pub 2024-02-28) NÃO deveria estar disponível em 2024-02-15"


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 5: Nenhum cálculo final de EV/EBITDA utiliza dados futuros
# ══════════════════════════════════════════════════════════════════════════════

class TestEvEbitdaNoFutureData:
    """Nenhum cálculo final de EV/EBITDA utiliza dados com publication_date > observation_date."""

    def test_ev_ebitda_clean_observations(self, sample_store):
        """Observação 'limpa' (FALSE) não utiliza nenhum dado futuro."""
        # Em 2024-04-30, EBITDA 2023 (pub 2024-03-15) já foi publicado
        observation_date = datetime(2024, 4, 30)

        ebitda_val, ebitda_rec = sample_store.get_latest_value(
            'PETR4.SA', 'EBITDA', observation_date
        )
        nd_val, nd_rec = sample_store.get_net_debt_pit('PETR4.SA', observation_date)

        # Verificar que todos os registros usados estão no passado
        for record in [ebitda_rec, nd_rec]:
            if record:
                assert record.publication_date <= observation_date, \
                    f"Registro {record.period} tem pub_date={record.publication_date} > obs_date={observation_date}"

    def test_ev_ebitda_excludes_future_in_calculation(self, sample_store):
        """Em 2024-01-31, EV/EBITDA deve usar EBITDA de 2022, não 2023."""
        observation_date = datetime(2024, 1, 31)

        ebitda_val, ebitda_rec = sample_store.get_latest_value(
            'PETR4.SA', 'EBITDA', observation_date
        )

        assert ebitda_rec is not None
        assert ebitda_rec.period == '2022', \
            f"Em 2024-01-31, deveria usar EBITDA 2022, mas usou {ebitda_rec.period}"
        assert ebitda_val == 261.016

    def test_observation_flag_correct(self):
        """compute_observation_lookahead_flag retorna TRUE se qualquer componente é TRUE."""
        # Caso: EBITDA FALSE, Net Debt TRUE → resultado TRUE
        flag = compute_observation_lookahead_flag('FALSE', 'TRUE', 'FALSE', 'UNKNOWN')
        assert flag == 'TRUE'

        # Caso: todos FALSE → resultado FALSE
        flag = compute_observation_lookahead_flag('FALSE', 'FALSE', 'FALSE', 'FALSE')
        assert flag == 'FALSE'

        # Caso: um UNKNOWN, nenhum TRUE → resultado UNKNOWN
        flag = compute_observation_lookahead_flag('FALSE', 'UNKNOWN', 'FALSE', 'FALSE')
        assert flag == 'UNKNOWN'


# ══════════════════════════════════════════════════════════════════════════════
# TESTE 6: Hardcodes continuam funcionando quando yfinance não fornece
# ══════════════════════════════════════════════════════════════════════════════

class TestHardcodedFallbackPreserved:
    """Os hardcodes antigos continuam sendo utilizados quando o yfinance não fornece o dado."""

    def test_hardcoded_data_in_store(self):
        """Dados hardcoded são populados corretamente no store."""
        store = FundamentalStore()

        ebitda_dates = pd.to_datetime(['2022-12-31', '2023-12-31'])
        ebitda_hardcoded = {'PETR4.SA': [261.016, 264.987]}
        net_debt_hardcoded = {'PETR4.SA': [220.0, 222.0]}
        net_income_hardcoded = {'PETR4.SA': [188.728, 124.606]}
        shares_fallback = {'PETR4.SA': 13.04}

        populate_store_from_hardcoded(
            store, ebitda_dates,
            ebitda_hardcoded, net_debt_hardcoded,
            net_income_hardcoded, shares_fallback,
        )

        # Verificar que os dados foram adicionados
        ebitda_records = store.get_all_records('PETR4.SA', 'EBITDA')
        assert len(ebitda_records) == 2, \
            f"Deveria ter 2 registros EBITDA, mas tem {len(ebitda_records)}"

        nd_records = store.get_all_records('PETR4.SA', 'NET_DEBT')
        assert len(nd_records) == 2

        ni_records = store.get_all_records('PETR4.SA', 'NET_INCOME')
        assert len(ni_records) == 2

        shares_records = store.get_all_records('PETR4.SA', 'SHARES_OUTSTANDING')
        assert len(shares_records) == 1

    def test_hardcoded_values_preserved(self):
        """Os valores hardcoded são idênticos aos originais."""
        store = FundamentalStore()

        ebitda_dates = pd.to_datetime(['2022-12-31', '2023-12-31'])
        ebitda_hardcoded = {'VALE3.SA': [91.242, 75.387]}
        net_debt_hardcoded = {'VALE3.SA': [40.0, 48.0]}
        net_income_hardcoded = {'VALE3.SA': [95.736, 39.840]}
        shares_fallback = {'VALE3.SA': 4.54}

        populate_store_from_hardcoded(
            store, ebitda_dates,
            ebitda_hardcoded, net_debt_hardcoded,
            net_income_hardcoded, shares_fallback,
        )

        # EBITDA 2023 = 75.387 (valor original preservado)
        ebitda_records = store.get_all_records('VALE3.SA', 'EBITDA')
        rec_2023 = [r for r in ebitda_records if r.period == '2023'][0]
        assert rec_2023.value == 75.387, \
            f"EBITDA 2023 deveria ser 75.387, mas é {rec_2023.value}"
        assert rec_2023.data_source_type == 'HARDCODED'

    def test_hardcoded_used_as_fallback(self):
        """
        Quando yfinance não fornece dado, o hardcoded continua disponível no store.
        Simula cenário: store tem apenas dados hardcoded (sem yfinance).
        """
        store = FundamentalStore()

        ebitda_dates = pd.to_datetime(['2022-12-31', '2023-12-31'])
        ebitda_hardcoded = {'WEGE3.SA': [7.090, 8.503]}
        net_debt_hardcoded = {'WEGE3.SA': [-2.4, -3.1]}
        net_income_hardcoded = {'WEGE3.SA': [4.208, 5.730]}
        shares_fallback = {'WEGE3.SA': 4.19}

        populate_store_from_hardcoded(
            store, ebitda_dates,
            ebitda_hardcoded, net_debt_hardcoded,
            net_income_hardcoded, shares_fallback,
        )

        # Depois de publication_date estimada, o dado deve estar disponível
        observation_date = pd.Timestamp('2024-04-30')
        value, record = store.get_latest_value('WEGE3.SA', 'EBITDA', observation_date)

        assert value is not None, "Dado hardcoded deveria estar disponível como fallback"
        assert value == 8.503
        assert record.data_source_type == 'HARDCODED'
