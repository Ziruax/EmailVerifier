import re
import random
import time
import pandas as pd
import dns.resolver
import smtplib
import streamlit as st
from collections import defaultdict
from datetime import datetime

# =============================
# CONFIG
# =============================
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

DISPOSABLE_DOMAINS = {
    "mailinator.com", "10minutemail.com", "guerrillamail.com", "yopmail.com",
    "tempmail.com", "throwawaymail.com", "fakeinbox.com", "guerrillamail.net",
    "temp-mail.org", "dispostable.com", "maildrop.cc", "getairmail.com",
    "mytemp.email", "trashmail.com", "mailforspam.com", "spamgourmet.com",
    "temporarymail.com", "moakt.com", "sharklasers.com", "grr.la",
    "mailinator2.com", "inboxalias.com", "tempinbox.com", "emailondeck.com",
    "trashymail.com", "mytrashmail.com", "mail-temporaire.fr", "temp-mail.net",
    "fake-mail.com", "discard.email", "spamdecoy.net", "tempmailaddress.com"
}

ROLE_BASED_PREFIXES = {
    "info", "support", "admin", "sales", "contact", "hr", "marketing", "ceo",
    "postmaster", "webmaster", "noreply", "no-reply", "accounts", "billing",
    "team", "office", "hello", "help", "service", "feedback"
}

MAJOR_PROVIDERS = {
    "gmail.com", "googlemail.com",
    "outlook.com", "hotmail.com", "live.com", "msn.com",
    "yahoo.com", "ymail.com", "rocketmail.com",
    "aol.com", "icloud.com", "me.com"
}

# Session caches
if "mx_cache" not in st.session_state:
    st.session_state.mx_cache = {}

# =============================
# HELPER FUNCTIONS
# =============================
@st.cache_data(ttl=7200)  # 2 hours
def get_mx(domain):
    try:
        records = dns.resolver.resolve(domain, 'MX', lifetime=6)
        mx = str(records[0].exchange).rstrip('.')
        return mx
    except Exception:
        return None

def safe_smtp_connect(mx, retries=2):
    for attempt in range(retries):
        try:
            server = smtplib.SMTP(timeout=12)
            server.connect(mx)
            server.ehlo_or_helo_if_needed()
            return server
        except Exception:
            time.sleep(1.0 if attempt == 0 else 2.0)
    return None

def smtp_check(server, email):
    try:
        server.mail("verify@local-check.com")
        code, _ = server.rcpt(email)
        return code
    except:
        return None

def is_catch_all(server, domain):
    if not server:
        return False
    for i in range(2):
        fake = f"randomtest{random.randint(100000,9999999)+i}@{domain}"
        code = smtp_check(server, fake)
        if code == 250:
            return True
        time.sleep(0.35)
    return False

def score_and_classify(email):
    if not EMAIL_REGEX.match(email):
        return 0, "invalid", "bad_syntax"

    local, domain = email.lower().split("@")
    score = 100
    reasons = set()

    # Disposable & role-based penalties (applied always)
    if domain in DISPOSABLE_DOMAINS:
        score -= 45
        reasons.add("disposable")
    if local in ROLE_BASED_PREFIXES or local.startswith(("noreply", "no-reply")):
        score -= 25
        reasons.add("role_based")

    mx = get_mx(domain)
    if not mx:
        return 0, "invalid", "no_mx_record"

    server = safe_smtp_connect(mx) if mx else None
    is_major = domain in MAJOR_PROVIDERS

    if not server:
        score -= 30
        reasons.add("smtp_connection_failed")
    else:
        code = smtp_check(server, email)

        if code == 250:
            # Clean accept → good
            pass
        elif code is None:
            score -= 25 if is_major else 35
            reasons.add("smtp_timeout_or_error")
        elif code in [421, 450, 451]:
            score -= 12 if is_major else 20
            reasons.add("soft_reject_greylisted")
        elif code in [550, 551, 553, 554]:
            score -= 60
            reasons.add("hard_reject")
        else:
            score -= 20 if is_major else 30
            reasons.add(f"smtp_response_{code}")

    # Special major provider adjustment (2026 reality)
    if is_major:
        # Forgive some connection / timeout issues
        if "smtp_connection_failed" in reasons:
            score += 15
            reasons.discard("smtp_connection_failed")
            reasons.add("major_provider_no_smtp_probe")
        if "smtp_timeout_or_error" in reasons:
            score += 12
            reasons.discard("smtp_timeout_or_error")
            reasons.add("major_provider_anti_probe")
        # Cap unrealistic high scores (they almost never give clean 250 anymore)
        if score > 92:
            score = 92

    score = max(0, min(100, score))

    # Status classification — more forgiving for major providers
    if is_major:
        if score >= 78:
            status = "valid"
        elif score >= 60:
            status = "probably_valid"
        elif score >= 40:
            status = "risky"
        else:
            status = "invalid"
    else:
        if score >= 88:
            status = "valid"
        elif score >= 65:
            status = "probably_valid"
        elif score >= 40:
            status = "risky"
        else:
            status = "invalid"

    return score, status, ",".join(sorted(reasons)) or "ok"

# =============================
# MAIN VERIFICATION
# =============================
def verify_emails(emails):
    cleaned = set(e.strip().lower() for e in emails if "@" in str(e))
    emails = [e for e in cleaned if EMAIL_REGEX.match(e)]
    total = len(emails)

    if total == 0:
        return pd.DataFrame(), "No valid emails after cleaning"

    grouped = defaultdict(list)
    for email in emails:
        grouped[email.split("@")[1]].append(email)

    results = []
    progress = st.progress(0.0)
    status_text = st.empty()
    processed = 0

    for domain, group in grouped.items():
        status_text.text(f"Checking {domain} ({len(group)} emails)")

        mx = get_mx(domain)
        server = safe_smtp_connect(mx) if mx else None
        catch_all = is_catch_all(server, domain) if server else False

        for email in group:
            score, status, reason = score_and_classify(email)

            # Catch-all override (if detected)
            if catch_all and status in ["valid", "probably_valid"]:
                score = min(score, 65)
                status = "risky"
                if "catch_all" not in reason:
                    reason += ",catch_all" if reason != "ok" else "catch_all"

            results.append({
                "email": email,
                "score": score,
                "status": status,
                "reason": reason
            })

            processed += 1
            progress.progress(processed / total)

        if server:
            try:
                server.quit()
            except:
                pass

        # Inter-domain delay — helps a lot against blocks
        time.sleep(0.9 + random.uniform(0, 0.9))  # 0.9 – 1.8 seconds

    progress.progress(1.0)
    status_text.text("Verification completed")

    df = pd.DataFrame(results)
    summary = df["status"].value_counts().to_dict()
    summary["total"] = len(df)

    return df, summary

# =============================
# STREAMLIT UI
# =============================

# =============================
# CUSTOM CSS STYLING
# =============================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

/* Global styles */
* {
    font-family: 'Inter', sans-serif !important;
}

/* Main header */
.main-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 2rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    text-align: center;
}

.main-header h1 {
    color: white !important;
    font-size: 2.8rem !important;
    font-weight: 700 !important;
    margin: 0 !important;
    text-shadow: 0 2px 4px rgba(0,0,0,0.2);
}

.main-header p {
    color: rgba(255,255,255,0.9) !important;
    font-size: 1.1rem !important;
    margin-top: 0.5rem !important;
}

/* Feature cards */
.feature-card {
    background: white;
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    border: 2px solid #e2e8f0;
    height: 100%;
}

.feature-icon {
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
}

.feature-title {
    font-weight: 600;
    color: #1a202c !important;
    font-size: 1.1rem;
    margin-bottom: 0.25rem;
}

.feature-desc {
    color: #4a5568 !important;
    font-size: 0.9rem;
}

/* Tabs styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 12px;
    background: #edf2f7;
    padding: 0.5rem;
    border-radius: 12px;
}

.stTabs [data-baseweb="tab"] {
    height: 55px;
    padding: 0 2rem;
    border-radius: 8px;
    font-weight: 600;
    font-size: 1rem;
    color: #4a5568 !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    color: white !important;
    font-weight: 600;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    border-radius: 10px !important;
    border: none !important;
    padding: 0.75rem 2rem !important;
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4) !important;
}

.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 16px rgba(102, 126, 234, 0.5) !important;
}

/* Metrics */
[data-testid="stMetric"] {
    background: white;
    padding: 1.5rem;
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    text-align: center;
    border: 2px solid #e2e8f0;
}

[data-testid="stMetricValue"] {
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    color: #1a202c !important;
}

[data-testid="stMetricLabel"] {
    font-size: 0.8rem !important;
    color: #4a5568 !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Input fields */
.stTextInput > div > div > input {
    border: 2px solid #cbd5e0 !important;
    border-radius: 10px !important;
    font-size: 1rem !important;
    color: #1a202c !important;
}

.stTextInput > div > div > input:focus {
    border-color: #667eea !important;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15) !important;
}

.stTextArea > div > div > textarea {
    border: 2px solid #cbd5e0 !important;
    border-radius: 10px !important;
    font-size: 1rem !important;
    color: #1a202c !important;
}

.stTextArea > div > div > textarea:focus {
    border-color: #667eea !important;
    box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.15) !important;
}

/* File uploader */
.stFileUploader {
    background: white;
    padding: 2.5rem;
    border-radius: 12px;
    border: 3px dashed #cbd5e0;
}

.stFileUploader:hover {
    border-color: #667eea;
    background: #f7fafc;
}

/* Alerts */
.stAlert {
    border-radius: 10px !important;
    border: 2px solid !important;
    font-weight: 500;
}

/* Section headers */
.section-header {
    font-size: 1.5rem;
    font-weight: 700;
    color: #1a202c !important;
    margin-bottom: 0.5rem;
}

.section-desc {
    color: #4a5568 !important;
    font-size: 1rem;
    margin-bottom: 1.5rem;
}

/* Status badges for results table */
.status-valid {
    background: #c6f6d5 !important;
    color: #22543d !important;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-weight: 600;
}

.status-probably_valid {
    background: #bee3f8 !important;
    color: #2c5282 !important;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-weight: 600;
}

.status-risky {
    background: #feebc8 !important;
    color: #7c2d12 !important;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-weight: 600;
}

.status-invalid {
    background: #fed7d7 !important;
    color: #742a2a !important;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-weight: 600;
}

/* Footer */
.footer {
    margin-top: 3rem;
    padding: 2rem 0;
    border-top: 2px solid #e2e8f0;
    text-align: center;
    color: #4a5568 !important;
    font-size: 0.95rem;
}

.footer strong {
    color: #667eea !important;
}

/* Info boxes */
.info-box {
    background: #ebf8ff;
    border-left: 4px solid #4299e1;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    color: #2c5282 !important;
    margin: 1rem 0;
}

/* Spinner container */
[data-testid="stSpinner"] {
    color: #667eea !important;
}
</style>
""", unsafe_allow_html=True)

st.set_page_config(page_title="Email Verifier 2026", page_icon="📧", layout="wide")

# Header with gradient background
st.markdown("""
<div class='main-header'>
    <h1>📧 Email Verifier</h1>
    <p>March 2026 Edition • Advanced Email Validation for Gmail, Outlook, Yahoo & More</p>
</div>
""", unsafe_allow_html=True)

# Feature highlights
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("""
    <div class='feature-card'>
        <div class='feature-icon'>⚡</div>
        <div class='feature-title'>Fast Processing</div>
        <div class='feature-desc'>Domain-level delays only</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown("""
    <div class='feature-card'>
        <div class='feature-icon'>🎯</div>
        <div class='feature-title'>Smart Detection</div>
        <div class='feature-desc'>Gmail/Outlook/Yahoo optimized</div>
    </div>
    """, unsafe_allow_html=True)
with col3:
    st.markdown("""
    <div class='feature-card'>
        <div class='feature-icon'>🛡️</div>
        <div class='feature-title'>Multi-Layer Check</div>
        <div class='feature-desc'>Syntax, MX, SMTP & more</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

# Tabs
tab1, tab2, tab3 = st.tabs(["📤 Batch Upload", "📝 Manual List", "🔍 Single Email"])

with tab1:
    st.markdown('<div class="section-header">📤 Upload CSV File</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">Upload a CSV file with an "email" column containing addresses to verify</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader("", type="csv", label_visibility="collapsed")

    if uploaded:
        try:
            df_in = pd.read_csv(uploaded)
            emails = df_in.get("email", pd.Series()).dropna().astype(str).tolist()
            if len(emails) > 0:
                st.markdown(f'<div class="info-box">📊 Loaded <strong>{len(emails)}</strong> emails (duplicates will be removed automatically)</div>', unsafe_allow_html=True)

            if st.button("🚀 Start Verification", type="primary", use_container_width=True):
                with st.spinner("Verifying emails..."):
                    result_df, summary = verify_emails(emails)
                    if not result_df.empty:
                        st.success("✅ Verification Complete!")
                        st.markdown("### 📈 Results Summary")
                        cols = st.columns(5)
                        cols[0].metric("Total", summary.get("total", 0))
                        cols[1].metric("Valid", summary.get("valid", 0))
                        cols[2].metric("Probably", summary.get("probably_valid", 0))
                        cols[3].metric("Risky", summary.get("risky", 0))
                        cols[4].metric("Invalid", summary.get("invalid", 0))
                        st.markdown("### 📋 Detailed Results")
                        st.dataframe(result_df[["email", "score", "status", "reason"]].sort_values("score", ascending=False), use_container_width=True, hide_index=True)
                        csv = result_df.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Download Full Report", csv, "verification_results.csv", "text/csv", type="primary", use_container_width=True)
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    else:
        st.markdown('<div class="info-box">👆 Upload a CSV file to get started</div>', unsafe_allow_html=True)

with tab2:
    st.markdown('<div class="section-header">📝 Paste Email List</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">Enter multiple email addresses, one per line. Blank lines will be ignored.</div>', unsafe_allow_html=True)
    manual_input = st.text_area("", height=250, placeholder="john@example.com\njane@company.org\nbob@test.com", label_visibility="collapsed")

    if manual_input:
        emails = [line.strip() for line in manual_input.split("\n") if line.strip()]
        if emails:
            st.markdown(f'<div class="info-box">📊 Found <strong>{len(emails)}</strong> emails to verify</div>', unsafe_allow_html=True)

    if st.button("🚀 Verify Emails", type="primary", use_container_width=True):
        if manual_input:
            emails = [line.strip() for line in manual_input.split("\n") if line.strip()]
            if emails:
                with st.spinner("Verifying emails..."):
                    result_df, summary = verify_emails(emails)
                    if not result_df.empty:
                        st.success("✅ Verification Complete!")
                        st.markdown("### 📈 Results Summary")
                        cols = st.columns(5)
                        cols[0].metric("Total", summary.get("total", 0))
                        cols[1].metric("Valid", summary.get("valid", 0))
                        cols[2].metric("Probably", summary.get("probably_valid", 0))
                        cols[3].metric("Risky", summary.get("risky", 0))
                        cols[4].metric("Invalid", summary.get("invalid", 0))
                        st.markdown("### 📋 Detailed Results")
                        st.dataframe(result_df[["email", "score", "status", "reason"]].sort_values("score", ascending=False), use_container_width=True, hide_index=True)
                        csv = result_df.to_csv(index=False).encode('utf-8')
                        st.download_button("📥 Download Full Report", csv, "verification_results.csv", "text/csv", type="primary", use_container_width=True)
            else:
                st.warning("⚠️ Please enter at least one email")

with tab3:
    st.markdown('<div class="section-header">🔍 Check Single Email</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-desc">Verify a single email address with detailed analysis</div>', unsafe_allow_html=True)
    single = st.text_input("", placeholder="name@example.com", label_visibility="collapsed")
    
    if single and st.button("🔍 Check Email", type="primary", use_container_width=True):
        score, status, reason = score_and_classify(single.strip().lower())
        status_colors = {"valid": ("#48bb78", "#f0fff4"), "probably_valid": ("#4299e1", "#ebf8ff"), "risky": ("#ed8936", "#fffaf0"), "invalid": ("#f56565", "#fff5f5")}
        color, bg = status_colors.get(status, ("#a0aec0", "#f7fafc"))
        st.markdown(f"""
        <div style='background: {bg}; padding: 2rem; border-radius: 12px; border-left: 5px solid {color}; margin: 1rem 0;'>
            <div style='font-size: 1.8rem; font-weight: 700; color: {color};'>{status.replace("_", " ").upper()}</div>
            <div style='font-size: 1.2rem; color: #4a5568; margin: 0.5rem 0;'>Score: <strong>{score}/100</strong></div>
            <div style='margin-top: 1rem; padding-top: 1rem; border-top: 1px solid rgba(0,0,0,0.1); color: #718096;'>{reason}</div>
        </div>
        """, unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("<div class='footer'><strong>Email Verifier 2026</strong> • Gmail/Outlook/Yahoo optimized • Catch-all detection enabled</div>", unsafe_allow_html=True)
