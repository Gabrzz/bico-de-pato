# 📈 Bico de Pato — Dashboard de Valuation e Desconexão Operacional B3

Este repositório contém o script em Python para análise fundamentalista e quantitativa da tese de **Compressão de Múltiplos e Desconexão Operacional ("Efeito Bico de Pato")** nas empresas listadas na B3 (Bolsa Brasileira).

---

## 💡 A Tese de Investimento

O termo **"Bico de Pato"** refere-se ao fenômeno visual e financeiro onde:
1. **Curva Operacional (EBITDA LTM acumulado):** Mantém trajetória ascendente ou resiliente, refletindo crescimento de lucros e caixa operacional.
2. **Curva de Preços (Ibovespa / Cotações):** Sofre forte desvalorização ou estagnação devido a fatores macroeconômicos (juros altos, risco fiscal).

A divergência entre o fundamento operacional crescente e a cotação cadente abre o "bico do pato", indicando uma oportunidade de **compressão de múltiplos (EV/EBITDA descontado)** e **Earnings Yield atrativo em relação às taxas reais de juros (NTN-B 10Y)**.

---

## 📊 Principais Recursos do Script

- **Universo de 20 Empresas Não-Financeiras da B3:** Divididas entre líderes de commodities (`PETR4`, `VALE3`) e cestas de ex-commodities (`WEGE3`, `RENT3`, `EGIE3`, `ABEV3`, `EQTL3`, `LREN3`, `RADL3`, `SBSP3`, `EMBR3`, etc.).
- **Coleta e Ajustes Dinâmicos:** 
  - Cálculo do número de ações em circulação (*Shares Outstanding*) dinâmico com séries históricas via `yfinance` (com fallbacks e retries).
  - Cálculo de EV (Enterprise Value) = *Market Cap* + Dívida Líquida.
- **Painéis do Dashboard:**
  - **Painel Superior:** Comparativo de evolução do EBITDA Consolidado Ex-Commodities vs. Ibovespa com overlays de taxas de juros reais (NTN-B 10Y).
  - **Painel Inferior:** Análise de múltiplos históricos (EV/EBITDA), Earnings Yield vs NTN-B e estatísticas de difusão da tese de descolamento operacional.
- **Saída Gráfica:** Gera automaticamente o dashboard visual em alta resolução (`bico_de_pato_top25_b3.png`).

---

## 🛠️ Pré-requisitos e Instalação

### Requisitos Python
Certifique-se de ter o Python 3.9+ instalado. Instale as bibliotecas necessárias com:

```bash
pip install pandas yfinance matplotlib
```

---

## 🚀 Como Executar

Execute o script diretamente pelo terminal:

```bash
python script.py
```

O script irá coletar as cotações históricas, alinhar as demonstrações financeiras e gerar o arquivo de imagem `bico_de_pato_top25_b3.png` na raiz do projeto.

---

## 📁 Estrutura do Repositório

```text
.
├── script.py         # Código-fonte principal da análise e geração do dashboard
└── README.md         # Documentação completa do projeto
```

---

## 📝 Licença

Este projeto é disponibilizado para fins educacionais e de estudo sobre análise quantitativa e fundamentalista do mercado de ações brasileiro (B3).
