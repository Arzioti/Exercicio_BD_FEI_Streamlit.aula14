import streamlit as st
from pymongo import MongoClient
import gridfs
from PIL import Image
import io
import numpy as np
import cv2

# --- Configuração da Página ---
st.set_page_config(page_title="Reconhecimento Facial", layout="wide", initial_sidebar_state="collapsed")

# --- CSS SUPREMO PARA TELA CHEIA MOBILE ---
st.markdown("""
<style>
    /* 1. REMOVE TODAS AS MARGENS DO STREAMLIT NO MOBILE */
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100% !important;
    }
    
    header {visibility: hidden;} /* Esconde o menu do topo */
    footer {visibility: hidden;} /* Esconde o rodapé */

    /* 2. FORÇA O CONTAINER DA CÂMERA A OCUPAR A TELA */
    div[data-testid="stCameraInput"] {
        width: 100% !important;
        margin: 0 !important;
        background-color: black; /* Fundo preto para parecer app nativo */
    }

    /* 3. VÍDEO GIGANTE E CENTRALIZADO */
    div[data-testid="stCameraInput"] video {
        width: 100% !important;
        height: auto !important;
        aspect-ratio: 0.8 !important; /* Mantém proporção retrato */
        object-fit: cover !important;
        border-radius: 0 !important; /* Sem bordas arredondadas no vídeo full */
    }

    /* 4. MÁSCARA SOBREPOSTA (SQUIRCLE) */
    div[data-testid="stCameraInput"]::after {
        content: ""; 
        position: absolute; 
        top: 50%; 
        left: 50%; 
        transform: translate(-50%, -50%);
        
        /* Ocupa 85% da largura da tela */
        width: 85%;
        aspect-ratio: 0.8; 
        
        border: 4px dashed rgba(255, 255, 255, 0.6); 
        border-radius: 45%; 
        
        /* Sombra externa */
        box-shadow: 0 0 0 100vmax rgba(0, 0, 0, 0.5); 
        
        pointer-events: none; 
        z-index: 10;
    }
    
    /* 5. BOTÃO DE FOTO ESTILIZADO E FLUTUANTE */
    div[data-testid="stCameraInput"] button { 
        z-index: 20; 
        position: absolute; /* Flutua sobre o vídeo */
        bottom: 20px;       /* Fica na parte de baixo */
        left: 50%;
        transform: translateX(-50%);
        
        border-radius: 50%;
        width: 80px; 
        height: 80px;
        border: 4px solid white;
        background-color: rgba(255, 50, 50, 0.8);
        color: transparent;
    }
    
    /* Ícone de câmera no botão */
    div[data-testid="stCameraInput"] button::after {
        content: "📸";
        font-size: 35px;
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        color: white;
    }
    
    /* Ajuste para telas grandes (PC) não ficarem estranhas */
    @media (min-width: 800px) {
        .block-container { padding: 2rem !important; }
        div[data-testid="stCameraInput"] { 
            width: 400px !important; 
            margin: 0 auto !important;
            border-radius: 20px;
            overflow: hidden;
        }
        div[data-testid="stCameraInput"] button {
            position: relative;
            bottom: auto;
            transform: none;
            left: auto;
            margin: 10px auto;
        }
    }
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

# --- Estados da Sessão ---
if 'resultados' not in st.session_state:
    st.session_state['resultados'] = None
if 'foto_atual' not in st.session_state:
    st.session_state['foto_atual'] = None

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
    
    todos_arquivos = list(fs.find())
    total = len(todos_arquivos)
    
    if total == 0: return [], img_usuario_processada

    progresso = st.progress(0)
    
    for i, grid_out in enumerate(todos_arquivos):
        try:
            bytes_img = grid_out.read()
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
            
        except Exception:
            continue
        
        if i % 5 == 0: progresso.progress((i + 1) / total)
    
    progresso.empty()
    resultados_ordenados = sorted(resultados, key=lambda x: x['porcentagem'], reverse=True)
    return resultados_ordenados, img_usuario_processada

def salvar_no_banco(nome, imagem_pil):
    try:
        buffer = io.BytesIO()
        imagem_pil.save(buffer, format='JPEG', quality=95)
        fs.put(buffer.getvalue(), filename=f"{nome}.jpg")
        st.toast(f"Salvo: {nome}.jpg", icon="💾")
        st.cache_resource.clear()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- Interface ---

col_cam = st.container()

with col_cam:
    # Câmera no topo (CSS cuida do tamanho)
    foto = st.camera_input("Tire a foto", label_visibility="collapsed")
    
    if foto:
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
            
        with st.spinner("Analisando..."):
            matches, img_proc = encontrar_matches(img_crop)
            st.session_state['resultados'] = matches
            st.session_state['foto_atual'] = img_proc

# Resultados (Abaixo da dobra)
if st.session_state['foto_atual']:
    # Adicionamos padding aqui para não colar nas bordas, já que removemos do global
    with st.container():
        st.markdown("<div style='padding: 20px;'>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["📊 Resultados", "💾 Salvar Nova"])
        
        with tab1:
            res = st.session_state['resultados']
            if res:
                c1, c2 = st.columns([2, 1])
                with c1: ordem = st.selectbox("Ordenar:", ["Mais Parecidas", "Menos Parecidas"])
                with c2: qtde = st.selectbox("Qtd:", [3, 6, 9], index=0)
                
                lista_final = res[:qtde] if "Mais" in ordem else res[-qtde:][::-1]
                
                cols = st.columns(3) 
                for i, item in enumerate(lista_final):
                    with cols[i % 3]:
                        st.image(item['imagem'], use_container_width=True)
                        pct = item['porcentagem']
                        
                        if pct >= 60: cor = "green"
                        else: cor = "red"
                        
                        st.markdown(f"<h4 style='text-align:center; color:{cor}; margin:0;'>{pct:.0f}%</h4>", unsafe_allow_html=True)
            else:
                st.info("Sem resultados.")

        with tab2:
            col_img, col_form = st.columns([1, 2])
            with col_img:
                st.image(st.session_state['foto_atual'], caption="Sua Foto", use_container_width=True)
            with col_form:
                with st.form("save"):
                    nome = st.text_input("Nome:")
                    if st.form_submit_button("Salvar no Banco", use_container_width=True):
                        if nome: salvar_no_banco(nome, st.session_state['foto_atual'])
                        else: st.warning("Digite um nome.")
        
        st.markdown("</div>", unsafe_allow_html=True)