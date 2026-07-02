import streamlit as st
import json
import os
import random
import io
import base64
import time

from groq import Groq
from PIL import Image

# =====================================================
# CONFIGURAÇÃO
# =====================================================

st.set_page_config(
    page_title="IA ou Real?",
    layout="wide"
)

# ================== GROQ API KEY ==================
GROQ_API_KEY = "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"

client = Groq(api_key=GROQ_API_KEY)

# Pastas
IMAGES_FOLDER = "imagens"
REAIS_FOLDER = os.path.join(IMAGES_FOLDER, "reais")
IA_FOLDER = os.path.join(IMAGES_FOLDER, "ia")

NUM_DICAS = 3
TAMANHO_PADRAO = (600, 500)

# CSS para forçar tamanho exato das imagens
st.markdown("""
    <style>
        .stImage img {
            width: 900px !important;
            height: 700px !important;
            object-fit: contain !important;
            border-radius: 8px;
        }
    </style>
""", unsafe_allow_html=True)

# =====================================================
# VERIFICAÇÕES
# =====================================================

for pasta in [IMAGES_FOLDER, REAIS_FOLDER, IA_FOLDER]:
    if not os.path.exists(pasta):
        os.makedirs(pasta, exist_ok=True)

def carregar_imagens():
    reais = [
        os.path.join(REAIS_FOLDER, f)
        for f in os.listdir(REAIS_FOLDER)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]
    ia = [
        os.path.join(IA_FOLDER, f)
        for f in os.listdir(IA_FOLDER)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]
    return reais, ia

reais, imagens_ia = carregar_imagens()

if not reais and not imagens_ia:
    st.error("Coloque imagens nas pastas `imagens/reais` e `imagens/ia`")
    st.stop()

# =====================================================
# SESSION STATE
# =====================================================

for chave, valor in {
    "jogo_iniciado": False,
    "imagens_usadas": [],
    "imagem_atual": None,
    "dicas": None,
    "resposta_correta": "",          # "IA" ou "REAL"
    "indice_dica": 0,
    "acertou": False,
    "revelada": False,
    "botao_jogar_novamente": False,
    "tentativas": 0,
}.items():
    if chave not in st.session_state:
        st.session_state[chave] = valor

# =====================================================
# FUNÇÕES
# =====================================================

def normalizar(texto):
    return texto.lower().strip()

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")

def gerar_dicas(caminho_imagem: str, eh_ia: bool):
    tipo = "gerada por IA" if eh_ia else "foto real"
    
    prompt = f"""
Você é um especialista em detecção de imagens geradas por IA.

Analise a imagem e crie **exatamente 3 dicas progressivas** para ajudar alguém a descobrir se ela é {tipo}.

- Dica 1: Difícil / sutil (detalhes que levantam suspeita)
- Dica 2: Nível médio
- Dica 3: Fácil (bem reveladora, mas sem dizer diretamente "é IA" ou "é real")

Foque em:
- Anatomia, mãos, olhos, simetria
- Iluminação, sombras e reflexos inconsistentes
- Texturas de pele/cabelo/fundos
- Artefatos típicos de IA (dedos extras, borrões, padrões estranhos)
- Qualidade de detalhes finos

Responda APENAS com JSON válido:
{{
  "dica1": "...",
  "dica2": "...",
  "dica3": "..."
}}
"""

    for tentativa in range(3):
        try:
            base64_image = encode_image(caminho_imagem)

            resposta = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                            }
                        ]
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=700,
                temperature=0.6
            )

            conteudo = resposta.choices[0].message.content.strip()
            return json.loads(conteudo)

        except Exception as e:
            print(f"Tentativa {tentativa+1} falhou: {e}")
            if tentativa < 2:
                time.sleep(2)

    st.error("Erro ao gerar dicas.")
    return {"dica1": "Erro na análise.", "dica2": "Erro na análise.", "dica3": "Erro na análise."}


def redimensionar_com_crop(img: Image.Image, tamanho: tuple) -> Image.Image:
    largura_alvo, altura_alvo = tamanho
    proporcao_alvo = largura_alvo / altura_alvo
    largura_orig, altura_orig = img.size
    proporcao_orig = largura_orig / altura_orig

    if proporcao_orig > proporcao_alvo:
        nova_altura = altura_alvo
        nova_largura = int(nova_altura * proporcao_orig)
    else:
        nova_largura = largura_alvo
        nova_altura = int(nova_largura / proporcao_orig)

    img_redimensionada = img.resize((nova_largura, nova_altura), Image.LANCZOS)

    left = (nova_largura - largura_alvo) / 2
    top = (nova_altura - altura_alvo) / 2
    right = left + largura_alvo
    bottom = top + altura_alvo

    return img_redimensionada.crop((left, top, right, bottom))


def carregar_imagem(caminho):
    """Carrega e redimensiona a imagem para tamanho exato"""
    img = Image.open(caminho).convert("RGB")
    img = redimensionar_com_crop(img, TAMANHO_PADRAO)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def escolher_nova_imagem():
    reais, imgs_ia = carregar_imagens()

    todas = [
        ("REAL", img) for img in reais
    ] + [
        ("IA", img) for img in imgs_ia
    ]

    # Remove as imagens já utilizadas
    disponiveis = [
        item for item in todas
        if item[1] not in st.session_state.imagens_usadas
    ]

    # Acabaram todas as imagens
    if not disponiveis:
        st.success("🎉 Todas as imagens já foram exibidas!")

        st.session_state.jogo_iniciado = False
        st.session_state.imagens_usadas = []
        st.rerun()

    # Escolhe somente entre as ainda não usadas
    tipo, escolha = random.choice(disponiveis)

    st.session_state.imagens_usadas.append(escolha)

    st.session_state.resposta_correta = tipo
    st.session_state.imagem_atual = escolha
    st.session_state.indice_dica = 0
    st.session_state.acertou = False
    st.session_state.revelada = False
    st.session_state.tentativas = 0

    with st.spinner("🔍 Analisando imagem com Llama 4 Scout..."):
        st.session_state.dicas = gerar_dicas(
            escolha,
            tipo == "IA"
        )

# =====================================================
# INTERFACE
# =====================================================

if st.session_state.botao_jogar_novamente:
    st.session_state.botao_jogar_novamente = False
    escolher_nova_imagem()

if not st.session_state.jogo_iniciado:
    st.title("🧠 IA ou Real?")
    st.write("A IA analisa a imagem e gera dicas para você descobrir se ela foi **gerada por inteligência artificial** ou é uma **foto real**.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Fotos Reais", len(reais))
    with col2:
        st.metric("Imagens IA", len(imagens_ia))
    
    if st.button("Iniciar Jogo", use_container_width=True, type="primary"):
        st.session_state.jogo_iniciado = True
        escolher_nova_imagem()
        st.rerun()
    st.stop()

# Jogo principal
imagem = carregar_imagem(st.session_state.imagem_atual)

col_img, col_lateral = st.columns([2, 1])

with col_img:
    st.image(imagem, width=TAMANHO_PADRAO[0])   # mantido para compatibilidade + CSS
    st.caption("Observe com atenção os detalhes!")

with col_lateral:
    st.subheader("💡 Dicas para Detecção")
    
    if st.session_state.dicas:
        for i in range(st.session_state.indice_dica):
            dica = st.session_state.dicas.get(f"dica{i+1}", "")
            if dica:
                st.markdown(f"**Dica {i+1}:** {dica}")

    if not st.session_state.acertou and not st.session_state.revelada:
        if st.button("Pedir Dica", use_container_width=True):
            if st.session_state.indice_dica < NUM_DICAS:
                st.session_state.indice_dica += 1
                st.rerun()
            else:
                st.warning("Não há mais dicas disponíveis.")

    if not st.session_state.acertou and not st.session_state.revelada:
        st.subheader("Qual é a sua resposta?")
        col_op1, col_op2 = st.columns(2)
        with col_op1:
            if st.button("🖼️ É REAL", use_container_width=True):
                if st.session_state.resposta_correta == "REAL":
                    st.session_state.acertou = True
                    st.rerun()
                else:
                    st.session_state.tentativas += 1
                    st.error("Não é real!")
        with col_op2:
            if st.button("🤖 É IA", use_container_width=True):
                if st.session_state.resposta_correta == "IA":
                    st.session_state.acertou = True
                    st.rerun()
                else:
                    st.session_state.tentativas += 1
                    st.error("Não é IA!")

# Resultado final
if st.session_state.acertou:
    st.success(f"🎉 Parabéns! Você acertou! Era **{st.session_state.resposta_correta}**.")
    st.balloons()
    if st.button("Jogar Novamente", use_container_width=True, type="primary"):
        st.session_state.botao_jogar_novamente = True
        st.rerun()

elif st.session_state.revelada:
    st.error("❌ Você não acertou.")
    st.info(f"**Resposta correta:** {'🤖 Gerada por IA' if st.session_state.resposta_correta == 'IA' else '🖼️ Foto Real'}")
    if st.button("Jogar Novamente", use_container_width=True):
        st.session_state.botao_jogar_novamente = True
        st.rerun()
else:
    placeholder = st.empty()

    with placeholder:
        if st.button("Pular Imagem", use_container_width=True):
            placeholder.empty()  # Remove o botão imediatamente
            escolher_nova_imagem()
            st.rerun()