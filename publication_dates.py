"""
PUBLICATION_DATES — Mapeamento de datas de publicação estimadas para dados hardcoded
===================================================================================

Empresas brasileiras de capital aberto divulgam resultados anuais entre 60 e 90 dias
após o encerramento do exercício fiscal (deadline CVM: ~3 meses). Grandes empresas
do Ibovespa tipicamente divulgam entre fim de fevereiro e meados de março.

IMPORTANTE:
    - Estas são ESTIMATIVAS CONSERVADORAS, NÃO datas verificadas na CVM.
    - Todos os registros que usarem estas estimativas serão marcados com:
          data_quality_flag = 'ESTIMATED_PUBLICATION_DATE'
          lookahead_flag = 'UNKNOWN'
    - Para obter datas exatas, seria necessário consultar o sistema de
      entrega de documentos da CVM (Empresas.NET / RAD) por empresa.
    - NÃO inventar datas: se não for possível estimar, usar None.
"""

# ══════════════════════════════════════════════════════════════════════════════
# ESTIMATIVAS DE PUBLICATION_DATE PARA RESULTADOS ANUAIS
# ══════════════════════════════════════════════════════════════════════════════

# Convenção: ~75 dias após period_end_date (conservador)
# Resultados de exercícios encerrados em 31/12 → publicados ~meados de março

ANNUAL_PUBLICATION_LAG_DAYS = 75

PUBLICATION_DATE_ESTIMATES = {
    # period_end_date → estimated_publication_date
    '2020-12-31': '2021-03-16',
    '2021-12-31': '2022-03-16',
    '2022-12-31': '2023-03-16',
    '2023-12-31': '2024-03-15',
    '2024-12-31': '2025-03-16',
    '2025-12-31': '2026-03-16',
}

# ══════════════════════════════════════════════════════════════════════════════
# ESTIMATIVAS DE PUBLICATION_DATE PARA RESULTADOS TRIMESTRAIS
# ══════════════════════════════════════════════════════════════════════════════

# Resultados trimestrais: ~45-60 dias após period_end_date
# Convenção conservadora: ~60 dias

QUARTERLY_PUBLICATION_LAG_DAYS = 60

# Para uso futuro quando houver dados trimestrais hardcoded
# Formato: 'YYYY-MM-DD' (period_end_date) → 'YYYY-MM-DD' (estimated_publication_date)
QUARTERLY_PUBLICATION_DATE_ESTIMATES = {
    # Q1 (encerra 31/03) → publicação ~fim de maio
    # Q2 (encerra 30/06) → publicação ~fim de agosto
    # Q3 (encerra 30/09) → publicação ~fim de novembro
    # Q4 (encerra 31/12) → publicação ~fim de fevereiro/março (mesmo que anual)
}


def get_estimated_publication_date(period_end_date_str, period_type='annual'):
    """
    Retorna a data de publicação estimada para um dado period_end_date.

    Args:
        period_end_date_str: String 'YYYY-MM-DD' do encerramento do período.
        period_type: 'annual' ou 'quarterly'.

    Returns:
        String 'YYYY-MM-DD' da publicação estimada, ou None se não disponível.
    """
    if period_type == 'annual':
        return PUBLICATION_DATE_ESTIMATES.get(period_end_date_str, None)
    elif period_type == 'quarterly':
        return QUARTERLY_PUBLICATION_DATE_ESTIMATES.get(period_end_date_str, None)
    return None
