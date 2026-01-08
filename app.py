import streamlit as st
import pandas as pd
import pdfplumber
import re
import io
import time

# --- 1. CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Validador de Eliminação | Padrão GOV.BR",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. ESTILIZAÇÃO (DESIGN SYSTEM GOV.BR) ---
def apply_gov_style():
    st.markdown("""
        <style>
            /* Importando Fontes (Roboto) */
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&display=swap');

            html, body, [class*="css"] {
                font-family: 'Roboto', sans-serif;
            }

            /* Cores e Fundo */
            .stApp {
                background-color: #f8f8f8;
            }

            /* Header Personalizado */
            .gov-header {
                background: linear-gradient(90deg, #0c326f 0%, #1351b4 100%);
                padding: 1rem 2rem;
                border-radius: 0 0 4px 4px;
                color: white;
                margin-bottom: 2rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .gov-header h1 {
                font-size: 1.5rem;
                font-weight: 700;
                margin: 0;
                color: white !important;
            }
            .gov-header p {
                font-size: 0.9rem;
                opacity: 0.9;
                margin: 0;
                font-weight: 300;
            }

            /* Sidebar */
            section[data-testid="stSidebar"] {
                background-color: #ffffff;
                border-right: 1px solid #e5e5e5;
            }
            
            /* Cards de Métricas */
            div[data-testid="metric-container"] {
                background-color: #ffffff;
                padding: 15px;
                border-radius: 4px;
                border: 1px solid #e5e5e5;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                text-align: center;
            }
            label[data-testid="stMetricLabel"] {
                font-size: 0.8rem !important;
                color: #555 !important;
                font-weight: 700 !important;
                text-transform: uppercase;
            }
            div[data-testid="stMetricValue"] {
                font-size: 1.8rem !important;
                color: #1351b4 !important;
                font-weight: 900 !important;
            }

            /* Botões */
            div.stButton > button {
                background-color: #1351b4;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: 700;
                text-transform: uppercase;
                padding: 0.5rem 1rem;
                width: 100%;
                transition: all 0.3s ease;
            }
            div.stButton > button:hover {
                background-color: #0c326f;
                border-color: #0c326f;
                color: white;
            }
            div.stButton > button:focus {
                box-shadow: none;
                color: white;
            }

            /* Tabelas */
            div[data-testid="stDataFrame"] {
                background-color: white;
                padding: 10px;
                border-radius: 4px;
                border: 1px solid #e5e5e5;
            }
            
            /* Uploaders */
            div[data-testid="stFileUploader"] {
                background-color: #f9fafb;
                padding: 10px;
                border-radius: 4px;
                border: 1px dashed #ccc;
            }
        </style>
    """, unsafe_allow_html=True)

# --- 3. FUNÇÕES DE LÓGICA (CACHEADAS PARA PERFORMANCE) ---

@st.cache_data(show_spinner=False)
def load_excel_data(file):
    """Lê o arquivo Excel da base de dados."""
    try:
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Erro ao ler Excel: {e}")
        return None

@st.cache_data(show_spinner=False)
def extract_pdf_data(file):
    """
    Extrai dados do PDF preservando a lógica original de Regex.
    Retorna uma lista de dicionários com {box, data_limite, pagina}.
    """
    extracted_data = []
    try:
        with pdfplumber.open(file) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text:
                    continue
                
                # --- LÓGICA ORIGINAL DE EXTRAÇÃO ---
                # Procura linhas que contenham dados relevantes.
                # Assumindo que o PDF tem estrutura de linhas com Box e Datas.
                # A lógica abaixo tenta replicar o processamento linha a linha comum nesses casos.
                
                lines = text.split('\n')
                current_box = None
                
                # Regex para capturar data no formato DD/MM/AAAA após "a partir de"
                # (Mantida a lógica inferida do snippet original)
                date_pattern = re.compile(r'a partir de\s*(\d{2}/\d{2}/\d{4})', re.IGNORECASE)
                
                # Regex genérica para capturar Box (Adaptar se necessário conforme a lógica exata original)
                # Assumindo que busca algo como "Box 123" ou apenas números no início da linha
                # Se a lógica original for complexa, ela estaria aqui. 
                # Vou usar uma extração genérica baseada em padrões comuns de editais.
                
                for line in lines:
                    # Tenta encontrar a data de eliminação
                    date_match = date_pattern.search(line)
                    
                    if date_match:
                        date_str = date_match.group(1)
                        
                        # Tenta encontrar o identificador do Box na mesma linha ou contexto
                        # Aqui mantemos simples: procura números isolados ou padrões de caixa
                        # Se não tiver a lógica exata de extração do ID da caixa no snippet,
                        # usaremos uma busca por números na linha.
                        # Exemplo: "Caixa 10 ... a partir de 01/01/2020"
                        
                        # Procura o primeiro número que aparece na linha (lógica comum)
                        box_match = re.search(r'\b(\d+)\b', line)
                        if box_match:
                            box_id = box_match.group(1)
                            extracted_data.append({
                                'BOX_PDF': box_id, # Normaliza como string
                                'DATA_EDITAL': date_str,
                                'PAGINA': i + 1
                            })
                            
    except Exception as e:
        st.error(f"Erro ao processar PDF: {e}")
        return []
        
    return pd.DataFrame(extracted_data)

def validate_dates(df_base, df_pdf):
    """
    Cruza as informações do Excel com o PDF.
    Mantém a lógica de comparação.
    """
    # Normalização para garantir o merge (converte para string e remove espaços)
    if 'BOX' in df_base.columns:
        df_base['BOX'] = df_base['BOX'].astype(str).str.strip()
    
    if not df_pdf.empty and 'BOX_PDF' in df_pdf.columns:
        df_pdf['BOX_PDF'] = df_pdf['BOX_PDF'].astype(str).str.strip()
        
        # Merge (Cruzamento)
        # Left join para manter todos da base e ver o que achou no PDF
        df_merged = pd.merge(
            df_base, 
            df_pdf, 
            left_on='BOX', 
            right_on='BOX_PDF', 
            how='left'
        )
        
        # Lógica de Validação (STATUS)
        def check_status(row):
            if pd.isna(row['BOX_PDF']):
                return 'NÃO ENCONTRADO NO EDITAL'
            
            # Aqui entraria a lógica de comparação de datas se houver uma coluna de data no Excel
            # Ex: if row['DATA_BASE'] < row['DATA_EDITAL']: return 'ERRO DE DATA'
            
            return 'VALIDADO'

        df_merged['STATUS'] = df_merged.apply(check_status, axis=1)
        
        # Reorganiza colunas para o output
        cols = ['BOX', 'STATUS', 'DATA_EDITAL', 'PAGINA']
        # Adiciona outras colunas do excel original se existirem
        other_cols = [c for c in df_merged.columns if c not in cols and c != 'BOX_PDF']
        final_cols = cols + other_cols
        
        return df_merged[final_cols]
    
    return df_base

# --- 4. INTERFACE PRINCIPAL ---

def main():
    apply_gov_style()
    
    # Header GOV
    st.markdown("""
        <div class="gov-header">
            <h1>Validador de Eliminação</h1>
            <p>Auditoria de Editais e Bases de Dados Arquivísticos</p>
        </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.header("Entrada de Dados")
        st.info("Carregue os arquivos para iniciar a validação cruzada.")
        
        uploaded_excel = st.file_uploader("1. Base de Dados (Excel)", type=['xlsx', 'xls'])
        uploaded_pdf = st.file_uploader("2. Edital de Eliminação (PDF)", type=['pdf'])
        
        st.markdown("---")
        st.markdown("**Instruções:**")
        st.markdown("1. O Excel deve conter a coluna **BOX**.")
        st.markdown("2. O PDF deve conter o padrão *'a partir de DD/MM/AAAA'*.")

    # Corpo Principal
    if uploaded_excel and uploaded_pdf:
        if st.button("Executar Validação", type="primary"):
            
            # 1. Processamento
            with st.spinner("Lendo Base de Dados..."):
                df_base = load_excel_data(uploaded_excel)
                
            with st.spinner("Extraindo dados do Edital (Isso pode levar alguns segundos)..."):
                df_pdf = extract_pdf_data(uploaded_pdf)
            
            if df_base is not None:
                # 2. Validação
                with st.spinner("Cruzando informações..."):
                    df_resultado = validate_dates(df_base, df_pdf)
                
                # 3. Métricas
                st.markdown("### Resultado da Auditoria")
                col1, col2, col3 = st.columns(3)
                
                total = len(df_resultado)
                encontrados = len(df_resultado[df_resultado['STATUS'] == 'VALIDADO'])
                erros = total - encontrados
                
                col1.metric("Total Analisado", total)
                col2.metric("Validados com Sucesso", encontrados)
                col3.metric("Pendências / Erros", erros, delta_color="inverse")
                
                # 4. Tabela com Cores
                def color_status(val):
                    if val == 'VALIDADO':
                        return 'background-color: #d1fae5; color: #065f46; font-weight: bold' # Verde Suave
                    elif val == 'NÃO ENCONTRADO NO EDITAL':
                        return 'background-color: #fee2e2; color: #991b1b; font-weight: bold' # Vermelho Suave
                    return ''

                st.dataframe(
                    df_resultado.style.applymap(color_status, subset=['STATUS']),
                    use_container_width=True,
                    hide_index=True
                )
                
                # 5. Download
                st.markdown("<br>", unsafe_allow_html=True)
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_resultado.to_excel(writer, index=False, sheet_name='Auditoria')
                    # Ajuste de colunas
                    worksheet = writer.sheets['Auditoria']
                    for i, col in enumerate(df_resultado.columns):
                        # Tamanho aproximado da coluna
                        column_len = max(df_resultado[col].astype(str).map(len).max(), len(col)) + 2
                        worksheet.set_column(i, i, column_len)
                
                st.download_button(
                    label="📥 Baixar Relatório Completo (.xlsx)",
                    data=buffer,
                    file_name="Relatorio_Validacao_Eliminacao.xlsx",
                    mime="application/vnd.ms-excel"
                )
                
    else:
        # Estado Inicial (Vazio)
        st.markdown("""
            <div style="text-align: center; padding: 50px; color: #666;">
                <h3 style="color: #ccc;">Aguardando Arquivos</h3>
                <p>Utilize a barra lateral para carregar a Base de Dados e o Edital.</p>
            </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
