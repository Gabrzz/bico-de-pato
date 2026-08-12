# 📈 Bico de Pato — Teste Empírico de Desconexão Operacional na B3

![Bico de Pato Dashboard](bico_de_pato_dashboard.png)

Script em Python que testa, sem forçar resultado, a tese do **"Bico de Pato"**: empresas não-financeiras da B3 cresceram operacionalmente (EBITDA LTM) enquanto o mercado comprimiu o múltiplo (EV/EBITDA), num cenário de juros reais mais altos (NTN-B IPCA+).

A hipótese **não é assumida como verdadeira**. O código classifica de forma objetiva e auditável:

- `CONFIRMADA`
- `PARCIALMENTE CONFIRMADA`
- `NÃO CONFIRMADA`
- `DADOS INSUFFICIENTES`

---

## O que o dashboard mostra (18×28, dark)

Ao rodar o script ele gera `bico_de_pato_dashboard.png` (o arquivo que realmente importa) e tenta abrir uma janela interativa com `plt.show()`.

**Aviso importante:** a janela interativa costuma espremer os gráficos e fazer legendas/anotações se sobreporem. Ignore a visualização aberta. Olhe só a imagem PNG gerada — ela é o dashboard oficial, com layout controlado.

### Header (KPIs no topo)
Números da amostra primária (Ex-PETR4/VALE3): variação do EBITDA LTM Index, EV/EBITDA mediano, NTN-B 10Y, spread EBITDA Yield vs NTN-B e a classificação final da hipótese.

### Painel A — Fundamentos operacionais
EBITDA LTM Index (base 100 = jan/2021):
- Ciano grosso → mediana das 18 empresas ex-PETR4/VALE3
- Verde → mediana das 20 empresas
- Vermelho tracejado → Ibovespa
- Pontilhados por setor → Utilidades, Bens de Capital/Transporte, Consumo/Varejo/Saúde, Materiais/Alimentos

Card com crescimento setorial e % de empresas que subiram EBITDA desde jan/2021.

### Painel B — O “Bico de Pato”
Eixo esquerdo (verde): EBITDA LTM Index  
Eixo direito (âmbar): EV/EBITDA mediano + faixa interquartil (P25–P75)  

Box de decomposição: crescimento de EBITDA, EV, Market Cap, Dívida Líquida e a **difusão do Bico** (% de empresas que simultaneamente tiveram EBITDA ↑ e múltiplo ↓).

### Painel C — Taxa real vs yields
- Roxo → NTN-B IPCA+ 10 anos
- Ciano → EBITDA Yield (EBITDA/EV)
- Verde pontilhado → Earnings Yield (Lucro/MCap)

Sem chamar de WACC ou custo de capital. Só comparação visual de yields.

### Painel D — Robustez por amostra
Três barras lado a lado:
1. Todas (20)
2. Ex-PETR4/VALE3 (18) ← amostra principal
3. Ex-commodities amplo (14)

---

## Por que o código é assim (regras de integridade)

Nada de “ajustar premissa pra ficar bonito”.

1. **Zero preços sintéticos**  
   Se o yfinance não entregar cotação real, a empresa vira `PRICE_DATA_INSUFFICIENT` e sai da amostra. Sem inventar preço a partir do Ibovespa.

2. **Limitações honestas do yfinance gratuito**  
   - EBITDA LTM trimestral só funciona bem nos últimos 4–5 trimestres. Antes disso usa anual ou fallback hardcoded auditado.  
   - Não tem `announcement_date` da CVM → publication_dates são estimativas (~75 dias após period_end_date).

3. **Point-in-Time / Look-Ahead Bias Correction**  
   Cada dado fundamental possui `publication_date` estimada. O cálculo de EV/EBITDA em uma data T só usa dados com `publication_date <= T`.  
   - Dados sem `publication_date` recebem `lookahead_flag = UNKNOWN`  
   - Observações com risco de look-ahead são excluídas da análise principal  
   - O arquivo `lookahead_audit.csv` permite verificação manual de cada observação  
   - Os dados hardcoded originais são **preservados** — apenas recebem metadados temporais

4. **Sem extrapolação cega**  
   NTN-B, Ibovespa e preços só usam datas em que realmente existem dados. O período da análise é a interseção comum.

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

## Os CSVs de auditoria

O script sempre gera:

1. `bico_de_pato_company_metrics.csv` — crescimento e flag `Bico_de_Pato` por empresa  
2. `bico_de_pato_sector_metrics.csv` — por setor  
3. `bico_de_pato_summary.csv` — resumo executivo + classificação final + metodologia PIT  
4. `bico_de_pato_data_quality.csv` — fontes, Look-Ahead Risk, PIT summary, EV negativo  
5. `bico_de_pato_raw_data.csv` — séries mensais completas (inclui `Lookahead_Flag` por ticker)  
6. `bico_de_pato_bico_diffusion.csv` — % de empresas com EBITDA↑, múltiplo↓ e Bico ao longo do tempo  
7. `bico_de_pato_macro_correlation.csv` — correlação NTN-B vs yields/múltiplos  
8. `bico_de_pato_sample_comparison.csv` — comparativo das 3 amostras  
9. `lookahead_audit.csv` — **trilha de auditoria Point-in-Time** com `ticker`, `observation_date`, `metric`, `period_end_date`, `publication_date`, `value`, `source`, `data_source_type`, `lookahead_flag`  
10. `included_companies.csv` — empresas candidatas aprovadas na amostragem efetiva (`ticker`, `company_name`, `sector`, `status`)  
11. `excluded_companies.csv` — empresas descartadas por insuficiência de dados (`ticker`, `company_name`, `sector`, `status`, `exclusion_reason`, `details`)  
12. `collection_errors.csv` — registro de exceções durante a coleta do yfinance (`ticker`, `stage`, `error_type`, `error_message`, `timestamp`)  
13. `sample_audit.csv` — trilha unificada de auditoria da amostragem (`ticker`, `company_name`, `sector`, `candidate`, `included`, `exclusion_reason`, `data_quality`)  
14. `bico_de_pato_statistical_report.txt` — **relatório de inferência estatística** com Intervalo de Confiança Bootstrap (95%), p-valores do Teste Binomial, Teste t pareado e teste ADF de estacionariedade

---

## Rigor Estatístico & Validação de Hipótese

Além do alinhamento temporal Point-in-Time, o repositório inclui módulo dedicado de inferência estatística (`bico_stats.py`):

- **Intervalo de Confiança Bootstrap (95%)**: Estimativa não-paramétrica por reamostragem (10.000 iterações) para a variação mediana do EBITDA, compressão de EV/EBITDA e difusão do Bico de Pato.
- **Teste Binomial de Difusão**: Avaliação de significância da proporção de empresas com o padrão Bico de Pato simultâneo versus o acaso ($H_0: p = 0.5$).
- **Teste t Pareado**: Teste de hipótese para alteração média dos múltiplos e fundamentos operacionais pré e pós período.
- **Teste ADF (Augmented Dickey-Fuller)**: Verificação de estacionariedade e ordenamento estatístico das séries temporais para evitar falsas correlações.

---

## Como rodar

```bash
pip install pandas numpy yfinance matplotlib scipy statsmodels pytest
python script.py
```

Ele baixa preços reais, alinha fundamentos (com correção Point-in-Time), valida, imprime o relatório no terminal, salva o PNG, os CSVs e o relatório estatístico.  
Lembrete de novo: a janela que abre com `plt.show()` pode ficar espremida e com legenda por cima do gráfico. Use só a imagem `bico_de_pato_dashboard.png`.

### Executar a suíte de testes automatizados:

```bash
pytest -v
```

---

## Estrutura de módulos

```
script.py              # Pipeline principal — orquestra coleta, cálculo, amostragem e dashboard
candidate_universe.py  # Universo candidato com 100+ empresas não-financeiras da B3
point_in_time.py       # Framework Point-in-Time: FundamentalRecord, FundamentalStore
publication_dates.py   # Mapeamento de publication_date estimadas
bico_stats.py          # Módulo estatístico: Bootstrap CI 95%, Teste Binomial, Teste t pareado, ADF
test_point_in_time.py  # 6 testes automatizados de integridade PIT
test_methodology.py    # Testes automatizados da metodologia e amostras
test_expansion.py      # Testes automatizados da expansão de amostra e auditoria
```

---

## Universo (20 empresas não-financeiras)

Commodities (fora da amostra primária): PETR4, VALE3
Utilidades: ELET3, EQTL3, CPLE6, SBSP3, EGIE3
Consumo / Varejo / Saúde: ABEV3, MGLU3, LREN3, RADL3, HAPV3
Bens de Capital & Transporte: WEGE3, RENT3, RAIL3, EMBR3
Materiais & Alimentos (ex-líderes): GGBR4, CSNA3, SUZB3, JBSS3

---

## Licença

Aberto para estudo de valuation, séries temporais e quant da B3. Use, critique, fork.

---

## Quer que uma IA explique o repo?

Clique em qualquer botão abaixo para abrir a IA com o link do repositório (`https://github.com/Gabrzz/bico-de-pato`):

<p align="left">
  <a href="https://claude.ai/new?q=Explique+o+reposit%C3%B3rio+https%3A%2F%2Fgithub.com%2FGabrzz%2Fbico-de-pato" target="_blank">
    <img src="https://img.shields.io/badge/Claude-Explicar%20o%20repo-FF6B35?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude">
  </a>
  <a href="https://chatgpt.com/?q=Explique+o+reposit%C3%B3rio+https%3A%2F%2Fgithub.com%2FGabrzz%2Fbico-de-pato" target="_blank">
    <img src="https://img.shields.io/badge/ChatGPT-Explicar%20o%20repo-10A37F?style=for-the-badge&logo=openai&logoColor=white" alt="ChatGPT">
  </a>
  <a href="https://gemini.google.com/app" target="_blank">
    <img src="https://img.shields.io/badge/Gemini-Explicar%20o%20repo-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini">
  </a>
  <a href="https://chat.deepseek.com/" target="_blank">
    <img src="https://img.shields.io/badge/DeepSeek-Explicar%20o%20repo-4D6BFE?style=for-the-badge&logoColor=white" alt="DeepSeek">
  </a>
  <a href="https://kimi.moonshot.cn/" target="_blank">
    <img src="https://img.shields.io/badge/Kimi-Explicar%20o%20repo-000000?style=for-the-badge&logoColor=white" alt="Kimi">
  </a>
</p>