# 📈 Bico de Pato — Dashboard de Valuation e Desconexão Operacional B3

Este repositório contém o script em Python para análise fundamentalista e quantitativa da tese de **Compressão de Múltiplos e Desconexão Operacional ("Efeito Bico de Pato")** nas empresas listadas na B3 (Bolsa Brasileira).

![Dashboard Bico de Pato - B3 Top 20](bico_de_pato_top20_b3.png)

---

## 🖼️ Descrição do Dashboard

O gráfico gerado (`bico_de_pato_top20_b3.png`) é composto por dois painéis principais de análise:

### 1. Painel Superior — Desconexão Operacional vs. Preço (Efeito "Bico de Pato")
- **Curva Verde (EBITDA LTM Consolidado Ex-Commodities):** Mostra a evolução acumulada do resultado operacional das 20 empresas selecionadas da B3 (rebased = 100 em Jan/2021). Revela um crescimento operacional consistente e resiliente da economia real.
- **Curva Azul (Ibovespa / Cotação Relativa):** Representa a performance do índice Ibovespa no mesmo período.
- **Área de Sombreamento ("Bico de Pato"):** Destaca visualmente o descolamento onde o desempenho operacional sobe enquanto o mercado precifica os ativos para baixo, criando uma nítida janela de compressão de múltiplos.
- **Linha Vermelha Tracejada (Taxa Real NTN-B 10Y):** Ilustra o impacto da elevação dos juros reais no Brasil sobre a precificação dos ativos de risco.

### 2. Painel Inferior — Múltiplos de Valuation e Métricas Complementares
- **EV/EBITDA Médio Consolidado:** Mede a evolução do múltiplo de firma ao longo do tempo, evidenciando o desconto atual frente às médias históricas.
- **Earnings Yield vs. NTN-B:** Compara o retorno de lucros da carteira de ações contra a taxa de juros real livre de risco.
- **Métrica de Difusão da Tese:** Mede a porcentagem exata de empresas do universo analisado que confirmam individualmente o padrão de descolamento operacional.

---

## 💡 A Tese de Investimento

O termo **"Bico de Pato"** refere-se ao fenômeno visual e financeiro onde:
1. **Curva Operacional (EBITDA LTM acumulado):** Mantém trajetória ascendente ou resiliente, refletindo crescimento de lucros e caixa operacional.
2. **Curva de Preços (Ibovespa / Cotações):** Sofre forte desvalorização ou estagnação devido a fatores macroeconômicos (juros altos, risco fiscal).

A divergência entre o fundamento operacional crescente e a cotação cadente abre o "bico do pato", indicando uma oportunidade de **compressão de múltiplos (EV/EBITDA descontado)** e **Earnings Yield atrativo em relação às taxas reais de juros (NTN-B 10Y)**.

---

## 📊 Universo de Amostra (20 Empresas B3)

O script analisa 20 grandes empresas não-financeiras brasileiras divididas nos seguintes setores:
- **Commodities & Materiais (Líderes):** `PETR4`, `VALE3`
- **Utilidades Públicas (Energia & Saneamento):** `ELET3`, `EQTL3`, `CPLE6`, `SBSP3`, `EGIE3`
- **Consumo, Varejo & Saúde:** `ABEV3`, `MGLU3`, `LREN3`, `RADL3`, `HAPV3`
- **Bens de Capital & Transporte:** `WEGE3`, `RENT3`, `RAIL3`, `EMBR3`
- **Materiais Ex-Líderes:** `GGBR4`, `CSNA3`, `SUZB3`, `JBSS3`

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

O script irá coletar as cotações históricas via `yfinance`, calcular os demonstrativos alinhados e salvar a imagem `bico_de_pato_top20_b3.png` na raiz do projeto.

---

## 📁 Estrutura do Repositório

```text
.
├── script.py                 # Código-fonte principal da análise e geração do dashboard
├── bico_de_pato_top20_b3.png # Dashboard visual gerado em alta resolução
└── README.md                 # Documentação completa do projeto
```

---

## 📝 Licença

Este projeto é disponibilizado para fins educacionais e de estudo sobre análise quantitativa e fundamentalista do mercado de ações brasileiro (B3).
