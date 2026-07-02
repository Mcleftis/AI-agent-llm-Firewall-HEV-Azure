import os
import streamlit as st
from dotenv import load_dotenv
from pathlib import Path
from security_core import generate_rsa_keys, JWTManager, verify_2fa


env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


raw_pass = os.getenv("IAM_ADMIN_PASSWORD")
ADMIN_PASS = raw_pass.strip().replace('"', '').replace("'", "") if raw_pass else None

st.set_page_config(page_title="Key Generator", layout="centered")
st.title("Zero-Trust IAM Provider")

if not ADMIN_PASS:
    st.error("System Error: Το IAM_ADMIN_PASSWORD δεν βρέθηκε στο .env!")
    st.stop()




admin_password = st.text_input("Enter IAM Admin Password", type="password")
two_fa_code = st.text_input("Enter 6-digit 2FA Code")


if st.button("Generate Credentials"):
    
   
    if admin_password != ADMIN_PASS:
        st.error(f"ΛΑΘΟΣ ΚΩΔΙΚΟΣ! Εσύ έγραψες '{admin_password}', αλλά το σύστημα περιμένει '{ADMIN_PASS}'")
        st.stop()
        
    
    if not verify_2fa(two_fa_code):
        st.error("ΛΑΘΟΣ 2FA! Access Denied.")
        st.stop()

    
    priv_key, pub_key = generate_rsa_keys()
    
    vault_dir = Path(__file__).parent.parent / 'vault'
    vault_dir.mkdir(exist_ok=True)
    
    with open(vault_dir / 'private.pem', 'w') as f:
        f.write(priv_key)
    
    
    jwt_mgr = JWTManager()
    token = jwt_mgr.generate_token(username="admin", expiration_minutes=60)
    
    
    st.success("ΜΠΗΚΕΣ! Κλειδιά δημιουργήθηκαν.")
    st.code(pub_key, language='text')
    st.code(token, language='text')