import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image
import io
import numpy as np
import cv2

# --- Configuração da Página (OBRIGATÓRIO SER A PRIMEIRA LINHA) ---
st.set_page_config(page_title="Reconhecimento Facial", layout="wide", initial_sidebar_state="collapsed")

# --- CSS SUPREMO PARA MOBILE (CORRIGIDO V8 - NUCLEAR + ALTERNÂNCIA) ---
st.markdown("""
<style>
    /* 1. RESET TOTAL DA PÁGINA */
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
    }
    
    header, footer, #MainMenu { display: none !important; }
    
    .stApp {
        background-color: black;
    }

    /* 2. ESTILOS DO MODO CÂMERA (FIXO E GIGANTE) */
    
    /* Container Principal da Câmera - Fixo e Tela Cheia */
    div[data-testid="stCameraInput"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 10 !important;
        background-color: black !important;
    }

    /* Wrapper interno do Streamlit (Onde ele tenta travar a proporção) */
    div[data-testid="stCameraInput"] > div {
        width: 100% !important;
        height: 100% !important;
        aspect-ratio: unset !important; /* [CRUCIAL] Remove a trava 4:3 ou 16:9 */
    }

    /* O Vídeo em si - Força bruta para ignorar redimensionamento JS */
    div[data-testid="stCameraInput"] video {
        width: 100% !important;
        height: 100% !important;
        min-height: 100vh !important; /* Garante que nunca encolha */
        min-width: 100vw !important;
        object-fit: cover !important; /* Preenche a tela (zoom) */
    }

    /* Máscara Guia (Rosto) */
    div[data-testid="stCameraInput"]::after {
        content: ""; 
        position: absolute; 
        top: 45%; 
        left: 50%; 
        transform: translate(-50%, -50%);
        width: 70vw; 
        height: 45vh; 
        border: 4px dashed rgba(255, 255, 255, 0.6); 
        border-radius: 50%; 
        box-shadow: 0 0 0 100vmax rgba(0, 0, 0, 0.5); 
        pointer-events: none; 
        z-index: 20; 
    }

    /* Botão de Captura */
    div[data-testid="stCameraInput"] button { 
        position: absolute !important; 
        bottom: 8vh !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        z-index: 30 !important; 
        width: 80px !important; 
        height: 80px !important;
        border-radius: 50% !important;
        background-color: #ff4444 !important;
        border: 4px solid white !important;
        color: transparent !important;
    }
    
    /* 3. ESTILOS DO MODO RESULTADO (LIMPO) */
    
    /* Container de Resultados */
    .resultados-wrapper {
        background-color: #0e1117;
        min-height: 100vh;
        padding: 20px;
        padding-top: 40px;
    }
    
    /* Botão Voltar/Nova Foto */
    .btn-nova-foto {
        width: 100%;
        padding: 15px;
        font-size: 18px;
        font-weight: bold;
    }

    /* STATUS LOADING */
    .stStatusWidget {
        position: fixed !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        z-index: 9999 !important;
        width: 80vw !important;
    }

    /* Esconde textos pequenos */
    small { display: none !important; }
    
</style>
""", unsafe_allow_html=True)

# --- Conexão MongoDB ---
URI = "mongodb+srv://antoniocjunior61_db_user:MP86bA8RrKUcVwc0@cluster0.xnstoor.mongodb.net/?appName=Cluster0"

@st.cache_resource
def init_connection():
    try:
        client = MongoClient(URI, serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        return client
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

client = init_connection()

if client:
    db = client['midias']
    fs = gridfs.GridFS(db)
else:
    st.stop()

# --- Gerenciamento de Estado ---

if 'camera_key' not in st.session_state:
    st.session_state.camera_key = 0
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = None
if 'foto_atual' not in st.session_state:
    st.session_state['foto_atual'] = None

def resetar_app():
    """Limpa os resultados e reinicia a câmera"""
    st.session_state['resultados'] = None
    st.session_state['foto_atual'] = None
    st.session_state.camera_key += 1
    st.rerun()

# --- Funções de Processamento ---

def processar_imagem_aula(image, target_size=(200, 250)):
    img_gray = image.convert('L')
    img_resized = img_gray.resize(target_size)
    img_array = np.array(img_resized, dtype=np.int16)
    return img_array, img_resized

def calcular_diferenca_aula(img_usuario_array, img_banco_array):
    diferenca_abs = np.abs(img_banco_array - img_usuario_array)
    score_diferenca = np.sum(diferenca_abs)
    return score_diferenca

def calcular_similaridade_percentual(diferenca_score):
    max_diferenca_aceitavel = 8000000.0 
    porcentagem = (1 - (diferenca_score / max_diferenca_aceitavel)) * 100
    return max(0.0, min(100.0, porcentagem))

def encontrar_matches(foto_usuario_pil):
    resultados = []
    array_usuario, img_usuario_processada = processar_imagem_aula(foto_usuario_pil)
    
    try:
        todos_arquivos = list(fs.find())
        if not todos_arquivos:
            return [], img_usuario_processada
    except:
        return [], img_usuario_processada
    
    for grid_out in todos_arquivos:
        try:
            bytes_img = grid_out.read()
            if not bytes_img: continue
            img_banco_pil = Image.open(io.BytesIO(bytes_img))
            array_banco, img_banco_processada = processar_imagem_aula(img_banco_pil)
            diferenca = calcular_diferenca_aula(array_usuario, array_banco)
            porcentagem = calcular_similaridade_percentual(diferenca)
            resultados.append({
                'filename': grid_out.filename,
                'diferenca': diferenca,
                'porcentagem': porcentagem,
                'imagem': img_banco_processada
            })
        except:
            continue
            
    resultados_ordenados = sorted(resultados, key=lambda x: x['porcentagem'], reverse=True)
    return resultados_ordenados, img_usuario_processada

def salvar_no_banco(nome, imagem_pil):
    try:
        buffer = io.BytesIO()
        imagem_pil.save(buffer, format='JPEG', quality=95)
        fs.put(buffer.getvalue(), filename=f"{nome}.jpg")
        st.toast(f"Salvo: {nome}.jpg", icon="💾")
        # Pequeno delay para usuário ver a mensagem antes de resetar
        import time
        time.sleep(1.5)
        resetar_app()
    except Exception as e:
        st.error(f"Erro: {e}")

# --- LÓGICA PRINCIPAL (ALTERNÂNCIA DE TELAS) ---

if st.session_state['foto_atual'] is None:
    # === TELA 1: CÂMERA ===
    
    # Renderiza a câmera usando uma key dinâmica para permitir reset
    foto = st.camera_input("Tire a foto", label_visibility="collapsed", key=f"cam_{st.session_state.camera_key}")
    
    if foto:
        # Assim que tira a foto:
        
        # 1. CSS Injection Imediato para esconder a imagem congelada que ficaria por cima
        st.markdown("""
            <style>
                div[data-testid="stCameraInput"] { display: none !important; }
            </style>
        """, unsafe_allow_html=True)
        
        # 2. Mostra barra de carregamento bonita
        with st.status("🔍 Processando imagem...", expanded=True) as status:
            img_original = Image.open(foto)
            
            # Crop Inteligente
            w, h = img_original.size
            target_ratio = 200/250
            current_ratio = w/h
            if current_ratio > target_ratio:
                new_w = h * target_ratio
                left = (w - new_w)/2
                img_crop = img_original.crop((left, 0, left + new_w, h))
            else:
                new_h = w / target_ratio
                top = (h - new_h)/2
                img_crop = img_original.crop((0, top, w, top + new_h))
            
            st.write("Comparando com banco de dados...")
            matches, img_proc = encontrar_matches(img_crop)
            
            # Salva no estado
            st.session_state['resultados'] = matches
            st.session_state['foto_atual'] = img_proc
            
            status.update(label="Concluído!", state="complete", expanded=False)
            
        # 3. Recarrega a página para entrar no "Modo Resultado"
        st.rerun()

else:
    # === TELA 2: RESULTADOS (CÂMERA REMOVIDA) ===
    
    # CSS para garantir que a imagem da câmera não volta assombrar e fundo correto
    st.markdown("""
        <style>
            div[data-testid="stCameraInput"] { display: none !important; }
            .stApp { background-color: #0e1117 !important; }
        </style>
    """, unsafe_allow_html=True)

    # Container principal dos resultados
    st.markdown("<div class='resultados-wrapper'>", unsafe_allow_html=True)
    
    # Botão para voltar
    if st.button("📸 Tirar Nova Foto", type="primary", use_container_width=True):
        resetar_app()
    
    st.divider()

    tab1, tab2 = st.tabs(["📊 Comparação", "💾 Salvar"])
    
    with tab1:
        res = st.session_state['resultados']
        if res:
            c1, c2 = st.columns([1, 1])
            with c1: qtde = st.selectbox("Qtd:", [3, 6, 9], index=0)
            with c2: ordem = st.radio("Ordem:", ["Maior %", "Menor %"], horizontal=True)
            
            if "Maior" in ordem:
                lista_final = res[:qtde]
            else:
                lista_final = res[-qtde:][::-1]
            
            cols = st.columns(3)
            for i, item in enumerate(lista_final):
                with cols[i % 3]:
                    st.image(item['imagem'], use_container_width=True)
                    pct = item['porcentagem']
                    cor = "green" if pct >= 60 else "red"
                    st.markdown(f"<h3 style='text-align:center; color:{cor}; margin:0;'>{pct:.0f}%</h3>", unsafe_allow_html=True)
                    st.caption(f"{item['filename']}", unsafe_allow_html=True)
        else:
            st.info("Nenhuma imagem no banco para comparar.")

    with tab2:
        col_img, col_input = st.columns([1, 2])
        with col_img:
            st.image(st.session_state['foto_atual'], use_container_width=True, caption="Sua Foto")
        with col_input:
            with st.form("salvar_foto"):
                nome_input = st.text_input("Nome:")
                if st.form_submit_button("Salvar no Banco", use_container_width=True):
                    if nome_input:
                        salvar_no_banco(nome_input, st.session_state['foto_atual'])
                    else:
                        st.warning("Digite um nome.")
    
    st.markdown("</div>", unsafe_allow_html=True)