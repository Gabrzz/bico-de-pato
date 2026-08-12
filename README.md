# 📈 Bico de Pato — Teste Empírico de Desconexão Operacional na B3

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
   - Não tem `announcement_date` da CVM → períodos anuais ficam marcados com `LOOK_AHEAD_RISK = TRUE` no CSV de qualidade.

3. **Sem extrapolação cega**  
   NTN-B, Ibovespa e preços só usam datas em que realmente existem dados. O período da análise é a interseção comum.

4. **Sem filtro arbitrário de múltiplo**  
   EV/EBITDA > 100x não é jogado fora. Os dados ficam raw; a robustez vem da mediana + P25/P75.

5. **Mediana + Agregado econômico**  
   Mediana evita distorção de outliers. Agregado (`ΣEV / ΣEBITDA`) respeita o peso econômico real.

6. **Assertions matemáticas**  
   Antes de plotar, o script confere:
   - `EV ≈ Market Cap + Net Debt`
   - `EV/EBITDA ≈ EV / EBITDA`  
   Se falhar, aborta.

---

## Os 8 CSVs de auditoria

O script sempre gera:

1. `bico_de_pato_company_metrics.csv` — crescimento e flag `Bico_de_Pato` por empresa  
2. `bico_de_pato_sector_metrics.csv` — por setor  
3. `bico_de_pato_summary.csv` — resumo executivo + classificação final  
4. `bico_de_pato_data_quality.csv` — fontes, Look-Ahead Risk, EV negativo  
5. `bico_de_pato_raw_data.csv` — séries mensais completas  
6. `bico_de_pato_bico_diffusion.csv` — % de empresas com EBITDA↑, múltiplo↓ e Bico ao longo do tempo  
7. `bico_de_pato_macro_correlation.csv` — correlação NTN-B vs yields/múltiplos  
8. `bico_de_pato_sample_comparison.csv` — comparativo das 3 amostras

---

## Como rodar

```bash
pip install pandas numpy yfinance matplotlib
python script.py
```

Ele baixa preços reais, alinha fundamentos, valida, imprime o relatório no terminal, salva o PNG e os 8 CSVs.
Lembrete de novo: a janela que abre com plt.show() pode ficar espremida e com legenda por cima do gráfico. Use só a imagem bico_de_pato_dashboard.png.

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

Clique em qualquer uma. O prompt já vem pronto pedindo pra ler o README e o código. Depois é só perguntar o que quiser.

```
    <img src="https://img.shields.io/badge/Claude-Explicar%20o%20repo-FF6B35?style=for-the-badge&#x26;logo=anthropic&#x26;logoColor=white" alt="Claude">
  
   
  
    <img src="https://img.shields.io/badge/ChatGPT-Explicar%20o%20repo-10A37F?style=for-the-badge&#x26;logo=openai&#x26;logoColor=white" alt="ChatGPT">
  
   
  
    <img src="https://img.shields.io/badge/Gemini-Explicar%20o%20repo-4285F4?style=for-the-badge&#x26;logo=google&#x26;logoColor=white" alt="Gemini">
  


  
    <img src="https://img.shields.io/badge/DeepSeek-Explicar%20o%20repo-4D6BFE?style=for-the-badge&#x26;logoColor=white" alt="DeepSeek">
  
   
  
    <img src="https://img.shields.io/badge/Kimi-Explicar%20o%20repo-000000?style=for-the-badge&#x26;logoColor=white" alt="Kimi">
  

```