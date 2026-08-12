"""
CANDIDATE_UNIVERSE — Universo Candidato de Empresas da B3
=========================================================

Estrutura centralizada do universo candidato para o Projeto Bico de Pato.
Contém empresas brasileiras não-financeiras listadas na B3 cobrindo diversos setores.

Regra fundamental:
    - NÃO inclui instituições financeiras (bancos, seguradoras, corretoras).
    - Preserva as 20 empresas originais do estudo.
    - Expandido para 100+ candidatas para amostragem representativa da B3.
    - Validação de integridade garante unicidade de tickers.
"""

CANDIDATE_TICKERS = [
    # ── 1. Commodities & Materiais Básicos (Original + Expansão) ──
    {"ticker": "PETR4.SA", "name": "Petrobras", "sector": "Petróleo, Gás & Biocombustíveis"},
    {"ticker": "VALE3.SA", "name": "Vale", "sector": "Mineração"},
    {"ticker": "GGBR4.SA", "name": "Gerdau", "sector": "Siderurgia & Metalurgia"},
    {"ticker": "CSNA3.SA", "name": "CSN", "sector": "Siderurgia & Metalurgia"},
    {"ticker": "SUZB3.SA", "name": "Suzano", "sector": "Papel & Celulose"},
    {"ticker": "JBSS3.SA", "name": "JBS", "sector": "Alimentos & Bebidas"},
    {"ticker": "PRIO3.SA", "name": "PRIO", "sector": "Petróleo, Gás & Biocombustíveis"},
    {"ticker": "BRAV3.SA", "name": "Brava Energia", "sector": "Petróleo, Gás & Biocombustíveis"},
    {"ticker": "RECV3.SA", "name": "PetroReconcavo", "sector": "Petróleo, Gás & Biocombustíveis"},
    {"ticker": "UGPA3.SA", "name": "Ultrapar", "sector": "Petróleo, Gás & Biocombustíveis"},
    {"ticker": "VBBR3.SA", "name": "Vibra Energia", "sector": "Petróleo, Gás & Biocombustíveis"},
    {"ticker": "KLBN11.SA", "name": "Klabin", "sector": "Papel & Celulose"},
    {"ticker": "UNIP6.SA", "name": "Unipar", "sector": "Químicos"},
    {"ticker": "BRKM5.SA", "name": "Braskem", "sector": "Químicos"},
    {"ticker": "USIM5.SA", "name": "Usiminas", "sector": "Siderurgia & Metalurgia"},
    {"ticker": "SMTO3.SA", "name": "São Martinho", "sector": "Açúcar & Álcool"},
    {"ticker": "SLCE3.SA", "name": "SLC Agrícola", "sector": "Agronegócio"},
    {"ticker": "BEEF3.SA", "name": "Minerva", "sector": "Alimentos & Bebidas"},
    {"ticker": "MRFG3.SA", "name": "Marfrig", "sector": "Alimentos & Bebidas"},
    {"ticker": "BRFS3.SA", "name": "BRF", "sector": "Alimentos & Bebidas"},

    # ── 2. Utilidades Públicas (Energia & Saneamento) ──
    {"ticker": "ELET3.SA", "name": "Eletrobras", "sector": "Energia Elétrica"},
    {"ticker": "EQTL3.SA", "name": "Equatorial", "sector": "Energia Elétrica"},
    {"ticker": "CPLE6.SA", "name": "Copel", "sector": "Energia Elétrica"},
    {"ticker": "SBSP3.SA", "name": "Sabesp", "sector": "Água & Saneamento"},
    {"ticker": "EGIE3.SA", "name": "Engie Brasil", "sector": "Energia Elétrica"},
    {"ticker": "TAEE11.SA", "name": "Taesa", "sector": "Energia Elétrica"},
    {"ticker": "TRPL4.SA", "name": "ISA CTEEP", "sector": "Energia Elétrica"},
    {"ticker": "CPFE3.SA", "name": "CPFL Energia", "sector": "Energia Elétrica"},
    {"ticker": "ALUP11.SA", "name": "Alupar", "sector": "Energia Elétrica"},
    {"ticker": "NEOE3.SA", "name": "Neoenergia", "sector": "Energia Elétrica"},
    {"ticker": "ENGI11.SA", "name": "Energisa", "sector": "Energia Elétrica"},
    {"ticker": "AURE3.SA", "name": "Auren Energia", "sector": "Energia Elétrica"},
    {"ticker": "ENEV3.SA", "name": "Eneva", "sector": "Energia Elétrica"},
    {"ticker": "CSMG3.SA", "name": "Copasa", "sector": "Água & Saneamento"},
    {"ticker": "SAPR11.SA", "name": "Sanepar", "sector": "Água & Saneamento"},

    # ── 3. Consumo, Varejo & Distribuição ──
    {"ticker": "ABEV3.SA", "name": "Ambev", "sector": "Alimentos & Bebidas"},
    {"ticker": "MGLU3.SA", "name": "Magazine Luiza", "sector": "Varejo"},
    {"ticker": "LREN3.SA", "name": "Lojas Renner", "sector": "Varejo"},
    {"ticker": "ALPA4.SA", "name": "Alpargatas", "sector": "Varejo"},
    {"ticker": "SOMA3.SA", "name": "Grupo Soma", "sector": "Varejo"},
    {"ticker": "PETZ3.SA", "name": "Petz", "sector": "Varejo"},
    {"ticker": "BHIA3.SA", "name": "Casas Bahia", "sector": "Varejo"},
    {"ticker": "GUAR3.SA", "name": "Guararapes", "sector": "Varejo"},
    {"ticker": "NTCO3.SA", "name": "Natura &Co", "sector": "Bens de Consumo"},
    {"ticker": "CRFB3.SA", "name": "Carrefour Brasil", "sector": "Varejo"},
    {"ticker": "ASAI3.SA", "name": "Assaí Atacadista", "sector": "Varejo"},
    {"ticker": "PCAR3.SA", "name": "Pão de Açúcar", "sector": "Varejo"},
    {"ticker": "SMFT3.SA", "name": "Smart Fit", "sector": "Serviços"},
    {"ticker": "VIVA3.SA", "name": "Vivara", "sector": "Varejo"},

    # ── 4. Saúde & Farmacêutico ──
    {"ticker": "RADL3.SA", "name": "Raia Drogasil", "sector": "Varejo & Farmacêutico"},
    {"ticker": "HAPV3.SA", "name": "Hapvida", "sector": "Saúde"},
    {"ticker": "RDOR3.SA", "name": "Rede D'Or", "sector": "Saúde"},
    {"ticker": "FLRY3.SA", "name": "Fleury", "sector": "Saúde"},
    {"ticker": "QUAL3.SA", "name": "Qualicorp", "sector": "Saúde"},
    {"ticker": "BLAU3.SA", "name": "Blau Farmacêutica", "sector": "Farmacêutico"},
    {"ticker": "VVEO3.SA", "name": "Viveo", "sector": "Saúde"},
    {"ticker": "MATD3.SA", "name": "Mater Dei", "sector": "Saúde"},
    {"ticker": "PNVL3.SA", "name": "Panvel", "sector": "Varejo & Farmacêutico"},

    # ── 5. Bens de Capital, Indústria & Transporte ──
    {"ticker": "WEGE3.SA", "name": "WEG", "sector": "Máquinas & Equipamentos"},
    {"ticker": "RENT3.SA", "name": "Localiza", "sector": "Transporte & Logística"},
    {"ticker": "RAIL3.SA", "name": "Rumo", "sector": "Transporte & Logística"},
    {"ticker": "EMBR3.SA", "name": "Embraer", "sector": "Aviação & Defesa"},
    {"ticker": "CCRO3.SA", "name": "CCR", "sector": "Concessões & Logística"},
    {"ticker": "ECOR3.SA", "name": "Ecorodovias", "sector": "Concessões & Logística"},
    {"ticker": "STBP3.SA", "name": "Santos Brasil", "sector": "Transporte & Logística"},
    {"ticker": "HBSA3.SA", "name": "Hidrovias do Brasil", "sector": "Transporte & Logística"},
    {"ticker": "VAMO3.SA", "name": "Vamos", "sector": "Transporte & Logística"},
    {"ticker": "SIMH3.SA", "name": "Simpar", "sector": "Transporte & Logística"},
    {"ticker": "JSLG3.SA", "name": "JSL", "sector": "Transporte & Logística"},
    {"ticker": "POMO4.SA", "name": "Marcopolo", "sector": "Automóveis & Autopeças"},
    {"ticker": "LEVE3.SA", "name": "Mahle Metal Leve", "sector": "Automóveis & Autopeças"},
    {"ticker": "MYPK3.SA", "name": "Iochpe-Maxion", "sector": "Automóveis & Autopeças"},
    {"ticker": "RAPT4.SA", "name": "Randoncorp", "sector": "Automóveis & Autopeças"},
    {"ticker": "TUPY3.SA", "name": "Tupy", "sector": "Indústria"},
    {"ticker": "SHUL4.SA", "name": "Schulz", "sector": "Máquinas & Equipamentos"},
    {"ticker": "ROMI3.SA", "name": "Industrias Romi", "sector": "Máquinas & Equipamentos"},
    {"ticker": "KEPL3.SA", "name": "Kepler Weber", "sector": "Máquinas & Equipamentos"},
    {"ticker": "DXCO3.SA", "name": "Dexco", "sector": "Indústria"},
    {"ticker": "TASA4.SA", "name": "Taurus Armas", "sector": "Indústria"},

    # ── 6. Construção Civil & Real Estate ──
    {"ticker": "CYRE3.SA", "name": "Cyrela", "sector": "Construção & Real Estate"},
    {"ticker": "EZTC3.SA", "name": "EZTec", "sector": "Construção & Real Estate"},
    {"ticker": "MRVE3.SA", "name": "MRV", "sector": "Construção & Real Estate"},
    {"ticker": "EVEN3.SA", "name": "Even", "sector": "Construção & Real Estate"},
    {"ticker": "DIRR3.SA", "name": "Direcional", "sector": "Construção & Real Estate"},
    {"ticker": "TEND3.SA", "name": "Tenda", "sector": "Construção & Real Estate"},
    {"ticker": "CURY3.SA", "name": "Cury", "sector": "Construção & Real Estate"},
    {"ticker": "PLPL3.SA", "name": "Plano&Plano", "sector": "Construção & Real Estate"},
    {"ticker": "ALSO3.SA", "name": "Allos", "sector": "Real Estate / Shopping"},
    {"ticker": "MULT3.SA", "name": "Multiplan", "sector": "Real Estate / Shopping"},
    {"ticker": "IGTI11.SA", "name": "Iguatemi", "sector": "Real Estate / Shopping"},

    # ── 7. Tecnologia, Telecom & Educação ──
    {"ticker": "VIVT3.SA", "name": "Telefonica Brasil", "sector": "Telecomunicações"},
    {"ticker": "TIMS3.SA", "name": "TIM", "sector": "Telecomunicações"},
    {"ticker": "TOTS3.SA", "name": "TOTVS", "sector": "Tecnologia"},
    {"ticker": "LWSA3.SA", "name": "Locaweb", "sector": "Tecnologia"},
    {"ticker": "CASH3.SA", "name": "Méliuz", "sector": "Tecnologia"},
    {"ticker": "POSI3.SA", "name": "Positivo", "sector": "Tecnologia"},
    {"ticker": "INTB3.SA", "name": "Intelbras", "sector": "Tecnologia"},
    {"ticker": "YDUQ3.SA", "name": "YDUQS", "sector": "Educação"},
    {"ticker": "COGN3.SA", "name": "Cogna", "sector": "Educação"},
    {"ticker": "ANIM3.SA", "name": "Anima", "sector": "Educação"},
    {"ticker": "SEER3.SA", "name": "Ser Educacional", "sector": "Educação"},
    {"ticker": "GPSI3.SA", "name": "Grupo GPS", "sector": "Serviços"},
]

# Assertions de integridade do universo candidato
_all_tickers = [item["ticker"] for item in CANDIDATE_TICKERS]
assert len(_all_tickers) == len(set(_all_tickers)), f"ERRO: Tickers duplicados no universo candidato: {[t for t in _all_tickers if _all_tickers.count(t) > 1]}"


def get_candidate_tickers() -> list:
    """Retorna a lista de tickers strings do universo candidato."""
    return [item["ticker"] for item in CANDIDATE_TICKERS]


def get_candidate_dict() -> dict:
    """Retorna um dicionário indexado por ticker contendo metadados."""
    return {item["ticker"]: item for item in CANDIDATE_TICKERS}
