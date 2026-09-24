
import streamlit as st
import os
import requests
import time
import pandas as pd
from google import genai

st.set_page_config(
    page_title="AI Financial Analyst",
    page_icon="📊",
    layout="wide"
)

# ==========================================
# CONFIGURAÇÃO
# ==========================================

# Credentials: environment variables in development,
# Streamlit Secrets in production.
EMAIL = os.getenv("SEC_EMAIL")

if not EMAIL:
    try:
        EMAIL = st.secrets["SEC_EMAIL"]
    except Exception:
        EMAIL = None

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    try:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    except Exception:
        GEMINI_API_KEY = None

if not EMAIL:
    raise RuntimeError(
        "SEC_EMAIL não configurado."
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY não configurada."
    )

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


TAGS_RECEITA = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet"
]

HEADERS = {
    "User-Agent": f"AI Financial Analyst {EMAIL}",
    "Accept-Encoding": "gzip, deflate"
}


# ==========================================
# CONSULTAS À SEC
# ==========================================

@st.cache_data(ttl=3600)
def consultar_json(url):

    resposta = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    resposta.raise_for_status()

    return resposta.json()


@st.cache_data(ttl=3600)
def carregar_sec(cik):

    cik = str(cik).zfill(10)

    submissions = consultar_json(
        f"https://data.sec.gov/submissions/CIK{cik}.json"
    )

    companyfacts = consultar_json(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    )

    return submissions, companyfacts


# ==========================================
# SELECIONAR 10-K
# ==========================================

def selecionar_10k(submissions):

    df = pd.DataFrame(
        submissions["filings"]["recent"]
    )

    df = df[
        df["form"] == "10-K"
    ].copy()

    if df.empty:
        raise ValueError(
            "Nenhum Form 10-K encontrado."
        )

    df["filingDate"] = pd.to_datetime(
        df["filingDate"]
    )

    df = df.sort_values(
        ["filingDate", "accessionNumber"],
        ascending=False
    )

    ultimo = df.iloc[0]

    if not ultimo["reportDate"]:
        raise ValueError(
            "10-K sem reportDate."
        )

    return {
        "accn": ultimo["accessionNumber"],
        "reportDate": ultimo["reportDate"],
        "filingDate": ultimo[
            "filingDate"
        ].strftime("%Y-%m-%d"),
        "primaryDocument": ultimo[
            "primaryDocument"
        ]
    }


# ==========================================
# PERÍODOS FISCAIS
# ==========================================

def obter_periodos_anuais(
    conceitos,
    documento,
    report_date
):

    if "NetIncomeLoss" not in conceitos:
        raise ValueError(
            "NetIncomeLoss não encontrado."
        )

    registros = (
        conceitos["NetIncomeLoss"]
        ["units"]
        .get("USD", [])
    )

    candidatos = []

    for item in registros:

        if item.get("accn") != documento:
            continue

        if item.get("form") != "10-K":
            continue

        if not item.get("start"):
            continue

        inicio = pd.to_datetime(
            item["start"]
        )

        fim = pd.to_datetime(
            item["end"]
        )

        duracao = (fim - inicio).days

        if not 330 <= duracao <= 380:
            continue

        if item["end"] > report_date:
            continue

        candidatos.append({
            "inicio": item["start"],
            "fim": item["end"]
        })

    periodos = pd.DataFrame(candidatos)

    if periodos.empty:
        raise ValueError(
            "Nenhum período anual válido."
        )

    periodos = (
        periodos
        .drop_duplicates()
        .sort_values(
            "fim",
            ascending=False
        )
        .head(2)
        .sort_values("fim")
    )

    if len(periodos) < 2:
        raise ValueError(
            "São necessários dois "
            "exercícios comparáveis."
        )

    if (
        periodos.iloc[-1]["fim"]
        != report_date
    ):
        raise ValueError(
            "Período mais recente não "
            "coincide com o 10-K."
        )

    return periodos


# ==========================================
# EXTRAÇÃO DE FLUXOS
# ==========================================

def buscar_fluxo(
    conceitos,
    tags,
    documento,
    inicio,
    fim,
    nome
):

    for tag in tags:

        if tag not in conceitos:
            continue

        registros = (
            conceitos[tag]
            ["units"]
            .get("USD", [])
        )

        encontrados = []

        for item in registros:

            if item.get("accn") != documento:
                continue

            if item.get("form") != "10-K":
                continue

            if item.get("start") != inicio:
                continue

            if item.get("end") != fim:
                continue

            encontrados.append(item)

        if encontrados:

            valores = {
                item["val"]
                for item in encontrados
            }

            if len(valores) > 1:
                raise ValueError(
                    f"Valores conflitantes "
                    f"para {nome}: {fim}"
                )

            item = encontrados[0]

            return {
                "valor": item["val"],
                "tag": tag,
                "inicio": inicio,
                "fim": fim,
                "accn": documento
            }

    raise ValueError(
        f"{nome} não encontrado para {fim}."
    )


# ==========================================
# EXTRAÇÃO DE ESTOQUES
# ==========================================

def buscar_estoque(
    conceitos,
    tag,
    documento,
    fim,
    nome
):

    if tag not in conceitos:
        raise ValueError(
            f"Tag não encontrada: {tag}"
        )

    registros = (
        conceitos[tag]
        ["units"]
        .get("USD", [])
    )

    encontrados = []

    for item in registros:

        if item.get("accn") != documento:
            continue

        if item.get("form") != "10-K":
            continue

        if item.get("end") != fim:
            continue

        if item.get("start") is not None:
            continue

        encontrados.append(item)

    if not encontrados:
        raise ValueError(
            f"{nome} não encontrado para {fim}."
        )

    valores = {
        item["val"]
        for item in encontrados
    }

    if len(valores) > 1:
        raise ValueError(
            f"Valores conflitantes "
            f"para {nome}: {fim}"
        )

    item = encontrados[0]

    return {
        "valor": item["val"],
        "tag": tag,
        "inicio": None,
        "fim": item["end"],
        "accn": item["accn"]
    }



# ==========================================
# MOTOR DE ANÁLISE FINANCEIRA
# ==========================================

def gerar_analise_financeira(
    atual,
    anterior,
    roe
):
    """
    Gera observações financeiras usando
    exclusivamente os indicadores calculados
    a partir dos dados validados da SEC.

    Não faz recomendação de investimento.
    """

    analises = []

    # --------------------------------------
    # RECEITA
    # --------------------------------------

    crescimento_receita = (
        atual["Crescimento Receita (%)"]
    )

    if crescimento_receita > 10:

        analises.append(
            f"Revenue increased strongly by "
            f"{crescimento_receita:.2f}% "
            f"year over year."
        )

    elif crescimento_receita > 0:

        analises.append(
            f"Revenue increased by "
            f"{crescimento_receita:.2f}% "
            f"year over year."
        )

    elif crescimento_receita < 0:

        analises.append(
            f"Revenue declined by "
            f"{abs(crescimento_receita):.2f}% "
            f"year over year."
        )

    else:

        analises.append(
            "Revenue remained unchanged "
            "year over year."
        )


    # --------------------------------------
    # LUCRO LÍQUIDO
    # --------------------------------------

    crescimento_lucro = (
        atual["Crescimento Lucro (%)"]
    )

    if crescimento_lucro > crescimento_receita:

        analises.append(
            f"Net income grew "
            f"{crescimento_lucro:.2f}%, "
            "faster than revenue."
        )

    elif crescimento_lucro > 0:

        analises.append(
            f"Net income increased by "
            f"{crescimento_lucro:.2f}%."
        )

    elif crescimento_lucro < 0:

        analises.append(
            f"Net income declined by "
            f"{abs(crescimento_lucro):.2f}%."
        )

    else:

        analises.append(
            "Net income remained unchanged."
        )


    # --------------------------------------
    # MARGEM
    # --------------------------------------

    margem_atual = (
        atual["Margem Liquida (%)"]
    )

    margem_anterior = (
        anterior["Margem Liquida (%)"]
    )

    mudanca_margem = (
        margem_atual - margem_anterior
    )

    if mudanca_margem > 1:

        analises.append(
            f"Net margin expanded from "
            f"{margem_anterior:.2f}% to "
            f"{margem_atual:.2f}%."
        )

    elif mudanca_margem < -1:

        analises.append(
            f"Net margin contracted from "
            f"{margem_anterior:.2f}% to "
            f"{margem_atual:.2f}%."
        )

    else:

        analises.append(
            f"Net margin remained relatively "
            f"stable at {margem_atual:.2f}%."
        )


    # --------------------------------------
    # BALANÇO
    # --------------------------------------

    crescimento_ativos = (
        atual["Ativos"]
        / anterior["Ativos"]
        - 1
    ) * 100

    crescimento_patrimonio = (
        atual["Patrimonio"]
        / anterior["Patrimonio"]
        - 1
    ) * 100

    analises.append(
        f"Total assets changed by "
        f"{crescimento_ativos:+.2f}% while "
        f"stockholders' equity changed by "
        f"{crescimento_patrimonio:+.2f}%."
    )


    # --------------------------------------
    # ROE
    # --------------------------------------

    if roe is None:

        analises.append(
            "ROE could not be calculated "
            "because average equity was not "
            "positive."
        )

    else:

        analises.append(
            f"ROE based on average "
            f"stockholders' equity was "
            f"{roe:.2f}%."
        )


    return analises



# ==========================================
# COMPANY SEARCH
# ==========================================

@st.cache_data(ttl=86400)
def carregar_tickers_sec():
    """
    Carrega a lista oficial de empresas/tickers
    disponibilizada pela SEC.
    """

    url = (
        "https://www.sec.gov/files/"
        "company_tickers.json"
    )

    resposta = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    resposta.raise_for_status()

    return resposta.json()


def buscar_empresa_por_ticker(ticker):
    """
    Converte um ticker em:
    - ticker oficial
    - nome da empresa
    - CIK
    """

    ticker = ticker.strip().upper()

    if not ticker:
        return None

    dados = carregar_tickers_sec()

    for empresa in dados.values():

        if empresa["ticker"].upper() == ticker:

            return {
                "ticker": empresa["ticker"].upper(),
                "nome": empresa["title"],
                "cik": int(empresa["cik_str"])
            }

    return None



# ==========================================
# AI CONTEXT
# ==========================================

def criar_contexto_analista(
    empresa,
    df,
    roe,
    relatorio
):
    """
    Cria um contexto financeiro estruturado
    usando somente dados já validados pelo
    pipeline da SEC.
    """

    anterior = df.iloc[-2]
    atual = df.iloc[-1]

    contexto = {
        "company": empresa["nome"],
        "ticker": empresa["ticker"],

        "fiscal_year_end": str(
            df.index[-1]
        ),

        "revenue_usd": float(
            atual["Receita"]
        ),

        "net_income_usd": float(
            atual["Lucro"]
        ),

        "total_assets_usd": float(
            atual["Ativos"]
        ),

        "stockholders_equity_usd": float(
            atual["Patrimonio"]
        ),

        "revenue_growth_pct": float(
            atual["Crescimento Receita (%)"]
        ),

        "net_income_growth_pct": float(
            atual["Crescimento Lucro (%)"]
        ),

        "net_margin_pct": float(
            atual["Margem Liquida (%)"]
        ),

        "roe_pct": (
            float(roe)
            if roe is not None
            else None
        ),

        "previous_revenue_usd": float(
            anterior["Receita"]
        ),

        "previous_net_income_usd": float(
            anterior["Lucro"]
        ),

        "sec_accession_number": relatorio["accn"],

        "sec_report_date": relatorio["reportDate"],

        "sec_filing_date": relatorio["filingDate"]
    }

    return contexto



# ==========================================
# ASK THE FINANCIAL ANALYST
# ==========================================

def responder_pergunta_financeira(
    pergunta,
    contexto
):
    """
    Responde perguntas financeiras básicas
    exclusivamente com dados validados
    presentes no AI Context.
    """

    pergunta = pergunta.lower().strip()

    ticker = contexto["ticker"]
    empresa = contexto["company"]

    receita = contexto["revenue_usd"] / 1e9
    lucro = contexto["net_income_usd"] / 1e9
    ativos = contexto["total_assets_usd"] / 1e9
    patrimonio = (
        contexto["stockholders_equity_usd"] / 1e9
    )

    crescimento_receita = (
        contexto["revenue_growth_pct"]
    )

    crescimento_lucro = (
        contexto["net_income_growth_pct"]
    )

    margem = contexto["net_margin_pct"]
    roe = contexto["roe_pct"]

    # RECEITA / REVENUE
    if (
        "revenue" in pergunta
        or "receita" in pergunta
    ):
        return (
            f"{empresa} ({ticker}) reported "
            f"${receita:.2f} billion in revenue. "
            f"Revenue changed by "
            f"{crescimento_receita:+.2f}% "
            f"year over year."
        )

    # LUCRO / PROFIT
    elif (
        "profit" in pergunta
        or "income" in pergunta
        or "lucro" in pergunta
    ):
        return (
            f"{empresa} ({ticker}) reported "
            f"${lucro:.2f} billion in net income. "
            f"Net income changed by "
            f"{crescimento_lucro:+.2f}% "
            f"year over year."
        )

    # MARGEM
    elif (
        "margin" in pergunta
        or "margem" in pergunta
        or "profitability" in pergunta
        or "rentabilidade" in pergunta
    ):
        return (
            f"{empresa} ({ticker}) had a "
            f"net margin of {margem:.2f}% "
            f"in the latest fiscal year."
        )

    # ROE
    elif "roe" in pergunta:

        if roe is None:
            return (
                "ROE could not be calculated "
                "from the available validated data."
            )

        return (
            f"{empresa} ({ticker}) had an ROE "
            f"of {roe:.2f}%, calculated using "
            f"average stockholders' equity."
        )

    # ATIVOS
    elif (
        "assets" in pergunta
        or "ativos" in pergunta
    ):
        return (
            f"{empresa} ({ticker}) reported "
            f"${ativos:.2f} billion in "
            f"total assets."
        )

    # PATRIMÔNIO
    elif (
        "equity" in pergunta
        or "patrimônio" in pergunta
        or "patrimonio" in pergunta
    ):
        return (
            f"{empresa} ({ticker}) reported "
            f"${patrimonio:.2f} billion in "
            f"stockholders' equity."
        )

    # RESUMO
    elif (
        "summary" in pergunta
        or "summarize" in pergunta
        or "overview" in pergunta
        or "resumo" in pergunta
        or "summarise" in pergunta
    ):
        return (
            f"{empresa} ({ticker}) generated "
            f"${receita:.2f}B in revenue and "
            f"${lucro:.2f}B in net income. "
            f"Revenue changed "
            f"{crescimento_receita:+.2f}% and "
            f"net income changed "
            f"{crescimento_lucro:+.2f}% year over year. "
            f"Net margin was {margem:.2f}%"
            + (
                f" and ROE was {roe:.2f}%."
                if roe is not None
                else "."
            )
        )

    # PERGUNTA AINDA NÃO SUPORTADA
    else:
        return (
            "I can currently answer questions about "
            "revenue, net income, growth, net margin, "
            "assets, stockholders' equity, ROE, "
            "or provide a financial summary."
        )



# ==========================================
# 10-K TEXT INTELLIGENCE
# ==========================================

@st.cache_data(ttl=86400)
def baixar_10k_html(
    cik,
    accession_number,
    primary_document
):
    """
    Baixa o documento principal do 10-K
    diretamente do SEC EDGAR.
    """

    cik_limpo = str(int(cik))

    accession_limpo = (
        accession_number.replace("-", "")
    )

    url = (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_limpo}/"
        f"{accession_limpo}/"
        f"{primary_document}"
    )

    resposta = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )

    resposta.raise_for_status()

    return {
        "url": url,
        "html": resposta.text
    }



# ==========================================
# 10-K TEXT CLEANING
# ==========================================

def limpar_html_10k(html):
    """
    Converte o HTML/XBRL do 10-K em texto
    limpo para análise textual.
    """

    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Elementos sem conteúdo analítico útil
    for elemento in soup(
        ["script", "style", "noscript"]
    ):
        elemento.decompose()

    texto = soup.get_text(
        separator=" ",
        strip=True
    )

    # Normaliza espaços
    texto = re.sub(
        r"\s+",
        " ",
        texto
    )

    return texto.strip()




def extrair_mda(texto):
    """
    Extrai o MD&A de diferentes estruturas de 10-K.

    Estratégia 1:
    Item 7 contém diretamente o MD&A.

    Estratégia 2:
    Item 7 apenas referencia uma seção independente
    chamada Management's Discussion and Analysis.
    """

    import re

    # ------------------------------------------
    # ESTRATÉGIA 1 — Item 7 tradicional
    # ------------------------------------------

    padrao_inicio = re.compile(
        r"Item\s+7[\.\:\-]?\s+"
        r"Management['’]s\s+Discussion",
        flags=re.IGNORECASE
    )

    padrao_fim = re.compile(
        r"Item\s+7A[\.\:\-]?\s+"
        r"Quantitative\s+and\s+Qualitative",
        flags=re.IGNORECASE
    )

    candidatos = list(
        padrao_inicio.finditer(texto)
    )

    for candidato in candidatos:

        fim_match = padrao_fim.search(
            texto,
            candidato.end()
        )

        if fim_match is None:
            continue

        tamanho = (
            fim_match.start()
            - candidato.start()
        )

        # Elimina índice e referências curtas
        if tamanho >= 5000:

            mda = texto[
                candidato.start():
                fim_match.start()
            ].strip()

            return {
                "texto": mda,
                "inicio": candidato.start(),
                "fim": fim_match.start(),
                "caracteres": len(mda),
                "metodo": "item7"
            }

    # ------------------------------------------
    # ESTRATÉGIA 2 — seção MD&A independente
    # ------------------------------------------

    padrao_mda = re.compile(
        r"Management['’]s\s+"
        r"discussion\s+and\s+analysis",
        flags=re.IGNORECASE
    )

    candidatos_mda = list(
        padrao_mda.finditer(texto)
    )

    for candidato in candidatos_mda:

        inicio = candidato.start()

        # Ignora índice e referências muito iniciais
        if inicio < len(texto) * 0.20:
            continue

        # Procuramos um limite posterior plausível
        limites = [
            r"Consolidated\s+Financial\s+Statements",
            r"Item\s+8[\.\:\-]?",
            r"Financial\s+Statements\s+and\s+Supplementary\s+Data"
        ]

        finais = []

        for limite in limites:

            match = re.search(
                limite,
                texto[candidato.end():],
                flags=re.IGNORECASE
            )

            if match:

                posicao = (
                    candidato.end()
                    + match.start()
                )

                # Evita referências muito próximas
                if posicao - inicio >= 5000:
                    finais.append(posicao)

        if finais:

            fim = min(finais)

            mda = texto[
                inicio:fim
            ].strip()

            if len(mda) >= 5000:

                return {
                    "texto": mda,
                    "inicio": inicio,
                    "fim": fim,
                    "caracteres": len(mda),
                    "metodo": "secao_independente"
                }

    raise ValueError(
        "Não foi possível identificar uma seção MD&A válida."
    )







def buscar_evidencias_mda(pergunta, texto_mda, top_k=5):
    """
    Evidence Retrieval v3.

    Detecta a métrica principal da pergunta e
    prioriza evidências relacionadas diretamente
    a essa métrica.
    """

    import re

    pergunta_lower = pergunta.lower()

    # ------------------------------------------
    # 1. Detectar assunto principal
    # ------------------------------------------

    grupos = {
        "revenue": [
            "revenue",
            "sales",
            "receita"
        ],

        "data_center": [
            "data center",
            "datacenter"
        ],

        "operating_expenses": [
            "operating expenses",
            "operating expense",
            "opex",
            "research and development",
            "r&d",
            "sales general and administrative",
            "sg&a"
        ],

        "gross_margin": [
            "gross margin",
            "gross profit",
            "margem bruta"
        ],

        "net_income": [
            "net income",
            "net profit",
            "lucro líquido",
            "lucro liquido"
        ]
    }

    assunto = None

    # Mais específicos primeiro
    ordem = [
        "data_center",
        "operating_expenses",
        "gross_margin",
        "net_income",
        "revenue"
    ]

    for grupo in ordem:
        if any(
            termo in pergunta_lower
            for termo in grupos[grupo]
        ):
            assunto = grupo
            break

    # ------------------------------------------
    # 2. Termos normais da pergunta
    # ------------------------------------------

    stopwords = {
        "the", "a", "an", "is", "are", "was", "were",
        "did", "do", "does", "why", "what", "how",
        "of", "in", "on", "for", "to", "and", "or",
        "with", "from", "this", "that",
        "o", "a", "os", "as", "de", "da", "do",
        "das", "dos", "em", "para", "por", "que",
        "como", "qual", "quais"
    }

    palavras = re.findall(
        r"[A-Za-zÀ-ÿ&]+",
        pergunta_lower
    )

    termos = {
        palavra
        for palavra in palavras
        if len(palavra) >= 3
        and palavra not in stopwords
    }

    # ------------------------------------------
    # 3. Dividir MD&A
    # ------------------------------------------

    sentencas = re.split(
        r"(?<=[.!?])\s+",
        texto_mda
    )

    candidatos = []

    padroes_causais = [
        "driven by",
        "primarily driven by",
        "due to",
        "primarily due to",
        "resulted from",
        "reflecting",
        "attributable to"
    ]

    pergunta_causal = (
        "why" in pergunta_lower
        or "por que" in pergunta_lower
        or "what drove" in pergunta_lower
        or "what affected" in pergunta_lower
        or "what caused" in pergunta_lower
        or "reason" in pergunta_lower
    )

    # ------------------------------------------
    # 4. Pontuar sentenças
    # ------------------------------------------

    for indice, sentenca in enumerate(sentencas):

        texto_lower = sentenca.lower()
        score = 0

        # Palavras da pergunta
        for termo in termos:
            if termo in texto_lower:
                score += 2

        # Assunto principal
        if assunto:

            termos_assunto = grupos[assunto]

            if any(
                termo in texto_lower
                for termo in termos_assunto
            ):
                score += 12

            else:
                # Penaliza frases que não falam
                # do assunto perguntado
                score -= 6

        # Linguagem causal
        tem_causa = any(
            padrao in texto_lower
            for padrao in padroes_causais
        )

        if tem_causa:
            score += 4

        if pergunta_causal and tem_causa:
            score += 6

        # Combinação mais valiosa:
        # assunto + causalidade
        if assunto:

            tem_assunto = any(
                termo in texto_lower
                for termo in grupos[assunto]
            )

            if tem_assunto and tem_causa:
                score += 10

        if score <= 0:
            continue

        # Contexto ao redor da sentença
        inicio_contexto = max(
            0,
            indice - 1
        )

        fim_contexto = min(
            len(sentencas),
            indice + 2
        )

        contexto = " ".join(
            sentencas[
                inicio_contexto:fim_contexto
            ]
        ).strip()

        candidatos.append({
            "score": score,
            "texto": contexto
        })

    # ------------------------------------------
    # 5. Ranking
    # ------------------------------------------

    candidatos.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    # ------------------------------------------
    # 6. Remover redundância
    # ------------------------------------------

    resultados = []

    for candidato in candidatos:

        texto = candidato["texto"].strip()

        palavras_texto = set(
            re.findall(
                r"[A-Za-zÀ-ÿ]+",
                texto.lower()
            )
        )

        redundante = False

        for existente in resultados:

            palavras_existente = set(
                re.findall(
                    r"[A-Za-zÀ-ÿ]+",
                    existente["texto"].lower()
                )
            )

            if (
                not palavras_texto
                or not palavras_existente
            ):
                continue

            similaridade = (
                len(
                    palavras_texto
                    & palavras_existente
                )
                /
                len(
                    palavras_texto
                    | palavras_existente
                )
            )

            if similaridade >= 0.55:
                redundante = True
                break

        if not redundante:
            resultados.append(candidato)

        if len(resultados) >= top_k:
            break

    return resultados


# ==========================================
# INTERFACE
# ==========================================



# ==========================================
# GENERATIVE AI — v0.10
# ==========================================

def criar_prompt_analista(
    pergunta,
    contexto,
    evidencias
):
    """
    Cria um prompt fundamentado exclusivamente
    nos dados financeiros validados e nas
    evidências recuperadas do 10-K.
    """

    blocos_evidencia = []

    for i, evidencia in enumerate(
        evidencias,
        start=1
    ):
        blocos_evidencia.append(
            f"[Evidence {i}]\n"
            f"{evidencia['texto']}"
        )

    texto_evidencias = "\n\n".join(
        blocos_evidencia
    )

    if contexto["roe_pct"] is not None:
        roe_texto = f'{contexto["roe_pct"]:.2f}%'
    else:
        roe_texto = "Not available"

    prompt = f"""
You are an AI financial analyst.

Your job is to answer questions about a company using ONLY
the validated financial data and SEC 10-K evidence provided below.

RULES:
1. Use ONLY the validated financial data and SEC 10-K evidence provided below.
2. Do not use outside knowledge.
3. Do not invent numbers, explanations, causes, or facts.
4. Any number taken from VALIDATED FINANCIAL DATA must be cited as [Validated Data].
5. Any causal explanation or qualitative claim from the SEC 10-K must cite the relevant [Evidence X].
6. Never cite [Evidence X] for a number unless that exact number appears in that evidence.
7. If the supplied information is insufficient, explicitly say so.
8. Clearly distinguish reported facts from interpretation.
9. Do not make investment recommendations.
10. Be concise and professional.

COMPANY:
{contexto["company"]} ({contexto["ticker"]})

VALIDATED FINANCIAL DATA:
Revenue: ${contexto["revenue_usd"] / 1e9:.2f} billion
Net Income: ${contexto["net_income_usd"] / 1e9:.2f} billion
Total Assets: ${contexto["total_assets_usd"] / 1e9:.2f} billion
Stockholders' Equity: ${contexto["stockholders_equity_usd"] / 1e9:.2f} billion
Revenue Growth: {contexto["revenue_growth_pct"]:.2f}%
Net Income Growth: {contexto["net_income_growth_pct"]:.2f}%
Net Margin: {contexto["net_margin_pct"]:.2f}%
ROE: {roe_texto}

SEC 10-K EVIDENCE:
{texto_evidencias}

USER QUESTION:
{pergunta}

ANSWER:
"""

    return prompt.strip()


def chamar_gemini_com_retry(
    prompt,
    tentativas=3
):
    """
    Envia o prompt ao Gemini e tenta novamente
    automaticamente em caso de erro temporário
    do servidor.
    """

    ultimo_erro = None

    for tentativa in range(
        1,
        tentativas + 1
    ):

        try:

            response = gemini_client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt
            )

            return response.text

        except Exception as erro:

            ultimo_erro = erro

            # Só tenta novamente para erros
            # temporários do servidor.
            status_code = getattr(
                erro,
                "status_code",
                None
            )

            if status_code not in (
                500,
                502,
                503,
                504
            ):
                raise

            if tentativa == tentativas:
                break

            espera = tentativa * 5

            time.sleep(espera)

    raise ultimo_erro



st.title("AI Financial Analyst")

st.markdown(
    "**SEC-powered financial intelligence with "
    "validated fundamentals and grounded AI analysis.**"
)

st.caption(
    "Portfolio Release • Version 1.0"
)

ticker_digitado = st.text_input(
    "Enter a U.S. stock ticker",
    value="NVDA",
    placeholder="Examples: AAPL, MSFT, TSLA, AMZN"
).strip().upper()

if not ticker_digitado:
    st.info("Enter a ticker to start the analysis.")
    st.stop()

with st.spinner("Searching SEC company database..."):
    empresa = buscar_empresa_por_ticker(
        ticker_digitado
    )

if empresa is None:
    st.error(
        f"Ticker '{ticker_digitado}' was not found "
        "in the SEC company database."
    )
    st.stop()

st.markdown(
    f"### {empresa['nome']} "
    f"({empresa['ticker']})"
)

st.caption(
    f"SEC CIK {empresa['cik']}"
)

# ==========================================
# PROCESSAMENTO
# ==========================================

try:

    with st.spinner(
        "Retrieving and validating SEC data..."
    ):

        submissions, facts = carregar_sec(
            empresa["cik"]
        )

        relatorio = selecionar_10k(
            submissions
        )

        conceitos = (
            facts["facts"]["us-gaap"]
        )

        periodos = obter_periodos_anuais(
            conceitos,
            relatorio["accn"],
            relatorio["reportDate"]
        )

        periodo_anterior = periodos.iloc[0]
        periodo_atual = periodos.iloc[1]

        linhas = []
        auditoria = []

        # ----------------------------------
        # DOIS EXERCÍCIOS
        # ----------------------------------

        for _, periodo in periodos.iterrows():

            inicio = periodo["inicio"]
            fim = periodo["fim"]

            receita = buscar_fluxo(
                conceitos,
                TAGS_RECEITA,
                relatorio["accn"],
                inicio,
                fim,
                "Receita"
            )

            lucro = buscar_fluxo(
                conceitos,
                ["NetIncomeLoss"],
                relatorio["accn"],
                inicio,
                fim,
                "Lucro líquido"
            )

            ativos = buscar_estoque(
                conceitos,
                "Assets",
                relatorio["accn"],
                fim,
                "Ativos"
            )

            patrimonio = buscar_estoque(
                conceitos,
                "StockholdersEquity",
                relatorio["accn"],
                fim,
                "Patrimônio líquido"
            )

            linhas.append({
                "Exercicio": fim,
                "Receita": receita["valor"],
                "Lucro": lucro["valor"],
                "Ativos": ativos["valor"],
                "Patrimonio": patrimonio["valor"]
            })

            for nome, dado in [
                ("Receita", receita),
                ("Lucro líquido", lucro),
                ("Ativos", ativos),
                ("Patrimônio líquido", patrimonio)
            ]:

                auditoria.append({
                    "Indicador": nome,
                    "Tag SEC": dado["tag"],
                    "Inicio": dado["inicio"],
                    "Fim": dado["fim"],
                    "Documento": dado["accn"],
                    "Valor USD": dado["valor"]
                })

        df = (
            pd.DataFrame(linhas)
            .set_index("Exercicio")
            .sort_index()
        )

        # ----------------------------------
        # VALIDAÇÕES
        # ----------------------------------

        if df.isnull().any().any():
            raise ValueError(
                "Existem dados financeiros ausentes."
            )

        if (df["Receita"] <= 0).any():
            raise ValueError(
                "Receita inválida."
            )

        if (df["Ativos"] <= 0).any():
            raise ValueError(
                "Ativos inválidos."
            )

        # ----------------------------------
        # INDICADORES
        # ----------------------------------

        df["Margem Liquida (%)"] = (
            df["Lucro"]
            / df["Receita"]
            * 100
        )

        df[
            "Crescimento Receita (%)"
        ] = (
            df["Receita"]
            .pct_change()
            * 100
        )

        df[
            "Crescimento Lucro (%)"
        ] = (
            df["Lucro"]
            .pct_change()
            * 100
        )

        patrimonio_inicial = (
            df.iloc[-2]["Patrimonio"]
        )

        patrimonio_final = (
            df.iloc[-1]["Patrimonio"]
        )

        patrimonio_medio = (
            patrimonio_inicial
            + patrimonio_final
        ) / 2

        if patrimonio_medio <= 0:

            roe = None

        else:

            roe = (
                df.iloc[-1]["Lucro"]
                / patrimonio_medio
                * 100
            )

        df_auditoria = pd.DataFrame(
            auditoria
        )


    # ======================================
    # DASHBOARD
    # ======================================

    st.success(
        "SEC data validated successfully."
    )

    st.subheader("Key Financials")

    atual = df.iloc[-1]

    # PRIMEIRA LINHA
    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Revenue",
            f"US$ {atual['Receita']/1e9:.2f} B",
            f"{atual['Crescimento Receita (%)']:.2f}%"
        )

    with col2:

        st.metric(
            "Net Income",
            f"US$ {atual['Lucro']/1e9:.2f} B",
            f"{atual['Crescimento Lucro (%)']:.2f}%"
        )

    with col3:

        st.metric(
            "Net Margin",
            f"{atual['Margem Liquida (%)']:.2f}%"
        )


    # SEGUNDA LINHA
    col4, col5, col6 = st.columns(3)

    with col4:

        st.metric(
            "Total Assets",
            f"US$ {atual['Ativos']/1e9:.2f} B"
        )

    with col5:

        st.metric(
            "Stockholders' Equity",
            f"US$ {atual['Patrimonio']/1e9:.2f} B"
        )

    with col6:

        if roe is None:

            st.metric(
                "ROE",
                "N/A"
            )

        else:

            st.metric(
                "ROE",
                f"{roe:.2f}%"
            )


    st.caption(
        f"Fiscal year ended "
        f"{df.index[-1]} • "
        f"10-K filed "
        f"{relatorio['filingDate']}"
    )


    # ======================================
    # GRÁFICO
    # ======================================

    st.subheader(
        "Financial Performance"
    )

    grafico = pd.DataFrame({
        "Revenue":
            df["Receita"] / 1e9,

        "Net Income":
            df["Lucro"] / 1e9
    })

    st.bar_chart(
        grafico
    )


    # ======================================
    # TABELA
    # ======================================

    tabela = df.copy()

    for coluna in [
        "Receita",
        "Lucro",
        "Ativos",
        "Patrimonio"
    ]:
        tabela[coluna] /= 1e9

    tabela = tabela.rename(
        columns={
            "Receita":
                "Revenue (US$ B)",

            "Lucro":
                "Net Income (US$ B)",

            "Ativos":
                "Assets (US$ B)",

            "Patrimonio":
                "Equity (US$ B)",

            "Margem Liquida (%)":
                "Net Margin (%)",

            "Crescimento Receita (%)":
                "Revenue Growth (%)",

            "Crescimento Lucro (%)":
                "Net Income Growth (%)"
        }
    )

    st.dataframe(
        tabela.round(2),
        width="stretch"
    )



    # ======================================
    # AUTOMATED FINANCIAL ANALYSIS
    # ======================================

    st.subheader("Financial Analysis")

    analises = gerar_analise_financeira(
        atual,
        df.iloc[-2],
        roe
    )

    for analise in analises:
        st.write("•", analise)

    st.caption(
        "Generated automatically from validated SEC filing data. "
        "This analysis describes historical financial results "
        "and is not investment advice."
    )



    # ======================================
    # ASK THE FINANCIAL ANALYST
    # ======================================

    st.divider()

    st.subheader("AI Financial Analyst")

    st.caption(
        "Ask questions about the company's financial "
        "performance. Answers are grounded in validated "
        "SEC data and retrieved 10-K evidence."
    )

    contexto_analista = criar_contexto_analista(
        empresa,
        df,
        roe,
        relatorio
    )

    pergunta_analista = st.text_input(
        "Your question",
        placeholder=(
            "Example: Why did revenue increase?"
        ),
        key="pergunta_analista"
    )

    if st.button(
        "Analyze",
        key="botao_analisar"
    ):

        if not pergunta_analista.strip():

            st.warning(
                "Please enter a question."
            )

        else:

            try:

                with st.spinner(
                    "Analyzing validated SEC data and 10-K evidence..."
                ):

                    # Baixar o 10-K correspondente
                    documento_10k = baixar_10k_html(
                        empresa["cik"],
                        relatorio["accn"],
                        relatorio["primaryDocument"]
                    )

                    # Limpar HTML
                    texto_10k = limpar_html_10k(
                        documento_10k["html"]
                    )

                    # Extrair MD&A
                    resultado_mda = extrair_mda(
                        texto_10k
                    )

                    # Recuperar evidências relevantes
                    evidencias_analista = buscar_evidencias_mda(
                        pergunta_analista,
                        resultado_mda["texto"],
                        top_k=3
                    )

                    # Criar prompt grounded
                    prompt_analista = criar_prompt_analista(
                        pergunta_analista,
                        contexto_analista,
                        evidencias_analista
                    )

                    # Gerar resposta com Gemini
                    resposta_analista = chamar_gemini_com_retry(
                        prompt_analista
                    )

                st.markdown("#### AI Analyst Response")

                st.markdown(
                    resposta_analista
                )

                             st.caption(
                    "Generated from validated SEC financial data "
                    "and retrieved 10-K evidence."
                )

                with st.expander(
                    "SEC Evidence Used"
                ):

                    st.caption(
                        f'10-K accession: {relatorio["accn"]}'
                    )

                    for i, evidencia in enumerate(
                        evidencias_analista,
                        start=1
                    ):

                        st.markdown(
                            f"**Evidence {i}**"
                        )

                        st.write(
                            evidencia["texto"]
                        )

            except Exception as erro:

                st.error(
                    "The AI analysis is temporarily unavailable."
                )

                st.code(
                    f"{type(erro).__name__}: {erro}"
                )

                st.caption(
                    "Showing the validated financial-data "
                    "response instead."
                )

                resposta_fallback = (
                    responder_pergunta_financeira(
                        pergunta_analista,
                        contexto_analista
                    )
                )

                st.markdown(
                    "#### Validated Data Response"
                )

                st.write(
                    resposta_fallback
                )
                    responder_pergunta_financeira(
                        pergunta_analista,
                        contexto_analista
                    )
                )

                st.markdown(
                    "#### Validated Data Response"
                )

                st.write(
                    resposta_fallback
                )


    # ======================================
    # ROE DETAILS
    # ======================================

    with st.expander(
        "ROE Calculation"
    ):

        st.write(
            "**Formula:** Net Income / "
            "Average Stockholders' Equity"
        )

        st.write(
            "Beginning equity:",
            f"US$ {patrimonio_inicial/1e9:.2f} B"
        )

        st.write(
            "Ending equity:",
            f"US$ {patrimonio_final/1e9:.2f} B"
        )

        st.write(
            "Average equity:",
            f"US$ {patrimonio_medio/1e9:.2f} B"
        )

        if roe is not None:

            st.write(
                "Calculated ROE:",
                f"{roe:.2f}%"
            )


    # ======================================
    # AUDITORIA
    # ======================================

    with st.expander(
        "SEC Data Audit"
    ):

        st.write(
            "Every financial value below "
            "is tied to the selected 10-K "
            "and fiscal period."
        )

        st.dataframe(
            df_auditoria,
            width="stretch"
        )

        st.write(
            "**SEC accession number:**",
            relatorio["accn"]
        )

        st.write(
            "**Primary document:**",
            relatorio["primaryDocument"]
        )


except Exception as erro:

    st.error(
        "Financial data is temporarily unavailable."
    )

    st.caption(
        "The requested SEC filing could not be "
        "retrieved or validated. Please try again later "
        "or select another company."
    )
