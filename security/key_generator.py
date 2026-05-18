import os
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from pathlib import Path


env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from security_core import generate_rsa_keys, JWTManager, verify_2fa

ADMIN_PASS = os.getenv("IAM_ADMIN_PASSWORD")

st.set_page_config(page_title="Key & Token Generator", layout="centered")
st.title("Zero-Trust IAM Provider")


if not ADMIN_PASS:
    st.error(f"System Error: IAM_ADMIN_PASSWORD not found. Η Python ψάχνει το αρχείο εδώ: {env_path}. Βεβαιώσου ότι δεν λέγεται .env.txt")
    st.stop()

admin_password = st.text_input("Enter IAM Admin Password", type="password")
two_fa_code = st.text_input("Enter 6-digit 2FA Code")

st.markdown("### Bot Verification (Cloudflare Turnstile)")

turnstile_html = """
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
<div class="cf-turnstile" data-sitekey="1x00000000000000000000AA"></div>
"""
components.html(turnstile_html, height=80)
is_human = st.checkbox("I confirm the Turnstile passed")

if st.button("Generate Credentials"):
    if admin_password != ADMIN_PASS:
        st.error("Unauthorized access. Wrong Password.")
        st.stop()
        
    if not verify_2fa(two_fa_code):
        st.error("Invalid 2FA Code. Access Denied.")
        st.stop()

    if not is_human:
        st.warning("Please verify that you are human.")
        st.stop()

    priv_key, pub_key = generate_rsa_keys()
    
    
    vault_dir = Path(__file__).parent.parent / 'vault'
    vault_dir.mkdir(exist_ok=True)
    vault_path = vault_dir / 'private.pem'
    
    with open(vault_path, 'w') as f:
        f.write(priv_key)
    
    pub_clean = pub_key.replace("-----BEGIN PUBLIC KEY-----\n", "").replace("\n-----END PUBLIC KEY-----\n", "").strip()
    
    jwt_mgr = JWTManager()
    token = jwt_mgr.generate_token(username="admin", expiration_minutes=60)
    
    st.success("Credentials generated securely. Private Key locked in Vault.")
    
    st.subheader("Public Key (For external distribution)")
    st.code(pub_clean, language='text')
    
    st.subheader("JWT Token")
    st.code(token, language='text')