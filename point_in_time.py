"""
POINT_IN_TIME — Framework de Rastreabilidade Temporal (Look-Ahead Bias Correction)
==================================================================================

Este módulo implementa o conceito de Point-in-Time / As-of Date para dados fundamentais,
garantindo que nenhum dado financeiro seja utilizado antes de sua data de publicação real.

Regra fundamental:
    publication_date <= observation_date

Estruturas:
    - FundamentalRecord: Registro individual de dado fundamental com metadados temporais.
    - FundamentalStore: Armazena e consulta registros respeitando restrições temporais.

Compatibilidade:
    - Mantém 100% de compatibilidade com os dados hardcoded existentes.
    - Dados sem publication_date são marcados como UNKNOWN e tratados separadamente.
    - Não remove, altera ou substitui nenhum dado existente no projeto.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
import pandas as pd
import numpy as np

from publication_dates import (
    PUBLICATION_DATE_ESTIMATES,
    ANNUAL_PUBLICATION_LAG_DAYS,
    get_estimated_publication_date,
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. ESTRUTURA DE DADOS — FundamentalRecord
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FundamentalRecord:
    """
    Registro individual de dado fundamental com rastreabilidade temporal completa.

    Attributes:
        ticker: Código do ativo (e.g., 'PETR4.SA')
        metric: Tipo de métrica ('EBITDA', 'NET_DEBT', 'NET_INCOME', 'SHARES_OUTSTANDING')
        period: Período textual (e.g., '2023', '2023Q4')
        period_end_date: Data de encerramento do período econômico
        value: Valor numérico (em R$ bilhões para EBITDA/NetDebt/NetIncome, bilhões de ações para shares)
        source: Descrição textual da fonte
        publication_date: Data em que o dado foi divulgado publicamente (None se desconhecida)
        data_source_type: Tipo de fonte ('YFINANCE', 'HARDCODED', 'FALLBACK')
        data_quality_flag: Qualidade da publication_date ('EXACT', 'APPROXIMATE', 'UNKNOWN',
                           'ESTIMATED_PUBLICATION_DATE')
    """
    ticker: str
    metric: str
    period: str
    period_end_date: datetime
    value: float
    source: str
    publication_date: Optional[datetime]
    data_source_type: str
    data_quality_flag: str

    def is_available_at(self, observation_date: datetime) -> Optional[bool]:
        """
        Verifica se este registro estava publicamente disponível em observation_date.

        Returns:
            True: Disponível (publication_date <= observation_date)
            False: Não disponível (publication_date > observation_date)
            None: Indeterminado (publication_date é None)
        """
        if self.publication_date is None:
            return None
        return self.publication_date <= observation_date

    def get_lookahead_flag(self, observation_date: datetime) -> str:
        """
        Retorna o lookahead_flag para este registro em relação a observation_date.

        Returns:
            'FALSE': Sem look-ahead bias (publication_date <= observation_date)
            'TRUE': Com look-ahead bias (publication_date > observation_date)
            'UNKNOWN': Indeterminado (publication_date desconhecida ou estimada)
        """
        if self.publication_date is None:
            return 'UNKNOWN'

        if self.data_quality_flag in ('UNKNOWN', 'ESTIMATED_PUBLICATION_DATE'):
            return 'UNKNOWN'

        if self.publication_date > observation_date:
            return 'TRUE'
        return 'FALSE'


# ══════════════════════════════════════════════════════════════════════════════
# 2. ARMAZENAMENTO E CONSULTA — FundamentalStore
# ══════════════════════════════════════════════════════════════════════════════

class FundamentalStore:
    """
    Armazena registros fundamentais e permite consultas Point-in-Time.

    Todos os dados são armazenados com metadados temporais completos.
    Consultas respeitam a restrição: publication_date <= observation_date.
    """

    def __init__(self):
        self._records: List[FundamentalRecord] = []
        # Índice por (ticker, metric) para acesso rápido
        self._index: Dict[Tuple[str, str], List[FundamentalRecord]] = {}

    def add_record(self, record: FundamentalRecord):
        """Adiciona um registro fundamental ao store."""
        self._records.append(record)
        key = (record.ticker, record.metric)
        if key not in self._index:
            self._index[key] = []
        self._index[key].append(record)

    def add_records(self, records: List[FundamentalRecord]):
        """Adiciona múltiplos registros ao store."""
        for record in records:
            self.add_record(record)

    def get_all_records(self, ticker: str = None, metric: str = None) -> List[FundamentalRecord]:
        """Retorna todos os registros, opcionalmente filtrados por ticker e/ou metric."""
        if ticker and metric:
            return list(self._index.get((ticker, metric), []))
        elif ticker:
            return [r for r in self._records if r.ticker == ticker]
        elif metric:
            return [r for r in self._records if r.metric == metric]
        return list(self._records)

    def get_available_records(
        self, ticker: str, metric: str, observation_date: datetime
    ) -> List[FundamentalRecord]:
        """
        Retorna APENAS registros disponíveis na observation_date.

        Filtra por: publication_date <= observation_date
        Registros sem publication_date são EXCLUÍDOS (não podem participar da análise PIT limpa).
        """
        candidates = self._index.get((ticker, metric), [])
        available = []
        for r in candidates:
            avail = r.is_available_at(observation_date)
            if avail is True:  # Somente registros confirmadamente disponíveis
                available.append(r)
        return sorted(available, key=lambda r: r.period_end_date, reverse=True)

    def get_available_records_with_unknown(
        self, ticker: str, metric: str, observation_date: datetime
    ) -> Tuple[List[FundamentalRecord], List[FundamentalRecord]]:
        """
        Retorna registros disponíveis E registros com status desconhecido.

        Returns:
            Tuple de (available_records, unknown_records)
        """
        candidates = self._index.get((ticker, metric), [])
        available = []
        unknown = []
        for r in candidates:
            avail = r.is_available_at(observation_date)
            if avail is True:
                available.append(r)
            elif avail is None:
                unknown.append(r)
            # avail is False → dado futuro, excluído
        return (
            sorted(available, key=lambda r: r.period_end_date, reverse=True),
            sorted(unknown, key=lambda r: r.period_end_date, reverse=True),
        )

    def get_latest_value(
        self, ticker: str, metric: str, observation_date: datetime
    ) -> Tuple[Optional[float], Optional[FundamentalRecord]]:
        """
        Retorna o valor mais recente disponível para (ticker, metric) em observation_date.

        Returns:
            Tuple de (value, record) ou (None, None) se nenhum disponível.
        """
        available = self.get_available_records(ticker, metric, observation_date)
        if available:
            latest = available[0]  # Já ordenado por period_end_date desc
            return latest.value, latest
        return None, None

    def get_ebitda_ltm_pit(
        self, ticker: str, observation_date: datetime
    ) -> Tuple[Optional[float], List[FundamentalRecord], str]:
        """
        Calcula EBITDA LTM Point-in-Time.

        Prioridade:
        1. Soma dos 4 trimestres mais recentes disponíveis (se houver dados trimestrais)
        2. Último dado anual disponível (fallback)

        Returns:
            Tuple de (ebitda_ltm_value, records_used, method)
            method: 'QUARTERLY_LTM_PIT' ou 'ANNUAL_PIT' ou 'UNAVAILABLE'
        """
        # Tentar dados trimestrais primeiro
        quarterly = self.get_available_records(ticker, 'EBITDA_QUARTERLY', observation_date)
        if len(quarterly) >= 4:
            top4 = quarterly[:4]  # 4 mais recentes disponíveis
            ltm = sum(r.value for r in top4)
            return ltm, top4, 'QUARTERLY_LTM_PIT'

        # Fallback: dado anual
        annual = self.get_available_records(ticker, 'EBITDA', observation_date)
        if annual:
            latest = annual[0]
            return latest.value, [latest], 'ANNUAL_PIT'

        return None, [], 'UNAVAILABLE'

    def get_net_debt_pit(
        self, ticker: str, observation_date: datetime
    ) -> Tuple[Optional[float], Optional[FundamentalRecord]]:
        """
        Retorna o Net Debt mais recente disponível em observation_date.
        """
        return self.get_latest_value(ticker, 'NET_DEBT', observation_date)

    def get_net_income_pit(
        self, ticker: str, observation_date: datetime
    ) -> Tuple[Optional[float], Optional[FundamentalRecord]]:
        """
        Retorna o Net Income mais recente disponível em observation_date.
        """
        return self.get_latest_value(ticker, 'NET_INCOME', observation_date)


# ══════════════════════════════════════════════════════════════════════════════
# 3. FUNÇÕES DE VERIFICAÇÃO DE LOOK-AHEAD
# ══════════════════════════════════════════════════════════════════════════════

def check_lookahead(records_used: List[FundamentalRecord], observation_date: datetime) -> str:
    """
    Determina o lookahead_flag para um conjunto de registros usados em observation_date.

    Args:
        records_used: Lista de FundamentalRecord utilizados no cálculo.
        observation_date: Data da observação.

    Returns:
        'FALSE': Todos os registros confirmadamente disponíveis (EXACT pub_date <= obs_date)
        'TRUE': Pelo menos um registro com publication_date > observation_date
        'UNKNOWN': Pelo menos um registro com pub_date desconhecida ou estimada
    """
    if not records_used:
        return 'UNKNOWN'

    has_unknown = False
    for r in records_used:
        flag = r.get_lookahead_flag(observation_date)
        if flag == 'TRUE':
            return 'TRUE'
        if flag == 'UNKNOWN':
            has_unknown = True

    return 'UNKNOWN' if has_unknown else 'FALSE'


# ══════════════════════════════════════════════════════════════════════════════
# 4. CONSTRUÇÃO DE SÉRIES MENSAIS POINT-IN-TIME
# ══════════════════════════════════════════════════════════════════════════════

def build_pit_monthly_series(
    store: FundamentalStore,
    ticker: str,
    metric: str,
    full_dates: pd.DatetimeIndex,
    is_ebitda: bool = False,
) -> Tuple[pd.Series, pd.Series, List[dict]]:
    """
    Constrói série mensal Point-in-Time para um ticker e métrica.

    Para cada observation_date em full_dates, consulta o FundamentalStore
    para obter apenas dados disponíveis naquela data.

    Args:
        store: FundamentalStore populado.
        ticker: Código do ativo.
        metric: 'EBITDA', 'NET_DEBT', 'NET_INCOME'.
        full_dates: DatetimeIndex das datas de observação mensais.
        is_ebitda: Se True, usa lógica especial de EBITDA LTM (4 trimestres).

    Returns:
        Tuple de:
            - pd.Series com os valores Point-in-Time
            - pd.Series com os lookahead_flags por data
            - List[dict] com registros de auditoria detalhados
    """
    values = pd.Series(np.nan, index=full_dates, dtype=float)
    flags = pd.Series('UNKNOWN', index=full_dates, dtype=str)
    audit_records = []

    for obs_date in full_dates:
        if is_ebitda:
            value, records_used, method = store.get_ebitda_ltm_pit(ticker, obs_date)
        else:
            value, record = store.get_latest_value(ticker, metric, obs_date)
            records_used = [record] if record else []

        if value is not None:
            values.loc[obs_date] = value

        flag = check_lookahead(records_used, obs_date)
        flags.loc[obs_date] = flag

        # Registrar auditoria
        for r in records_used:
            audit_records.append({
                'ticker': ticker,
                'observation_date': obs_date,
                'metric': r.metric if r else metric,
                'period': r.period if r else None,
                'period_end_date': r.period_end_date if r else None,
                'publication_date': r.publication_date if r else None,
                'value': r.value if r else None,
                'source': r.source if r else None,
                'data_source_type': r.data_source_type if r else None,
                'data_quality_flag': r.data_quality_flag if r else None,
                'lookahead_flag': r.get_lookahead_flag(obs_date) if r else 'UNKNOWN',
            })

        # Se nenhum registro foi usado, registrar a ausência
        if not records_used:
            audit_records.append({
                'ticker': ticker,
                'observation_date': obs_date,
                'metric': metric,
                'period': None,
                'period_end_date': None,
                'publication_date': None,
                'value': None,
                'source': 'NO_DATA_AVAILABLE_PIT',
                'data_source_type': None,
                'data_quality_flag': 'UNKNOWN',
                'lookahead_flag': 'UNKNOWN',
            })

    return values, flags, audit_records


# ══════════════════════════════════════════════════════════════════════════════
# 5. POPULAÇÃO DO STORE A PARTIR DOS DADOS HARDCODED
# ══════════════════════════════════════════════════════════════════════════════

def populate_store_from_hardcoded(
    store: FundamentalStore,
    ebitda_dates: pd.DatetimeIndex,
    ebitda_hardcoded: dict,
    net_debt_hardcoded: dict,
    net_income_hardcoded: dict,
    shares_fallback: dict,
):
    """
    Popula o FundamentalStore com os dados hardcoded existentes do projeto,
    adicionando metadados temporais e de fonte.

    Os dados hardcoded são dados ANUAIS com period_end_date em 31/12 de cada ano.
    As publication_dates são ESTIMATIVAS (~75 dias após period_end_date).

    Args:
        store: FundamentalStore a ser populado.
        ebitda_dates: DatetimeIndex com as datas dos dados anuais.
        ebitda_hardcoded: Dict ticker → [valores anuais] (EBITDA em R$ bilhões).
        net_debt_hardcoded: Dict ticker → [valores anuais] (Net Debt em R$ bilhões).
        net_income_hardcoded: Dict ticker → [valores anuais] (Net Income em R$ bilhões).
        shares_fallback: Dict ticker → valor (shares em bilhões).
    """
    for ticker, values in ebitda_hardcoded.items():
        for date, value in zip(ebitda_dates, values):
            period_end_str = date.strftime('%Y-%m-%d')
            pub_date_str = get_estimated_publication_date(period_end_str, 'annual')
            pub_date = pd.to_datetime(pub_date_str) if pub_date_str else None

            quality_flag = 'ESTIMATED_PUBLICATION_DATE' if pub_date else 'UNKNOWN'

            store.add_record(FundamentalRecord(
                ticker=ticker,
                metric='EBITDA',
                period=str(date.year),
                period_end_date=date,
                value=value,
                source=f'EBITDA_HARDCODED_BI {date.year}',
                publication_date=pub_date,
                data_source_type='HARDCODED',
                data_quality_flag=quality_flag,
            ))

    for ticker, values in net_debt_hardcoded.items():
        for date, value in zip(ebitda_dates, values):
            period_end_str = date.strftime('%Y-%m-%d')
            pub_date_str = get_estimated_publication_date(period_end_str, 'annual')
            pub_date = pd.to_datetime(pub_date_str) if pub_date_str else None

            quality_flag = 'ESTIMATED_PUBLICATION_DATE' if pub_date else 'UNKNOWN'

            store.add_record(FundamentalRecord(
                ticker=ticker,
                metric='NET_DEBT',
                period=str(date.year),
                period_end_date=date,
                value=value,
                source=f'NET_DEBT_HARDCODED_BI {date.year}',
                publication_date=pub_date,
                data_source_type='HARDCODED',
                data_quality_flag=quality_flag,
            ))

    for ticker, values in net_income_hardcoded.items():
        for date, value in zip(ebitda_dates, values):
            period_end_str = date.strftime('%Y-%m-%d')
            pub_date_str = get_estimated_publication_date(period_end_str, 'annual')
            pub_date = pd.to_datetime(pub_date_str) if pub_date_str else None

            quality_flag = 'ESTIMATED_PUBLICATION_DATE' if pub_date else 'UNKNOWN'

            store.add_record(FundamentalRecord(
                ticker=ticker,
                metric='NET_INCOME',
                period=str(date.year),
                period_end_date=date,
                value=value,
                source=f'NET_INCOME_HARDCODED_BI {date.year}',
                publication_date=pub_date,
                data_source_type='HARDCODED',
                data_quality_flag=quality_flag,
            ))

    for ticker, value in shares_fallback.items():
        # Shares outstanding fallback: sem publication_date conhecida
        # Marcado como UNKNOWN — não é possível determinar quando o dado
        # de shares se tornou público neste nível de granularidade
        store.add_record(FundamentalRecord(
            ticker=ticker,
            metric='SHARES_OUTSTANDING',
            period='CURRENT_FALLBACK',
            period_end_date=pd.Timestamp.now().normalize(),
            value=value,
            source='SHARES_OUTSTANDING_FALLBACK_BI',
            publication_date=None,
            data_source_type='FALLBACK',
            data_quality_flag='UNKNOWN',
        ))


def populate_store_from_yfinance(
    store: FundamentalStore,
    ticker: str,
    ebitda_series: pd.Series,
    ebitda_source: str,
    ebitda_dates: pd.DatetimeIndex,
):
    """
    Adiciona dados obtidos do yfinance ao FundamentalStore.

    O yfinance gratuito não fornece announcement_date da CVM,
    então os dados do yfinance são marcados com data_quality_flag='APPROXIMATE'.

    Para dados trimestrais do yfinance, assumimos que a publicação ocorreu
    ~45-60 dias após o period_end_date.
    """
    if 'YFINANCE' not in ebitda_source:
        return  # Não há dados yfinance para adicionar

    for date in ebitda_dates:
        if date in ebitda_series.index and pd.notna(ebitda_series.loc[date]):
            value = ebitda_series.loc[date]
            period_end_str = date.strftime('%Y-%m-%d')
            pub_date_str = get_estimated_publication_date(period_end_str, 'annual')
            pub_date = pd.to_datetime(pub_date_str) if pub_date_str else None

            store.add_record(FundamentalRecord(
                ticker=ticker,
                metric='EBITDA',
                period=str(date.year),
                period_end_date=date,
                value=value,
                source=f'{ebitda_source} {date.year}',
                publication_date=pub_date,
                data_source_type='YFINANCE',
                data_quality_flag='APPROXIMATE' if pub_date else 'UNKNOWN',
            ))


# ══════════════════════════════════════════════════════════════════════════════
# 6. GERAÇÃO DE RELATÓRIO DE AUDITORIA
# ══════════════════════════════════════════════════════════════════════════════

def generate_audit_dataframe(audit_records: List[dict]) -> pd.DataFrame:
    """
    Gera um DataFrame de auditoria a partir dos registros coletados durante
    a construção das séries Point-in-Time.

    Colunas:
        ticker, observation_date, metric, period, period_end_date,
        publication_date, value, source, data_source_type,
        data_quality_flag, lookahead_flag
    """
    if not audit_records:
        return pd.DataFrame(columns=[
            'ticker', 'observation_date', 'metric', 'period', 'period_end_date',
            'publication_date', 'value', 'source', 'data_source_type',
            'data_quality_flag', 'lookahead_flag',
        ])

    df = pd.DataFrame(audit_records)

    # Ordenar para facilitar auditoria manual
    sort_cols = ['ticker', 'observation_date', 'metric']
    available_sort = [c for c in sort_cols if c in df.columns]
    if available_sort:
        df = df.sort_values(available_sort).reset_index(drop=True)

    return df


def compute_observation_lookahead_flag(
    ebitda_flag: str, net_debt_flag: str, net_income_flag: str, shares_flag: str = 'UNKNOWN'
) -> str:
    """
    Computa o lookahead_flag consolidado para uma observação inteira.

    Regra:
        - Se QUALQUER componente for 'TRUE' → 'TRUE'
        - Se QUALQUER componente for 'UNKNOWN' e nenhum for 'TRUE' → 'UNKNOWN'
        - Se TODOS forem 'FALSE' → 'FALSE'
    """
    flags = [ebitda_flag, net_debt_flag, net_income_flag, shares_flag]

    if 'TRUE' in flags:
        return 'TRUE'
    if 'UNKNOWN' in flags:
        return 'UNKNOWN'
    return 'FALSE'
