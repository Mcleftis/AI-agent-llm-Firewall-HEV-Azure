import os
import platform
import ctypes
import time
import uuid
import streamlit as st
from security.security_core import sign_payload, verify_signature, JWTManager
from security.llm_firewall import query_llama_secure

st.set_page_config(page_title="HEV Security Gateway", layout="wide")

lib_ext = '.dll' if platform.system() == 'Windows' else '.so'
firewall_lib_path = os.path.join(os.path.dirname(__file__), 'cpp_core', 'cpp_firewall', f"firewall{lib_ext}")

try:
    cpp_firewall = ctypes.CDLL(firewall_lib_path)
    cpp_firewall.validate_api_command.argtypes = [ctypes.c_char_p]
    cpp_firewall.validate_api_command.restype = ctypes.c_int
    firewall_loaded = True
except OSError:
    firewall_loaded = False
    st.sidebar.error("Hardware Firewall is offline.")

jwt_mgr = JWTManager()
st.sidebar.header("Authentication")
token_input = st.sidebar.text_input("JWT Token", type="password")
pub_key = st.sidebar.text_area("Public Key (PEM format)")

if not token_input:
    st.warning("Provide JWT Token to access the system.")
    st.stop()

is_valid, payload_or_error = jwt_mgr.verify_token(token_input)
if not is_valid:
    st.sidebar.error(payload_or_error)
    st.stop()

user_prompt = st.text_input("Command AI:", placeholder="e.g., Please turn on the eco mode.")

if st.button("Send to AI"):
    if not pub_key:
        st.error("Public Key required for signature verification.")
        st.stop()

    if not firewall_loaded:
        st.error("Cannot proceed. Hardware Firewall is offline.")
        st.stop()

    llm_result = query_llama_secure(user_prompt)
    
    if "Blocked:" in llm_result:
        st.error(llm_result)
        st.stop()
        
    st.info(llm_result)
    action = llm_result.split(": ")[-1]

    payload = {
        "command": action, 
        "user": payload_or_error.get('sub'),
        "timestamp": time.time(),
        "nonce": str(uuid.uuid4())
    }
    
    vault_path = '/app/vault/private.pem'
    if not os.path.exists(vault_path):
        st.error("Private key vault not found. Generate keys first.")
        st.stop()
        
    with open(vault_path, 'r') as f:
        priv_key_pem = f.read()
    
    signature = sign_payload(priv_key_pem, payload)
    
    if not signature:
        st.error("Cryptographic signing failed. Vault access denied.")
        st.stop()
        
    is_verified = verify_signature(pub_key, payload, signature)
    
    if is_verified:
        cpp_status = cpp_firewall.validate_api_command(action.encode('utf-8'))
        if cpp_status == 1:
            st.success(f"Command '{action}' executed securely.")
        else:
            st.error("Hardware Firewall Blocked.")
    else:
        st.error("Verification Failed: Invalid Signature or Replay Attack Detected.")