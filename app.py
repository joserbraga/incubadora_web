import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
import json
from PIL import Image
import requests

# ---------- CONFIGURAÇÕES ----------
ARQ_INCUBACAO_ATUAL = "incubacao_atual.csv"
ARQ_INCUBACOES_JSON = "incubacoes.json"
ARQ_DADOS = "dados.csv"
ARQ_AVES = "aves.json"
DIR_FOTOS = "fotos"
IP_ESP32 = "192.168.1.125"  # IP fixo definido por você

# Criar pasta de fotos caso ainda não exista
os.makedirs(DIR_FOTOS, exist_ok=True)

# ---------- FUNÇÕES UTILITÁRIAS ----------

# Carrega as espécies de aves e seus parâmetros
def carregar_aves():
    if os.path.exists(ARQ_AVES):
        with open(ARQ_AVES, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Carrega os dados da incubação atual
def carregar_incubacao_ativa():
    if os.path.exists(ARQ_INCUBACAO_ATUAL):
        return pd.read_csv(ARQ_INCUBACAO_ATUAL).iloc[0].to_dict()
    return None

# Salva os dados da incubação atual
def salvar_incubacao_ativa(dados):
    pd.DataFrame([dados]).to_csv(ARQ_INCUBACAO_ATUAL, index=False)

# Limpa o registro da incubação ativa
def limpar_incubacao_ativa():
    if os.path.exists(ARQ_INCUBACAO_ATUAL):
        os.remove(ARQ_INCUBACAO_ATUAL)

# Salva os dados de uma incubação finalizada no histórico
def salvar_incubacao_finalizada(incubacao):
    historico = []
    if os.path.exists(ARQ_INCUBACOES_JSON):
        with open(ARQ_INCUBACOES_JSON, "r") as f:
            historico = json.load(f)
    historico.append(incubacao)
    with open(ARQ_INCUBACOES_JSON, "w") as f:
        json.dump(historico, f, indent=2)

# Carrega o histórico de todas as incubações
def carregar_historico():
    if os.path.exists(ARQ_INCUBACOES_JSON):
        with open(ARQ_INCUBACOES_JSON, "r") as f:
            return json.load(f)
    return []

# Envia a configuração para o ESP32 por HTTP GET
def enviar_config_esp32(params):
    try:
        response = requests.get(f"http://{IP_ESP32}/config", params=params, timeout=5)
        return response.status_code == 200
    except:
        return False
# ---------- INTERFACE PRINCIPAL ----------

# Logo e título
logo = Image.open("logo_cb.png")
col1, col2, col3 = st.columns([1, 3, 1])
with col1:
    st.image(logo, width=100)
with col2:
    st.markdown("<h1 style='text-align: center;'>Carvalho Braga Automação</h1>", unsafe_allow_html=True)

# Abas principais
abas = st.tabs(["🐣 Incubadora Atual", "📜 Histórico de Incubações"])

# ---------- ABA 1: INCUBADORA ATUAL ----------
with abas[0]:
    st.subheader("Sistema de Monitoramento de Incubação")

    # Carrega dados
    incubacao = carregar_incubacao_ativa()
    aves = carregar_aves()

    # Se ainda não houver incubação ativa, exibe o formulário de nova incubação
    if not incubacao:
        # Lista as espécies e seleciona fora do form para permitir atualização imediata
        especies = [ave["nome"] for ave in aves]
        especie_sel = st.selectbox("Espécie da ave", especies)

        # Busca os dados da espécie selecionada
        dados_ave = next((a for a in aves if a["nome"] == especie_sel), None)

        # Mostra os parâmetros ideais da ave selecionada
        st.markdown(f"**🕒 Duração:** {dados_ave['dias']} dias")
        st.markdown(f"🌡️ **Temperatura ideal:** {dados_ave['temp_min']}°C a {dados_ave['temp_max']}°C")
        st.markdown(f"💧 **Umidade ideal:** {dados_ave['umid_min']}% a {dados_ave['umid_max']}%")

        # Formulário separado para enviar os dados
        with st.form("form_incubacao"):
            ovos = st.number_input("Quantidade de ovos", min_value=1, step=1)
            observacoes = st.text_area("Observações")
            enviar = st.form_submit_button("✅ Iniciar Incubação")

            if enviar:
                dados = {
                    "inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ovos": ovos,
                    "raca": especie_sel,
                    "observacoes": observacoes,
                    "ovoscopia": "",
                    "nascimentos": "",
                    "fim": "",
                    "dias": dados_ave["dias"]
                }
                salvar_incubacao_ativa(dados)

                # Envia os dados ao ESP32
                enviado = enviar_config_esp32({
                    "dias": dados_ave["dias"],
                    "temp_min": dados_ave["temp_min"],
                    "temp_max": dados_ave["temp_max"],
                    "umid_min": dados_ave["umid_min"],
                    "umid_max": dados_ave["umid_max"]
                })

                if enviado:
                    st.success("✅ Configuração enviada ao ESP32 com sucesso!")
                else:
                    st.warning("⚠️ Não foi possível enviar a configuração ao ESP32.")
                st.rerun()

    else:
        st.success("✅ Incubação em andamento")
        st.write(f"📅 Início: {incubacao['inicio']}")
        st.write(f"🥚 Ovos: {incubacao['ovos']}")
        st.write(f"🐔 Raça: {incubacao['raca']}")
        st.write(f"📝 {incubacao['observacoes']}")

        dias_atuais = int(incubacao["dias"])
        inicio = datetime.strptime(incubacao["inicio"], "%Y-%m-%d %H:%M:%S")
        fim = inicio + timedelta(days=dias_atuais)
        agora = datetime.now()
        dias_decorridos = (agora - inicio).days
        restante = fim - agora

        if restante.total_seconds() > 0:
            dias = restante.days
            horas = restante.seconds // 3600
            minutos = (restante.seconds % 3600) // 60
            st.info(f"⏳ Tempo restante: {dias}d {horas}h {minutos}min")
            st.write(f"📆 Previsão de eclosão: {fim.strftime('%d/%m/%Y %H:%M')}")

            # Ovoscopia no 7º dia
            if dias_decorridos == 7 and incubacao["ovoscopia"] == "":
                with st.form("form_ovoscopia"):
                    ovos_fert = st.number_input("Quantos ovos continuam após ovoscopia?", min_value=0, max_value=int(incubacao["ovos"]))
                    confirmar = st.form_submit_button("📋 Registrar Ovoscopia")
                    if confirmar:
                        incubacao["ovoscopia"] = ovos_fert
                        salvar_incubacao_ativa(incubacao)
                        st.success("Ovoscopia registrada.")
                        st.rerun()
            elif incubacao["ovoscopia"] != "":
                st.info(f"🔎 Ovoscopia registrada: {incubacao['ovoscopia']} ovos férteis")

        else:
            # Finalização da incubação
            st.warning("🟡 Período de incubação encerrado!")
            if incubacao["nascimentos"] == "":
                with st.form("form_nascimentos"):
                    max_n = int(incubacao["ovoscopia"]) if incubacao["ovoscopia"] else int(incubacao["ovos"])
                    nascimentos = st.number_input("Quantos pintinhos nasceram?", min_value=0, max_value=max_n)
                    confirmar = st.form_submit_button("✅ Registrar Nascimentos")
                    if confirmar:
                        incubacao["fim"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        incubacao["nascimentos"] = nascimentos
                        salvar_incubacao_finalizada(incubacao)
                        limpar_incubacao_ativa()
                        st.success("Incubação finalizada e registrada no histórico!")
                        st.rerun()
            else:
                st.success(f"🐣 Nascimentos registrados: {incubacao['nascimentos']} pintinhos")

        # Gráfico de dados
        st.subheader("📈 Histórico de Temperatura e Umidade")
        if os.path.exists(ARQ_DADOS):
            df = pd.read_csv(ARQ_DADOS, names=["data_hora", "temperatura", "umidade"])
            df["data_hora"] = pd.to_datetime(df["data_hora"])
            df = df.sort_values("data_hora")
            st.line_chart(df.set_index("data_hora")[["temperatura", "umidade"]])
            st.download_button("📥 Baixar dados CSV", df.to_csv(index=False), file_name="historico_temp.csv")
        else:
            st.info("Nenhum dado de temperatura recebido ainda.")

# ---------- ABA 2: HISTÓRICO DE INCUBAÇÕES ----------
with abas[1]:
    st.subheader("📜 Histórico de Incubações Finalizadas")
    historico = carregar_historico()

    if not historico:
        st.info("Nenhuma incubação finalizada ainda.")
    else:
        df_hist = pd.DataFrame(historico)
        st.dataframe(df_hist)

        st.download_button(
            label="📥 Baixar histórico JSON",
            data=json.dumps(historico, indent=2),
            file_name="incubacoes.json",
            mime="application/json"
        )
