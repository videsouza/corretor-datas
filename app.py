import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import time

# --- CONFIGURAÇÃO DA PÁGINA (Deve ser o primeiro comando) ---
st.set_page_config(
    page_title="Validador de Eliminação Pro",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILIZAÇÃO CSS CUSTOMIZADA (PREMIUM LOOK) ---
st.markdown("""
    <style>
        /* Fundo principal mais suave */
        .stApp {
            background-color: #f8f9fa;
        }
        /* Estilo dos Cards de Métricas */
        div[data-testid="metric-container"] {
            background-color: #ffffff;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border: 1px solid #e0e0e0;
        }
        /* Estilo da Tabela */
        div[data-testid="stDataFrame"] {
            background-color: #ffffff;
            padding: 10px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        /* Botão de Download em destaque */
        div.stButton > button {
            width: 100%;
            border-radius: 8px;
            font-weight: bold;
        }
        /* Esconder menu padrão do Streamlit para ficar mais limpo */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE LÓGICA (Mantidas do original) ---

def extract_data_from_pdf(pdf_file):
    """Extrai dados do PDF usando a lógica de regex fornecida."""
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
    codigo = row['COD_PDF']
    espec = row['ESPEC_PDF']
    
    regras_filtradas = regras_df[regras_df['COD'].astype(str) == codigo]
    
    if regras_filtradas.empty:
        return "Código não encontrado na Tabela Excel", None, None
    
    regra_selecionada = None
    
    # Lógica Especial 2.0.10.00.01
    if codigo == '2.0.10.00.01':
        for _, regra in regras_filtradas.iterrows():
            espec_regra = str(regra['ESPEC']).upper()
            if espec_regra in espec.upper() or espec.upper() in espec_regra:
                regra_selecionada = regra
                break
        if regra_selecionada is None:
             regra_selecionada = regras_filtradas.iloc[0]
             # Marcador silencioso, o status informará se houver erro
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

# --- SIDEBAR (Barra Lateral) ---

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/9543/9543962.png", width=60) # Ícone genérico
    st.title("Painel de Controle")
    st.markdown("---")
    
    st.subheader("1. Arquivos de Entrada")
    file_excel = st.file_uploader("📂 Tabela Temporalidade (Excel)", type=["xlsx", "xls"], help="Colunas obrigatórias: COD, ESPEC, ELIM")
    file_pdf = st.file_uploader("📄 Relatório Eliminação (PDF)", type=["pdf"])
    
    st.markdown("---")
    st.caption("Desenvolvido para validação automática de editais de eliminação de documentos.")
    st.caption("Versão 2.0 (Premium)")

# --- ÁREA PRINCIPAL ---

st.title("🛡️ Auditoria de Datas de Eliminação")
st.markdown("#### Sistema de Validação Cruzada (PDF vs Temporalidade)")

if not file_excel or not file_pdf:
    # Estado Inicial (Sem arquivos)
    st.info("👋 Bem-vindo! Para começar, faça o upload dos arquivos no menu lateral à esquerda.")
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.markdown("### 1️⃣ Upload")
        st.write("Carregue a tabela de regras e o PDF do edital.")
    with col_b:
        st.markdown("### 2️⃣ Processamento")
        st.write("O sistema cruza códigos e calcula datas automaticamente.")
    with col_c:
        st.markdown("### 3️⃣ Relatório")
        st.write("Baixe uma planilha contendo apenas as divergências encontradas.")

else:
    # Processamento
    with st.status("Processando documentos...", expanded=True) as status:
        # 1. Excel
        st.write("Lendo Tabela de Temporalidade...")
        try:
            df_regras = pd.read_excel(file_excel)
            cols_upper = [c.upper() for c in df_regras.columns]
            df_regras.columns = cols_upper
            if not all(col in df_regras.columns for col in ['COD', 'ESPEC', 'ELIM']):
                st.error("O Excel precisa ter as colunas: COD, ESPEC, ELIM")
                st.stop()
        except Exception as e:
            st.error(f"Erro no Excel: {e}")
            st.stop()
            
        # 2. PDF
        st.write("Extraindo dados do PDF (isso pode levar alguns segundos)...")
        try:
            df_pdf = extract_data_from_pdf(file_pdf)
            if df_pdf.empty:
                st.warning("Nenhum padrão de data reconhecido no PDF.")
                st.stop()
        except Exception as e:
            st.error(f"Erro no PDF: {e}")
            st.stop()

        # 3. Análise
        st.write("Validando datas e calculando divergências...")
        resultados = []
        erros_count = 0
        
        # Barra de progresso visual
        prog_bar = st.progress(0)
        total = len(df_pdf)
        
        for idx, row in df_pdf.iterrows():
            status_calc, c_ini, c_fim = calcular_correto(row, df_regras)
            
            if status_calc != "OK":
                erros_count += 1
                resultados.append({
                    'CÓDIGO': row['COD_PDF'],
                    'ESPECIFICAÇÃO (PDF)': row['ESPEC_PDF'],
                    'LIMITE INICIAL': row['LIMITE_INI'],
                    'LIMITE FINAL': row['LIMITE_FIM'],
                    'ELIM PDF': f"{row['ELIM_PDF_INI']} a {row['ELIM_PDF_FIM']}",
                    'STATUS': status_calc,
                    'DATA CORRETA': f"{c_ini} a {c_fim}" if c_ini else "N/A"
                })
            prog_bar.progress((idx + 1) / total)
            
        status.update(label="Análise concluída!", state="complete", expanded=False)

    # --- DASHBOARD DE RESULTADOS ---
    
    st.divider()
    
    # KPIs (Métricas Principais)
    kpi1, kpi2, kpi3 = st.columns(3)
    
    with kpi1:
        st.metric("Documentos Analisados", f"{total}", delta="Processamento Completo")
    
    with kpi2:
        if erros_count > 0:
            st.metric("Inconsistências", f"{erros_count}", delta="-Atenção Requerida", delta_color="inverse")
        else:
            st.metric("Inconsistências", "0", delta="Perfeito", delta_color="normal")
            
    with kpi3:
        taxa_sucesso = ((total - erros_count) / total) * 100
        st.metric("Taxa de Precisão", f"{taxa_sucesso:.1f}%")

    # Exibição dos Dados
    if resultados:
        st.subheader("⚠️ Detalhe das Divergências")
        st.caption("Abaixo estão listados apenas os registros onde a data do PDF difere do cálculo esperado.")
        
        df_resultado = pd.DataFrame(resultados)
        
        # Colorir status
        def color_status(val):
            color = '#ffcdd2' if val == 'ERRO' else '#fff9c4'
            return f'background-color: {color}'

        st.dataframe(
            df_resultado.style.applymap(color_status, subset=['STATUS']),
            use_container_width=True,
            hide_index=True
        )
        
        # Área de Download
        st.markdown("<br>", unsafe_allow_html=True)
        col_download, col_vazia = st.columns([1, 2])
        
        with col_download:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_resultado.to_excel(writer, index=False, sheet_name='Erros')
                # Ajuste automático de colunas
                worksheet = writer.sheets['Erros']
                for i, col in enumerate(df_resultado.columns):
                    column_len = max(df_resultado[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(i, i, column_len)
            
            st.download_button(
                label="📥 Baixar Relatório Corretivo (Excel)",
                data=buffer,
                file_name="Relatorio_Auditoria_Datas.xlsx",
                mime="application/vnd.ms-excel",
                type="primary" # Botão destacado
            )
            
    else:
        st.markdown("---")
        st.success("✅ **Auditoria Aprovada:** Nenhuma divergência encontrada. Todas as datas de eliminação correspondem à tabela de temporalidade.")
        st.balloons()
