# 📈 Bico de Pato — Desconexão Operacional e Compressão de Múltiplos na B3

Script em Python que testa, de forma empírica e sem forçar o resultado, a tese do **"Bico de Pato"**:

Empresas não-financeiras da B3 cresceram operacionalmente (EBITDA LTM) enquanto o mercado comprimiu o múltiplo (EV/EBITDA), em um ambiente de juros reais mais altos (NTN-B IPCA+).

A hipótese **não é assumida como verdadeira**. O código classifica o resultado de forma objetiva:

- `CONFIRMADA`
- `PARCIALMENTE CONFIRMADA`
- `NÃO CONFIRMADA`
- `DADOS INSUFFICIENTES`

No estado atual (período Jan/2021 → Jul/2026, amostra efetiva ~86 empresas de um universo candidato de ~102), a classificação saiu **PARCIALMENTE CONFIRMADA**. Tem direção (EBITDA sobe, múltiplo cai), correlação negativa significante e evidência descritiva, mas difusão, teste binomial e persistência temporal não passam em todos os critérios de robustez.

![Bico de Pato Dashboard](bico_de_pato_dashboard.png)

---

## O que o dashboard mostra

Ao rodar o script ele gera `bico_de_pato_dashboard.png` (o arquivo que importa) e tenta abrir uma janela interativa com `plt.show()`.

**Aviso importante:** a janela interativa costuma espremer os gráficos e fazer legendas/anotações se sobreporem. Ignore a visualização aberta. Olhe só a imagem PNG gerada — ela é o dashboard oficial, com layout controlado (18×28, dark).

O dashboard atual tem vários painéis:

- **Header (KPIs)** — EBITDA LTM Index, EV/EBITDA mediano, NTN-B, spread e status da hipótese
- **Painel A** — Fundamentos operacionais (EBITDA LTM base 100) + decomposição setorial
- **Painel B** — O “Bico de Pato” (EBITDA ↑ vs EV/EBITDA ↓ + faixa interquartil)
- **Painel C** — Taxa real (NTN-B) vs yields (EBITDA Yield e Earnings Yield)
- **Painel D** — Robustez por amostra (Todas / Ex-PETR4/VALE3 / Ex-commodities)
- **Painel E** — Difusão do Bico por subamostra (N, K e IC Wilson)
- **Painel F** — Persistência temporal (proporção de empresas em Bico ao longo do tempo)
- **Painel G** — Scatter Δ EBITDA vs Δ EV/EBITDA (com quadrante Bico de Pato)
- **Painel H** — Decomposição do EV (ΔEBITDA, ΔEV, ΔMCap, ΔNetDebt)

---

## Por que o código é assim (regras de integridade)

Nada de “ajustar premissa pra ficar bonito no gráfico”.

1. **Zero preços sintéticos**  
   Se o yfinance não entregar cotação real, a empresa vira `PRICE_DATA_INSUFFICIENT` e sai da amostra. Sem inventar preço a partir do Ibovespa.

2. **Limitações honestas do yfinance gratuito**  
   - EBITDA LTM trimestral só funciona bem nos últimos 4–5 trimestres. Antes disso usa anual ou fallback hardcoded auditado.  
   - Não tem `announcement_date` oficial da CVM → `publication_date` são estimativas (~75 dias após o fim do período).

3. **Point-in-Time / Look-Ahead Bias**  
   Cada dado fundamental carrega `publication_date` estimada. Em uma data de observação T só entram dados com `publication_date <= T`.  
   - Dados sem data clara recebem `lookahead_flag = UNKNOWN`  
   - Observações com risco de look-ahead são tratadas à parte  
   - O arquivo `lookahead_audit.csv` permite auditar observação por observação  
   - Os dados hardcoded originais são preservados — só ganham metadados temporais

4. **Sem extrapolação cega**  
   NTN-B, Ibovespa e preços só usam datas em que realmente existem observações. O período da análise é a interseção comum.

5. **Sem filtro arbitrário de múltiplo**  
   EV/EBITDA > 100x não é jogado fora. Os dados ficam raw; a robustez vem da mediana + P25/P75.

6. **Mediana + Agregado econômico**  
   Mediana evita distorção de outliers. Agregado (`ΣEV / ΣEBITDA`) respeita o peso econômico real.

7. **Assertions matemáticas**  
   Antes de plotar, o script confere:
   - `EV ≈ Market Cap + Net Debt`
   - `EV/EBITDA ≈ EV / EBITDA`  
   Se falhar, aborta.

---

## Rigor estatístico

Além do alinhamento temporal Point-in-Time, o módulo `bico_stats.py` roda:

- Intervalo de confiança (bootstrap / reamostragem)
- Teste binomial exato de difusão (H₀: p = 0,5)
- Correlação Spearman / Pearson entre ΔEBITDA e ΔEV/EBITDA
- Regressão simples e regressão controlada por NTN-B
- Persistência temporal e streaks
- Evidence Scorecard com critérios pass/fail
- Relatório completo em `bico_de_pato_statistical_report.txt`

Tudo isso alimenta a classificação final da hipótese de forma transparente.

---

## Arquivos gerados

O script gera (entre outros):

- `bico_de_pato_dashboard.png` — dashboard oficial
- `bico_de_pato_company_metrics.csv`
- `bico_de_pato_sector_metrics.csv`
- `bico_de_pato_summary.csv`
- `bico_de_pato_data_quality.csv`
- `bico_de_pato_raw_data.csv`
- `bico_de_pato_bico_diffusion.csv`
- `bico_de_pato_macro_correlation.csv`
- `bico_de_pato_sample_comparison.csv`
- `lookahead_audit.csv` — trilha Point-in-Time
- `included_companies.csv` / `excluded_companies.csv`
- `collection_errors.csv`
- `sample_audit.csv`
- `bico_de_pato_statistical_report.txt` — relatório de inferência estatística

(Os CSVs estão no `.gitignore` por padrão, então não sobem no repositório.)

---

## Como rodar

```bash
pip install pandas numpy yfinance matplotlib scipy statsmodels pytest
python script.py
```

Ele baixa preços reais, alinha fundamentos com correção Point-in-Time, valida, imprime o relatório no terminal, salva o PNG, os CSVs e o relatório estatístico.

**Lembrete de novo:** a janela que abre com `plt.show()` pode ficar espremida e com legenda por cima do gráfico. Use só a imagem `bico_de_pato_dashboard.png`.

### Testes automatizados

```bash
pytest -v
```

---

## Estrutura de módulos

```text
script.py              # Pipeline principal — coleta, cálculo, amostragem e dashboard
candidate_universe.py  # Universo candidato (~100+ empresas não-financeiras da B3)
point_in_time.py       # Framework Point-in-Time (FundamentalRecord, FundamentalStore)
publication_dates.py   # Estimativas de publication_date
bico_stats.py          # Bootstrap, teste binomial, regressões, persistência, scorecard
test_point_in_time.py  # Testes de integridade PIT
test_methodology.py    # Testes de metodologia e amostras
test_expansion.py      # Testes de expansão de amostra e auditoria
```

---

## Universo

Começa com um universo candidato de ~100+ empresas não-financeiras da B3 (sem bancos, seguradoras etc.). Depois da coleta e dos filtros de qualidade, a amostra efetiva fica em torno de 86 empresas.  
As 20 originais do estudo continuam preservadas e servem de referência:

- **Commodities (fora da amostra primária):** PETR4, VALE3
- **Utilidades:** ELET3, EQTL3, CPLE6, SBSP3, EGIE3
- **Consumo / Varejo / Saúde:** ABEV3, MGLU3, LREN3, RADL3, HAPV3
- **Bens de Capital & Transporte:** WEGE3, RENT3, RAIL3, EMBR3
- **Materiais & Alimentos (ex-líderes):** GGBR4, CSNA3, SUZB3, JBSS3

---

## Licença

Aberto para estudo de valuation, séries temporais e quant da B3. Use, critique, fork.

---

## Quer que uma IA explique o repo?

Clique em qualquer botão abaixo para abrir a IA com o link do repositório ([https://github.com/Gabrzz/bico-de-pato](https://github.com/Gabrzz/bico-de-pato)):

<p align="center">
  <a href="https://claude.ai/new?q=Explique%20o%20reposit%C3%B3rio%20https%3A%2F%2Fgithub.com%2FGabrzz%2Fbico-de-pato" target="_blank">
    <img src="https://img.shields.io/badge/Claude-Explicar%20o%20repo-FF6B35?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude">
  </a>
  <a href="https://chatgpt.com/?q=Explique%20o%20reposit%C3%B3rio%20https%3A%2F%2Fgithub.com%2FGabrzz%2Fbico-de-pato" target="_blank">
    <img src="https://img.shields.io/badge/ChatGPT-Explicar%20o%20repo-10A37F?style=for-the-badge&logo=openai&logoColor=white" alt="ChatGPT">
  </a>
  <a href="https://gemini.google.com/app?q=Explique%20o%20reposit%C3%B3rio%20https%3A%2F%2Fgithub.com%2FGabrzz%2Fbico-de-pato" target="_blank">
    <img src="https://img.shields.io/badge/Gemini-Explicar%20o%20repo-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini">
  </a>
  <a href="https://chat.deepseek.com/?q=Explique%20o%20reposit%C3%B3rio%20https%3A%2F%2Fgithub.com%2FGabrzz%2Fbico-de-pato" target="_blank">
    <img src="https://img.shields.io/badge/DeepSeek-Explicar%20o%20repo-4D6BFE?style=for-the-badge&logoColor=white" alt="DeepSeek">
  </a>
  <a href="https://www.kimi.com/?q=Explique%20o%20reposit%C3%B3rio%20https%3A%2F%2Fgithub.com%2FGabrzz%2Fbico-de-pato" target="_blank">
    <img src="https://img.shields.io/badge/Kimi-Explicar%20o%20repo-000000?style=for-the-badge&logoColor=white" alt="Kimi">
  </a>
</p>


