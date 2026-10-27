"""Meterless connection setup and a plain-text chat check; no audit-provider switch."""
from pathlib import Path
import streamlit as st
from hydroguard.ai.meterless import (RuntimeSettings, MeterlessProvider, MeterlessError,
                                    parse_connection, auto_detect)


def render():
    st.title("HydroGuard - Meterless Runtime")
    st.caption("Connection setup and chat check. This does not configure the Evidence Critic or establish a Nemotron model identity.")
    settings = RuntimeSettings()
    try:
        connection = settings.load()
    except MeterlessError as error:
        st.error(str(error)); return
    # Use a password widget because a pasted connect URL can contain a secret fragment.
    address = st.text_input("Runtime URL or connect link", value=connection.base_url, type="password")
    token = st.text_input("Runtime token", type="password", help="Paste the real token or import stateDir/proxy-token. rt-local is not valid.")
    state_dir = st.text_input("Runtime stateDir (optional)")
    status = st.session_state.get("meterless_status")
    try:
        if st.button("Import proxy-token"):
            connection = settings.from_state_dir(Path(state_dir), address)
            status = MeterlessProvider(connection).probe()
        if st.button("Connect"):
            connection = parse_connection(address,token or connection.token)
            settings.save(connection)
            status = MeterlessProvider(connection).probe()
        if st.button("Auto Detect"):
            found,status = auto_detect(settings,token or connection.token)
            if found:
                connection = found
        if status is not None:
            st.session_state["meterless_status"] = status
            st.write("Status: " + status.state)
            st.caption("Runtime address: " + settings.load().base_url)
            if status.requires_token:
                st.warning("unauthorized - paste the Runtime token in the masked field above, then Connect.")
        if status and status.state == "online":
            model = st.selectbox("Routing mode",status.models,index=status.models.index("meterless/auto") if "meterless/auto" in status.models else 0)
            prompt = st.text_area("Plain text request")
            if st.button("Send"):
                with st.spinner("Waiting for Runtime (up to 180 seconds)…"):
                    st.write(MeterlessProvider(settings.load()).chat(prompt,model))
    except MeterlessError as error:
        st.error(str(error))
