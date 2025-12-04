import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import time

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Auditor de Eliminação Elegante",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS PERSONALIZADO (TEMA DARK SLATE / TEAL) ---
st.markdown("""
    <style>
        /* Fundo Geral Escuro e Elegante */
        .stApp {
            background-color: #1e1e24; /* Dark Slate */
            color: #f0f0f0; /* Texto Claro */
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        /* Sidebar Mais Escura */
        .stSidebar {
            background-color: #262730; /* Darker Slate */
            border-right: 1px solid #3c3c45;
        }
        
        /* Títulos de Seção e Elementos Principais */
        h1, h2, h3, .stSidebar h2 {
            color: #00BFA5; /* Teal de destaque */
            font-weight: 600;
        }

        /* Cards de Conteúdo (Dashboard) */
        .stContainer, .stPlotlyChart, div[data-testid="stDataFrame"], div[data-testid="stVerticalBlock"] {
            background-color: #262730 !important;
            border-radius: 12px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.4);
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #3c3c45;
        }
        
        /* Card de KPI (Métricas) */
        div[data-testid="stMetric"] {
            background-color: #262730;
            padding: 15px;
            border-radius: 8px;
            border-left: 5px solid #00BFA5; /* Linha de destaque Teal */
            box-shadow: none;
            color: #f0f0f0;
        }
        div[data-testid="stMetricLabel"] {
            color: #a0a0a0;
            font-size: 14px;
        }
        div[data-testid="stMetricValue"] {
            color: white;
            font-size: 28px;
            font-weight: 700;
        }

        /* Botão de Upload (Melhor contraste) */
        div[data-testid="stFileUploader"] {
            border: 2px dashed #00BFA5;
            border-radius: 10px;
            padding: 15px;
            background: #262730;
            color: white;
        }

        /* Tabela de Resultados (Melhor contraste) */
        table th {
            background-color: #3c3c45 !important;
            color: #00BFA5 !important;
            font-weight: 700;
        }
        table td {
            color: #f0f0f0;
        }
        table tr:nth-child(even) {
            background-color: #1e1e24 !important;
        }

        /* Botão Principal */
        div.stButton > button {
            background-color: #00BFA5; /* Teal */
            color: black;
            border-radius: 8px;
            font-weight: bold;
            padding: 0.6rem 1rem;
            width: 100%;
            border: none;
        }
        div.stButton > button:hover {
            background-color: #00e6c3; 
            color: black;
        }

        /* Remover elementos padrão do Streamlit */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE LÓGICA (BACKEND) ---
# (Mantidas inalteradas, apenas renomeadas para melhor legibilidade)

def extract_data_from_pdf(pdf_file):
    """Extrai dados do PDF usando a lógica de regex."""
    dados = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            linhas = text.split('\n')
            for linha in linhas:
                match_codigo = re.match(r'^(\d\.\d\.\d{2}\.\d{2}\.\d{2})\s+', linha)
                if match_codigo:
                    codigo = match_codigo.group(1)
                    partes = linha.split()
                    anos_encontrados = []
                    for parte in partes:
                        if re.match(r'^(19|20)\d{2}$', parte):
                            anos_encontrados.append(int(parte))
                    
                    data_limite_ini = None
                    data_limite_fim = None
                    elim_prevista_ini = None
                    elim_prevista_fim = None
                    
                    linha_upper = linha.upper()
                    tem_ate = "ATÉ" in linha_upper
                    
                    if len(anos_encontrados) >= 2:
                        if tem_ate and len(anos_encontrados) >= 4:
                            data_limite_ini = anos_encontrados[0]
                            data_limite_fim = anos_encontrados[1]
                            elim_prevista_ini = anos_encontrados[2]
                            elim_prevista_fim = anos_encontrados[3]
                        elif tem_ate and len(anos_encontrados) >= 3:
                            data_limite_ini = anos_encontrados[0]
                            data_limite_fim = anos_encontrados[1]
                            elim_prevista_ini = anos_encontrados[2]
                            elim_prevista_fim = anos_encontrados[2]
                        elif not tem_ate and len(anos_encontrados) >= 2:
                            data_limite_ini = anos_encontrados[0]
                            data_limite_fim = anos_encontrados[0]
                            elim_prevista_ini = anos_encontrados[1]
                            elim_prevista_fim = anos_encontrados[1]

                    obs_match = re.search(r'(SE -.*|EMEI.*|EMEF.*|IMI.*|NEI.*|CECOI.*|CENTRO.*|SECRETARIA.*)', linha)
                    especificacao = obs_match.group(1).strip() if obs_match else ""

                    if elim_prevista_ini:
                        dados.append({
                            'COD_PDF': codigo,
                            'ESPEC_PDF': especificacao,
                            'LIMITE_INI': data_limite_ini,
                            'LIMITE_FIM': data_limite_fim,
                            'ELIM_PDF_INI': elim_prevista_ini,
                            'ELIM_PDF_FIM': elim_prevista_fim,
                            'LINHA_ORIGINAL': linha
                        })
    return pd.DataFrame(dados)

def calcular_correto(row, regras_df):
    """Calcula a data correta baseada no Excel, incluindo regra 2.0.10.00.01."""
    codigo = row['COD_PDF']
    espec = row['ESPEC_PDF']
    regras_filtradas = regras_df[regras_df['COD'].astype(str) == codigo]
    
    if regras_filtradas.empty:
        return "Código não encontrado no Excel", None, None
    
    regra_selecionada = None
    if codigo == '2.0.10.00.01':
        for _, regra in regras_filtradas.iterrows():
            espec_regra = str(regra['ESPEC']).upper()
            if espec_regra in espec.upper() or espec.upper() in espec_regra:
                regra_selecionada = regra
                break
        if regra_selecionada is None:
             regra_selecionada = regras_filtradas.iloc[0]
    else:
        regra_selecionada = regras_filtradas.iloc[0]

    prazo = regra_selecionada['ELIM']
    try:
        anos_adicionar = int(prazo)
        calc_ini = row['LIMITE_INI'] + anos_adicionar
        calc_fim = row['LIMITE_FIM'] + anos_adicionar
        
        status = "OK"
        if calc_ini != row['ELIM_PDF_INI'] or calc_fim != row['ELIM_PDF_FIM']:
            status = "ERRO"
        return status, calc_ini, calc_fim
    except ValueError:
        return f"Informativo: Prazo é '{prazo}'", None, None

# --- SIDEBAR (Entrada de Dados) ---

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9543/9543962.png", width=60)
    st.title("🛡️ Data Auditor")
    st.markdown("---")
    st.markdown("**1. Tabela Temporalidade (Excel)**")
    file_excel = st.file_uploader("Upload Excel (COD, ESPEC, ELIM)", type=["xlsx", "xls"], key="excel_sidebar")
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**2. Relatório de Eliminação (PDF)**")
    file_pdf = st.file_uploader("Upload Relatório de Eliminação", type=["pdf"], key="pdf_sidebar")
    
    st.markdown("---")
    st.caption("Sistema de Auditoria de Temporalidade V3.0")

# --- ÁREA PRINCIPAL ---

st.title("Auditor de Datas de Eliminação")
st.subheader("Verificação Cruzada e Geração de Relatório Corretivo")
st.markdown("---")

if not file_excel or not file_pdf:
    st.info("👈 Por favor, carregue os arquivos (Excel e PDF) no menu lateral para iniciar a auditoria.")
else:
    # --- PROCESSAMENTO ---
    with st.spinner("🔄 Processando documentos..."):
        try:
            # 1. Ler Excel
            df_regras = pd.read_excel(file_excel)
            df_regras.columns = [c.upper() for c in df_regras.columns]
            
            # 2. Ler PDF
            df_pdf = extract_data_from_pdf(file_pdf)
            
            if df_pdf.empty:
                st.error("❌ Nenhum padrão de código/data foi encontrado no PDF.")
                st.stop()
            
            # 3. Análise
            resultados = []
            erros_count = 0
            
            for row_idx, row in df_pdf.iterrows():
                status_calc, c_ini, c_fim = calcular_correto(row, df_regras)
                if status_calc != "OK":
                    erros_count += 1
                    resultados.append({
                        'CÓDIGO': row['COD_PDF'],
                        'ESPECIFICAÇÃO': row['ESPEC_PDF'],
                        'LIMITE': f"{row['LIMITE_INI']} - {row['LIMITE_FIM']}",
                        'DATA NO PDF': f"{row['ELIM_PDF_INI']} - {row['ELIM_PDF_FIM']}",
                        'STATUS': status_calc,
                        'DATA CORRETA': f"{c_ini} - {c_fim}" if c_ini else "N/A"
                    })

            # --- DASHBOARD DE RESULTADOS ---
            st.success("✅ Auditoria Concluída!")
            st.markdown("---")
            
            # KPIs (Métricas)
            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            
            with col_kpi1:
                st.metric("Total Analisado", len(df_pdf))
            
            with col_kpi2:
                if erros_count > 0:
                    st.metric("Inconsistências Encontradas", erros_count, delta="Requer atenção", delta_color="inverse")
                else:
                    st.metric("Inconsistências Encontradas", erros_count, delta="Perfeito", delta_color="normal")
            
            with col_kpi3:
                taxa_precisao = ((len(df_pdf) - erros_count) / len(df_pdf)) * 100 if len(df_pdf) > 0 else 0
                st.metric("Taxa de Conformidade", f"{taxa_precisao:.1f}%")

            st.markdown("---")
            
            # Tabela de Detalhes
            if erros_count > 0:
                st.subheader("❌ Detalhe das Divergências")
                st.caption(f"Foram encontradas **{erros_count}** divergências onde a data do PDF não corresponde ao cálculo.")
                
                df_resultado = pd.DataFrame(resultados)
                
                # Estilização da Tabela (destaque para ERRO e Informativo)
                def color_status(val):
                    if val == 'ERRO':
                        # Vermelho no fundo escuro
                        return 'background-color: #58151c; color: #ffcdd2' 
                    elif val.startswith('Informativo'):
                        # Amarelo no fundo escuro
                        return 'background-color: #4b4b00; color: #fff9c4'
                    return ''
                
                st.dataframe(
                    df_resultado.style.applymap(color_status, subset=['STATUS']),
                    use_container_width=True,
                    hide_index=True
                )
                
                # Botão de Download
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_resultado.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 BAIXAR RELATÓRIO CORRETIVO (EXCEL)",
                    data=buffer,
                    file_name="Relatorio_Auditoria_Datas.xlsx",
                    mime="application/vnd.ms-excel"
                )
                
            else:
                st.subheader("Resultado")
                st.balloons()
                st.success("🎉 Nenhum erro encontrado! Todas as datas de eliminação estão em conformidade com a Tabela de Temporalidade.")

        except Exception as e:
            st.error(f"Ocorreu um erro inesperado no processamento. Verifique o formato dos seus arquivos. Detalhes: {str(e)}")
