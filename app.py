import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image, ImageOps
import io
import numpy as np

# --- Configuração da Página (OBRIGATÓRIO SER A PRIMEIRA LINHA) ---
st.set_page_config(page_title="Reconhecimento Facial", layout="wide", initial_sidebar_state="collapsed")

# --- CSS ESTÁVEL (VERSÃO ROBUSTA) ---
st.markdown("""
<style>
    /* 1. RESET BÁSICO */
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
    }
    
    header, footer, #MainMenu { display: none !important; }
    
    .stApp {
        background-color: black;
    }

    /* 2. CÂMERA EM TELA CHEIA (FORÇA BRUTA) */
    /* Isso garante que o vídeo ocupe 100% da tela e não encolha para 1/3 */
    div[data-testid="stCameraInput"] {
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        z-index: 10 !important;
        background-color: black !important;
    }

    div[data-testid="stCameraInput"] > div {
        height: 100vh !important;
        width: 100vw !important;
        aspect-ratio: unset !important; /* Desliga a trava de proporção do Streamlit */
    }

    div[data-testid="stCameraInput"] video {
        width: 100vw !important;
        height: 100vh !important;
        object-fit: cover !important; /* Preenche a tela toda (Zoom centralizado) */
        min-height: 100vh !important; /* Previne encolhimento */
    }

    /* 3. MÁSCARA GUIA (SIMPLES E CENTRALIZADA) */
    div[data-testid="stCameraInput"]::after {
        content: ""; 
        position: absolute; 
        top: 50%; 
        left: 50%; 
        transform: translate(-50%, -50%);
        width: 250px; /* Tamanho fixo para consistência */
        height: 330px; 
        border: 4px dashed rgba(255, 255, 255, 0.6); 
        border-radius: 50%; 
        box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.5); /* Escurece o fundo */
        pointer-events: none; 
        z-index: 20; 
    }

    /* 4. BOTÃO DE CAPTURA */
    div[data-testid="stCameraInput"] button { 
        position: absolute !important; 
        bottom: 50px !important; 
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
    
    /* 5. TELA DE RESULTADOS */
    .resultados-wrapper {
        background-color: #0e1117;
        min-height: 100vh;
        padding: 20px;
        padding-top: 40px;
        display: flex;
        flex-direction: column;
        align-items: center;
        overflow-y: auto !important; /* Permite rolar */
    }
    
    /* Ajuste de cor para textos */
    .stRadio label, .stSelectbox label, p {
        color: white !important;
    }

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

# --- Estados ---
if 'camera_key' not in st.session_state:
    st.session_state.camera_key = 0
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = None
if 'foto_atual' not in st.session_state:
    st.session_state['foto_atual'] = None

def resetar_app():
    st.session_state['resultados'] = None
    st.session_state['foto_atual'] = None
    st.session_state.camera_key += 1
    st.rerun()

# --- Processamento ---
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
        import time
        time.sleep(1.5)
        resetar_app()
    except Exception as e:
        st.error(f"Erro: {e}")

# --- LÓGICA PRINCIPAL (Câmera Fixa -> Resultados) ---

if st.session_state['foto_atual'] is None:
    # === TELA 1: CÂMERA ===
    foto = st.camera_input("Tire a foto", label_visibility="collapsed", key=f"cam_{st.session_state.camera_key}")
    
    if foto:
        # Esconde a câmera imediatamente após o clique
        st.markdown("""<style>div[data-testid="stCameraInput"] { display: none !important; }</style>""", unsafe_allow_html=True)
        
        with st.status("Processando...", expanded=True) as status:
            img_original = Image.open(foto)
            img_original = ImageOps.exif_transpose(img_original) # Corrige rotação
            
            # --- CROP SIMPLES E EFICIENTE (CENTRO EXATO) ---
            # Assume que o usuário centralizou o rosto na tela.
            # Corta um retângulo central da imagem original.
            w, h = img_original.size
            
            # Define o tamanho do corte (60% da menor dimensão para garantir que pegue o rosto)
            crop_size = min(w, h) * 0.6
            
            left = (w - crop_size) / 2
            top = (h - (crop_size * 1.25)) / 2 # Leve ajuste para proporção retrato (altura > largura)
            right = (w + crop_size) / 2
            bottom = (h + (crop_size * 1.25)) / 2
            
            img_crop = img_original.crop((left, top, right, bottom))
            
            matches, img_proc = encontrar_matches(img_crop)
            
            st.session_state['resultados'] = matches
            st.session_state['foto_atual'] = img_proc
            
            status.update(label="Pronto!", state="complete", expanded=False)
        st.rerun()

else:
    # === TELA 2: RESULTADOS ===
    # Garante que o scroll funciona e remove a câmera
    st.markdown("""
        <style>
            .block-container { overflow: auto !important; }
            div[data-testid="stCameraInput"] { display: none !important; }
            .stApp { background-color: #0e1117 !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='resultados-wrapper'>", unsafe_allow_html=True)
    st.markdown("<h3 style='color: white; text-align: center;'>Análise Concluída</h3>", unsafe_allow_html=True)
    
    # Foto do Usuário
    st.image(st.session_state['foto_atual'], caption="Sua Foto", width=150)
    
    st.divider()
    
    res = st.session_state['resultados']
    if res:
        # Filtros (Restaurados)
        c_f1, c_f2 = st.columns([1, 1])
        with c_f1: qtde = st.selectbox("Qtd:", [3, 6, 9], index=0)
        with c_f2: ordem = st.radio("Ver:", ["Mais Parecidas", "Menos Parecidas"], horizontal=True)
        
        lista = res[:qtde] if "Mais" in ordem else res[-qtde:][::-1]
        
        # Grid de Resultados
        cols = st.columns(3)
        for i, item in enumerate(lista):
            with cols[i % 3]:
                st.image(item['imagem'], use_container_width=True)
                pct = item['porcentagem']
                cor = "#00ff00" if pct >= 60 else "#ff4444"
                st.markdown(f"<div style='text-align:center; color:{cor}; font-weight:bold;'>{pct:.0f}%</div>", unsafe_allow_html=True)
                st.caption(f"{item['filename']}")
    else:
        st.info("Banco vazio.")

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Nova Foto", use_container_width=True, type="primary"):
            resetar_app()
    with c2:
        with st.popover("💾 Salvar", use_container_width=True):
            nome = st.text_input("Nome:")
            if st.button("Confirmar"):
                if nome: salvar_no_banco(nome, st.session_state['foto_atual'])
                else: st.warning("Nome vazio")
    
    st.markdown("</div>", unsafe_allow_html=True)