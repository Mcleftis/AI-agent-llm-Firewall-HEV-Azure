import os
import streamlit as st
from dotenv import load_dotenv
from security_core import generate_rsa_keys, JWTManager, verify_2fa

load_dotenv()
ADMIN_PASS = os.getenv("IAM_ADMIN_PASSWORD")

st.set_page_config(page_title="Key & Token Generator", layout="centered")
st.title("Zero-Trust IAM Provider")

if not ADMIN_PASS:
    st.error("System Error: IAM_ADMIN_PASSWORD not found in .env file.")
    st.stop()

admin_password = st.text_input("Enter IAM Admin Password", type="password")
two_fa_code = st.text_input("Enter 6-digit 2FA Code")
is_human = st.checkbox("Verify you are human (Cloudflare Turnstile)")

if st.button("Generate Credentials"):
    if admin_password != ADMIN_PASS:
        st.warning("Unauthorized access.")
        st.stop()
        
    if not verify_2fa(two_fa_code):
        st.error("Invalid 2FA Code. Access Denied.")
        st.stop()

    if not is_human:
        st.warning("Please verify that you are human.")
        st.stop()

    priv_key, pub_key = generate_rsa_keys()
    
    os.makedirs('/app/vault', exist_ok=True)
    with open('/app/vault/private.pem', 'w') as f:
        f.write(priv_key)
    
    pub_clean = pub_key.replace("-----BEGIN PUBLIC KEY-----\n", "").replace("\n-----END PUBLIC KEY-----\n", "").strip()
    
    jwt_mgr = JWTManager()
    token = jwt_mgr.generate_token(username="admin", expiration_minutes=60)
    
    st.success("Credentials generated securely. Private Key locked in Vault.")
    
    st.subheader("Public Key (For external distribution)")
    st.code(pub_clean, language='text')
    
    st.subheader("JWT Token")
    st.code(token, language='text')