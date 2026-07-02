import requests
import json
import csv
import os
import random
from datetime import datetime
from dotenv import load_dotenv  # Αν δεν το έχεις: pip install python-dotenv

# --- Φόρτωση Environment Variables ---
load_dotenv() 

# ΠΑΙΡΝΕΙ ΤΟ LINK ΑΠΟ ΤΟ ΚΡΥΦΟ ΑΡΧΕΙΟ .env
WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Έλεγχος αν βρέθηκε το Link (για να μην σκάει με περίεργα errors)
if not WEBHOOK_URL:
    print("❌ ERROR: Δεν βρέθηκε το DISCORD_WEBHOOK_URL.")
    print("   -> Φτιάξε ένα αρχείο .env και βάλε μέσα: DISCORD_WEBHOOK_URL=https://discord...")
    exit(1)

# --- 1. HYBRID CONTEXT MAPPING & CVEs ---
ASSET_MAP = {
    # CAN Bus Assets
    "0x01A": {"System": "Braking System (ABS)", "Risk": "CRITICAL", "Type": "CAN_BUS", "CVE": "CVE-2026-1234"},
    "0x1B4": {"System": "Steering Control", "Risk": "CRITICAL", "Type": "CAN_BUS", "CVE": "CVE-2026-5588"},
    
    # Network Assets (Target Ports)
    "22":   {"System": "SSH Remote Access", "Risk": "HIGH", "Type": "NETWORK", "Proto": "TCP", "CVE": "CVE-2024-4567"},
    "80":   {"System": "Infotainment Web UI", "Risk": "MEDIUM", "Type": "NETWORK", "Proto": "TCP", "CVE": "N/A"},
    "443":  {"System": "Secure Diagnostics API", "Risk": "LOW", "Type": "NETWORK", "Proto": "TCP", "CVE": "N/A"},
    "502":  {"System": "Modbus/TCP (Industrial)", "Risk": "CRITICAL", "Type": "NETWORK", "Proto": "TCP", "CVE": "N/A"}
}

# --- 2. PROCESS HIERARCHY (Διαδρομή Αρχείων Επίθεσης) ---
PROCESS_TREES = [
    "services.exe -> svchost.exe -> malicious_thread.dll",
    "init -> bluetooth_stack.d -> DRIVER_PHONE",
    "explorer.exe -> chrome.exe -> suspicious_script.js",
    "wininit.exe -> lsass.exe -> credential_harvester.exe"
]

# --- PATH CONFIG ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EVIDENCE_DIR_NAME = "evidence_reports_cybersecurity"
FULL_EVIDENCE_PATH = os.path.join(BASE_DIR, EVIDENCE_DIR_NAME)
CSV_FILE_PATH = os.path.join(FULL_EVIDENCE_PATH, 'forensics_report.csv')

def get_context(target_id):
    return ASSET_MAP.get(target_id, {"System": "Unknown Service", "Risk": "UNKNOWN", "Type": "GENERIC", "Proto": "N/A", "CVE": "N/A"})

def save_forensic_evidence(target_id, attack_type, payload_data, context, source_info, dest_port, status_data):
    # Δημιουργία φακέλου αν δεν υπάρχει
    if not os.path.exists(FULL_EVIDENCE_PATH):
        try: os.makedirs(FULL_EVIDENCE_PATH)
        except: return

    file_exists = os.path.isfile(CSV_FILE_PATH)
    try:
        with open(CSV_FILE_PATH, 'a', newline='', encoding='utf-8') as csvfile:
            # Στήλες για Forensics Report
            fieldnames = ['Timestamp', 'Target_ID', 'Dest_Port', 'System', 'Risk_Level', 'Attack_Type', 'Source_Info', 'Mitigation', 'Validation', 'Patch_Status', 'Process_Tree']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow({
                'Timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'Target_ID': target_id,
                'Dest_Port': dest_port,
                'System': context['System'],
                'Risk_Level': context['Risk'],
                'Attack_Type': attack_type,
                'Source_Info': source_info,
                'Mitigation': 'BLOCKED',
                'Validation': status_data['validation'],
                'Patch_Status': status_data['patch'],
                'Process_Tree': status_data['hierarchy']
            })
            print(f"💾 [FORENSICS] {context['Type']} Evidence saved to CSV.")
    except Exception as e:
        print(f"⚠️ Failed to save forensics: {e}")

def send_critical_alert(target_id, attack_type, engine_source="RUST_FIREWALL", mitre_id="T1046", payload_data="N/A", is_false_positive=False):
    # 1. Enrich Data
    context = get_context(target_id)
    
    # 2. Logic για Ports vs CAN IDs
    if context['Type'] == "NETWORK":
        attacker_ip = f"192.168.1.{random.randint(50, 200)}"
        attacker_port = random.randint(1024, 65535)
        dest_port = target_id
        source_info = f"{attacker_ip}:{attacker_port}"
        target_display = f"LocalHost:{dest_port} ({context['Proto']})"
        icon = "🌐"
        
    else:
        source_info = "ECU_Gateway (Internal)"
        dest_port = "N/A"
        target_display = f"CAN ID: `{target_id}`"
        icon = "🚗"
        mitre_id = "T1565" # ID για Manipulation

    # --- 3. SENIOR FEATURES (Validation, Patching, Hierarchy) ---
    status_data = {
        "validation": "❌ FALSE POSITIVE" if is_false_positive else "✅ TRUE POSITIVE",
        "patch": f"🛠️ PATCH APPLIED ({context['CVE']})" if context['CVE'] != "N/A" else "✅ SYSTEM SECURE",
        "hierarchy": random.choice(PROCESS_TREES)
    }

    # 4. Save Forensics locally
    save_forensic_evidence(target_id, attack_type, payload_data, context, source_info, dest_port, status_data)
    
    # 5. Alert Construction (Colors)
    color_map = {"CRITICAL": 15548997, "HIGH": 15158332, "MEDIUM": 15105570, "LOW": 3066993}
    alert_color = 3447003 if is_false_positive else color_map.get(context['Risk'], 9807270)
    
    # 6. Discord Payload
    discord_payload = {
        "username": "HEV Security Sentinel",
        "avatar_url": "https://i.imgur.com/8n9Y99f.png",
        "embeds": [{
            "title": f"{icon} {status_data['validation']} | {context['System']}",
            "description": f"**Detection:** Traffic Anomaly Detected & Blocked by {engine_source}.",
            "color": alert_color,
            "fields": [
                {"name": "🕵️ Attacker Source", "value": f"`{source_info}`", "inline": True},
                {"name": "🎯 Target Destination", "value": f"`{target_display}`", "inline": True},
                {"name": "⚖️ Risk Level", "value": f"**{context['Risk']}**", "inline": True},
                
                {"name": "⚔️ Attack Vector", "value": f"*{attack_type}*", "inline": True},
                {"name": "🦅 MITRE ATT&CK", "value": f"[`{mitre_id}`](https://attack.mitre.org/techniques/{mitre_id}/)", "inline": True},
                {"name": "🛡️ Mitigation", "value": "✅ **CONNECTION DROPPED**" if not is_false_positive else "⚠️ **ALERT SUPPRESSED**", "inline": True},

                {"name": "🌳 Attack Path (Process Hierarchy)", "value": f"```mermaid\n{status_data['hierarchy']}```", "inline": False},
                
                {"name": "🩹 Vulnerability Patching", "value": status_data['patch'], "inline": True},
                {"name": "💾 Forensic Evidence", "value": f"Saved to `{EVIDENCE_DIR_NAME}/`", "inline": True},
                
                {"name": "⏰ Timestamp", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "inline": False}
            ],
            "footer": {"text": "SOC Intelligence System | Network & CAN Security"}
        }]
    }

    # 7. SEND TO DISCORD (ΔΙΟΡΘΩΜΕΝΟ)
    try:
        # Χρησιμοποιούμε τη σωστή μεταβλητή WEBHOOK_URL
        response = requests.post(WEBHOOK_URL, data=json.dumps(discord_payload), headers={'Content-Type': 'application/json'})
        
        if response.status_code == 204:
            print(f"🚀 [SOC] Alert dispatched for {context['System']}.")
        else:
            print(f"⚠️ [SOC] Discord Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"[!] Alert failed: {e}")

# --- MAIN DEMO ---
if __name__ == "__main__":
    print(f"--- 🏁 STARTING SENIOR SOC DEMO 🏁 ---")
    
    # Σενάριο 1: Network Attack (SSH Brute Force) - TRUE POSITIVE
    print("\n[+] Detecting Network Attack...")
    send_critical_alert("22", "SSH Brute Force", "NIDS_ENGINE", "T1110", "AUTH_FAIL", is_false_positive=False)
    
    # Σενάριο 2: CAN Bus Attack (Braking System) - TRUE POSITIVE
    print("\n[+] Detecting Vehicle Bus Attack...")
    send_critical_alert("0x01A", "CAN Bus Injection", "RUST_FIREWALL", "T1565", "FF 00", is_false_positive=False)