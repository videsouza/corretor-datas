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
            @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700;900&display=swap');
            html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
            .stApp { background-color: #f8f8f8; }
            .gov-header {
                background: linear-gradient(90deg, #0c326f 0%, #1351b4 100%);
                padding: 1rem 2rem; border-radius: 0 0 4px 4px; color: white; margin-bottom: 2rem;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .gov-header h1 { font-size: 1.5rem; font-weight: 700; margin: 0; color: white !important; }
            .gov-header p { font-size: 0.9rem; opacity: 0.9; margin: 0; font-weight: 300; }
            section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e5e5e5; }
            div[data-testid="metric-container"] {
                background-color: #ffffff; padding: 15px; border-radius: 4px; border: 1px solid #e5e5e5;
                box-shadow: 0 1px 3px rgba(0,0,0,0.05); text-align: center;
            }
            div.stButton > button {
                background-color: #1351b4; color: white; border: none; border-radius: 4px;
                font-weight: 700; text-transform: uppercase; padding: 0.5rem 1rem; width: 100%;
                transition: all 0.3s ease;
            }
            div.stButton > button:hover { background-color: #0c326f; }
            div[data-testid="stDataFrame"] { background-color: white; padding: 10px; border-radius: 4px; border: 1px solid #e5e5e5; }
        </style>
    """, unsafe_allow_html=True)

# --- 3. FUNÇÕES DE LÓGICA ---

@st.cache_data(show_spinner=False)
def load_excel_data(file):
    try:
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Erro ao ler Excel: {e}")
        return None

@st.cache_data(show_spinner=False)
def extract_pdf_data(file):
    extracted_data = []
    try:
        with pdfplumber.open(file) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if not text: continue
                
                lines = text.split('\n')
                # Regex para capturar data (DD/MM/AAAA) após "a partir de"
                date_pattern = re.compile(r'a partir de\s*(\d{2}/\d{2}/\d{4})', re.IGNORECASE)
                
                for line in lines:
                    date_match = date_pattern.search(line)
                    if date_match:
                        date_str = date_match.group(1)
                        # Procura o primeiro número que aparece na linha (Identificador/Box)
                        # Ajuste conforme necessidade se o ID for mais complexo
                        box_match = re.search(r'\b(\d+)\b', line)
                        if box_match:
                            box_id = box_match.group(1)
                            extracted_data.append({
                                'ID_PDF': box_id,
                                'DATA_EDITAL': date_str,
                                'PAGINA': i + 1
                            })
    except Exception as e:
        st.error(f"Erro ao processar PDF: {e}")
        return []
        
    return pd.DataFrame(extracted_data)

def validate_dates(df_base, df_pdf):
    # 1. Identificar a coluna chave no Excel (COD)
    col_chave = 'COD'
    
    if col_chave not in df_base.columns:
        # Tenta fallback se COD não existir, mas avisa erro
        if 'BOX' in df_base.columns: col_chave = 'BOX'
        else:
            df_base['STATUS'] = f'ERRO: COLUNA "{col_chave}" NÃO ENCONTRADA'
            return df_base

    # Normalizar Excel
    df_base[col_chave] = df_base[col_chave].astype(str).str.strip()

    # 2. Verificar PDF
    if df_pdf.empty or 'ID_PDF' not in df_pdf.columns:
        df_base['STATUS'] = 'NÃO VERIFICADO (PDF VAZIO)'
        return df_base

    # Normalizar PDF
    df_pdf['ID_PDF'] = df_pdf['ID_PDF'].astype(str).str.strip()
    
    # 3. Cruzamento (Merge)
    # Usa 'COD' do Excel e 'ID_PDF' do PDF
    df_merged = pd.merge(
        df_base, 
        df_pdf, 
        left_on=col_chave, 
        right_on='ID_PDF', 
        how='left'
    )
    
    # 4. Definir Status
    def check_status(row):
        if pd.isna(row['ID_PDF']):
            return 'NÃO ENCONTRADO NO EDITAL'
        # Aqui você pode adicionar lógica extra: comparar row['ELIM'] com row['DATA_EDITAL']
        return 'VALIDADO'

    df_merged['STATUS'] = df_merged.apply(check_status, axis=1)
    
    # 5. Limpeza de colunas para exibição
    # Colunas prioritárias
    cols_order = [col_chave, 'ESPEC', 'ELIM', 'STATUS', 'DATA_EDITAL', 'PAGINA']
    
    # Filtra apenas as que existem
    final_cols = [c for c in cols_order if c in df_merged.columns]
    
    # Adiciona o restante que sobrar
    remaining = [c for c in df_merged.columns if c not in final_cols and c != 'ID_PDF']
    
    return df_merged[final_cols + remaining]

# --- 4. INTERFACE ---

def main():
    apply_gov_style()
    
    st.markdown("""
        <div class="gov-header">
            <h1>Validador de Eliminação</h1>
            <p>Auditoria de Editais e Bases de Dados Arquivísticos</p>
        </div>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.header("Entrada de Dados")
        st.info("Carregue os arquivos para iniciar.")
        uploaded_excel = st.file_uploader("1. Base de Dados (Excel)", type=['xlsx', 'xls'])
        uploaded_pdf = st.file_uploader("2. Edital de Eliminação (PDF)", type=['pdf'])
        st.markdown("---")
        st.markdown("**Requisitos:**")
        st.markdown(f"- Excel deve ter: **COD**, **ESPEC**, **ELIM**")
        st.markdown("- PDF: Texto selecionável ('a partir de...')")

    if uploaded_excel and uploaded_pdf:
        if st.button("Executar Validação", type="primary"):
            with st.spinner("Lendo Excel..."):
                df_base = load_excel_data(uploaded_excel)
            with st.spinner("Lendo PDF..."):
                df_pdf = extract_pdf_data(uploaded_pdf)
            
            if df_base is not None:
                with st.spinner("Validando..."):
                    df_resultado = validate_dates(df_base, df_pdf)
                
                # Métricas
                st.markdown("### Resultado")
                col1, col2, col3 = st.columns(3)
                
                # Garante coluna STATUS
                if 'STATUS' not in df_resultado.columns: df_resultado['STATUS'] = 'ERRO'

                total = len(df_resultado)
                ok = len(df_resultado[df_resultado['STATUS'] == 'VALIDADO'])
                erro = total - ok
                
                col1.metric("Itens Analisados", total)
                col2.metric("Validados", ok)
                col3.metric("Não Encontrados / Erros", erro, delta_color="inverse")
                
                # Tabela
                def color_row(val):
                    if val == 'VALIDADO': return 'background-color: #d1fae5; color: #065f46; font-weight: bold'
                    return 'background-color: #fee2e2; color: #991b1b; font-weight: bold'

                st.dataframe(
                    df_resultado.style.map(color_row, subset=['STATUS']),
                    use_container_width=True, hide_index=True
                )
                
                # Download
                st.markdown("<br>", unsafe_allow_html=True)
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_resultado.to_excel(writer, index=False, sheet_name='Auditoria')
                    worksheet = writer.sheets['Auditoria']
                    for i, col in enumerate(df_resultado.columns):
                        try: width = max(df_resultado[col].astype(str).map(len).max(), len(col)) + 2
                        except: width = 15
                        worksheet.set_column(i, i, width)
                
                st.download_button("📥 Baixar Relatório (.xlsx)", buffer, "Relatorio_Validacao.xlsx", "application/vnd.ms-excel")
    else:
        st.markdown("<div style='text-align:center; padding:50px; color:#666;'><h3>Aguardando Arquivos</h3></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
