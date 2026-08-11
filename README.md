# 📈 Bico de Pato — Dashboard de Valuation e Desconexão Operacional B3

Este repositório contém o script em Python para análise fundamentalista e quantitativa da tese de **Compressão de Múltiplos e Desconexão Operacional ("Efeito Bico de Pato")** nas empresas listadas na B3 (Bolsa Brasileira).

![Dashboard Bico de Pato - B3 Top 20](bico_de_pato_top20_b3.png)

---

## 🖼️ Descrição do Dashboard

O gráfico gerado (`bico_de_pato_top20_b3.png`) é composto por **três painéis** empilhados, compartilhando o mesmo eixo temporal (Jan/2021 até a data mais recente disponível).

### Painel A — Desconexão Operacional vs. Ibovespa (Efeito "Bico de Pato")

- **Curva Verde (EBITDA LTM Consolidado — Amostra Total):** evolução acumulada do resultado operacional das 20 empresas selecionadas da B3 (rebased = 100 em Jan/2021), incluindo os líderes de commodities (PETR4 e VALE3).
- **Curva Ciano/Teal (EBITDA LTM Consolidado — Ex-Commodities):** mesma lógica, mas excluindo PETR4 e VALE3. É a curva central da tese, plotada com maior destaque (linha mais espessa).
- **Curva Vermelha Tracejada (Ibovespa):** performance do índice Ibovespa (preço) no mesmo período.
- **Área de Sombreamento ("Bico de Pato"):** destaca visualmente o descolamento entre a curva EBITDA Ex-Commodities e o Ibovespa — a "abertura do bico" quando o operacional sobe e o preço não acompanha.
- **Linhas Pontilhadas Setoriais:** quatro curvas adicionais (mais finas e translúcidas) mostram a decomposição do EBITDA Ex-Commodities por setor — Utilidades Públicas, Bens de Capital & Transporte, Consumo/Varejo/Saúde e Materiais/Alimentos Ex-Líderes — permitindo ver quais setores puxam o movimento agregado.
- **Card de Texto:** resume a variação percentual acumulada de cada setor no período e a métrica de Difusão da Tese (ver abaixo).

### Painel B — Múltiplo EV/EBITDA Real (Mediano, Ex-Commodities)

- **Linha Âmbar:** EV/EBITDA **mediano** real (Enterprise Value = Market Cap + Dívida Líquida, sobre EBITDA LTM), calculado apenas sobre as empresas **ex-commodities**.
- **Faixa Sombreada (P25–P75):** intervalo interquartil da amostra, mostrando a dispersão dos múltiplos individuais em torno da mediana.
- **Linha Cinza Pontilhada:** média do múltiplo mediano ao longo de todo o período, como referência histórica.
- **Anotação:** compara o múltiplo no início e no fim da série, evidenciando a compressão (ou expansão) real do valuation.

### Painel C — Custo de Capital: Juros Reais vs. Yields da Bolsa

- **Linha Roxa (eixo esquerdo):** Taxa Real NTN-B 10 anos (IPCA+), representando o custo de oportunidade livre de risco no Brasil.
- **Linha Ciano Traço-Ponto (eixo direito):** EBITDA Yield Implícito Mediano (EBITDA / EV), ex-commodities.
- **Linha Verde Pontilhada (eixo direito):** Earnings Yield Implícito Mediano — 1 / (P/L), ex-commodities.

Este painel é o núcleo da comparação "renda fixa real vs. renda variável": quando os yields implícitos da bolsa se aproximam ou ficam abaixo da NTN-B, o prêmio de risco embutido nas ações fica historicamente comprimido.

---

## 💡 A Tese de Investimento

O termo **"Bico de Pato"** refere-se ao fenômeno visual e financeiro onde:

1. **Curva Operacional (EBITDA LTM acumulado, ex-commodities):** mantém trajetória ascendente ou resiliente, refletindo crescimento de lucros e caixa operacional.
2. **Curva de Preços (Ibovespa):** sofre forte desvalorização ou estagnação, geralmente por fatores macroeconômicos (juros reais altos, risco fiscal).

A divergência entre o fundamento operacional crescente e a cotação cadente abre o "bico do pato" no Painel A, indicando uma possível oportunidade de **compressão de múltiplos (EV/EBITDA descontado, Painel B)** e de **Earnings/EBITDA Yield atrativo frente à taxa real livre de risco (NTN-B 10Y, Painel C)**.

> ⚠️ **Escopo importante:** os múltiplos, yields e a métrica de difusão (Painéis B e C, e a decomposição setorial do Painel A) são calculados **apenas sobre as 18 empresas ex-commodities** — PETR4 e VALE3 são deliberadamente excluídas dessas contas por terem dinâmica de EBITDA muito mais atrelada a preços de commodities globais do que ao ciclo doméstico. Elas aparecem apenas na curva "EBITDA LTM Consolidado — Amostra Total" do Painel A.

### Métrica de Difusão da Tese

Mede o percentual exato das 18 empresas ex-commodities cujo EBITDA LTM atual é maior do que o registrado em Jan/2021 — ou seja, quantas delas, individualmente, confirmam o padrão de crescimento operacional que sustenta a tese (e não apenas o agregado/mediana).

---

## 📊 Universo de Amostra (20 Empresas B3)

O script analisa 20 grandes empresas não financeiras brasileiras divididas nos seguintes grupos:

- **Commodities & Materiais (Líderes, excluídos dos múltiplos/yields):** `PETR4`, `VALE3`
- **Utilidades Públicas (Energia & Saneamento):** `ELET3`, `EQTL3`, `CPLE6`, `SBSP3`, `EGIE3`
- **Consumo, Varejo & Saúde:** `ABEV3`, `MGLU3`, `LREN3`, `RADL3`, `HAPV3`
- **Bens de Capital & Transporte:** `WEGE3`, `RENT3`, `RAIL3`, `EMBR3`
- **Materiais/Alimentos Ex-Líderes:** `GGBR4`, `CSNA3`, `SUZB3`, `JBSS3`

---

## 🗃️ Sobre os Dados Fundamentalistas (Hardcoded)

EBITDA LTM, Dívida Líquida, Lucro Líquido e a série de Taxa Real NTN-B 10Y **não são buscados dinamicamente via API** — estão hardcoded diretamente no script (`EBITDA_HARDCODED_BI`, `NET_DEBT_HARDCODED_BI`, `NET_INCOME_HARDCODED_BI`, `NTN_B_MONTHLY_DATA`).

Isso é uma escolha deliberada, não uma limitação esquecida: o ideal seria puxar esses dados de forma 100% variável via **BRAPI** e/ou **yfinance**, mas os endpoints fundamentalistas completos (demonstrativos financeiros históricos, dívida líquida, etc.) dessas bibliotecas exigem plano pago, que não está disponível no momento. Por isso, os valores foram coletados **manualmente** a partir de fontes públicas confiáveis — principalmente **AUVP Analítica** e **ZoneBourse** — e cruzados com os releases/demonstrativos das próprias companhias sempre que possível.

Implicações práticas de manter esses dados hardcoded:

- **Atualização manual:** os dicionários cobrem até `2025-12-31` (e a NTN-B até `2026-01-31`). Para manter o dashboard atual, é preciso adicionar novos pontos manualmente às fontes citadas conforme novos trimestres/anos forem divulgados.
- **Preços seguem "ao vivo":** apenas as cotações (via `yfinance`) e o número de ações em circulação (via `get_shares_full`/fallback) são buscados dinamicamente a cada execução. Isso significa que, para meses além do último ponto hardcoded, o script propaga (`ffill`) o último valor conhecido de EBITDA/Dívida/Lucro/NTN-B enquanto o preço de mercado continua se movendo normalmente — um efeito a ter em mente ao interpretar os meses mais recentes do gráfico.
- **Apenas Ações em circulação têm fallback interno no código** (`SHARES_OUTSTANDING_FALLBACK_BI`), usado somente se a busca dinâmica via `yfinance` falhar.

Se/quando o acesso a um plano pago de BRAPI ou yfinance for viabilizado, a recomendação é migrar esses quatro dicionários para chamadas de API, mantendo o hardcoded apenas como fallback de contingência (assim como já é feito hoje para preços e ações em circulação).

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

O script irá coletar as cotações históricas via `yfinance`, combiná-las com os dados fundamentalistas hardcoded (ver seção acima), calcular os múltiplos e yields, e salvar a imagem `bico_de_pato_top20_b3.png` na raiz do projeto.

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