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

# Session state initialization
if "mx_cache" not in st.session_state:
    st.session_state.mx_cache = {}
if "last_run" not in st.session_state:
    st.session_state.last_run = None

# =============================
# HELPER FUNCTIONS
# =============================
@st.cache_data(ttl=3600)  # Cache MX for 1 hour
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
            time.sleep(1.2)
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
        time.sleep(0.4)
    return False

def score_and_classify(email, server=None):
    if not EMAIL_REGEX.match(email):
        return 0, "invalid", "bad_syntax"

    local, domain = email.lower().split("@")
    score = 100
    reasons = set()

    if domain in DISPOSABLE_DOMAINS:
        score -= 45
        reasons.add("disposable")

    if local in ROLE_BASED_PREFIXES or local.startswith(("noreply", "no-reply")):
        score -= 25
        reasons.add("role_based")

    mx = get_mx(domain)
    if not mx:
        return 0, "invalid", "no_mx_record"

    if not server:
        score -= 35
        reasons.add("smtp_connect_failed")
    else:
        code = smtp_check(server, email)
        if code == 250:
            pass  # great
        elif code is None:
            score -= 30
            reasons.add("smtp_timeout_or_error")
        elif code in [421, 450, 451]:
            score -= 15
            reasons.add("soft_reject_greylisted")
        elif code in [550, 551, 553, 554]:
            score -= 60
            reasons.add("hard_reject")
        else:
            score -= 25
            reasons.add(f"smtp_code_{code}")

    score = max(0, min(100, score))

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
# MAIN VERIFICATION LOGIC
# =============================
def verify_emails(emails):
    if not emails:
        return pd.DataFrame(), "No valid emails found"

    # Clean & deduplicate
    cleaned = set()
    for e in emails:
        e = str(e).strip().lower()
        if "@" in e and EMAIL_REGEX.match(e):
            cleaned.add(e)
    emails = sorted(list(cleaned))
    total = len(emails)

    if total == 0:
        return pd.DataFrame(), "No valid emails after cleaning"

    grouped = defaultdict(list)
    for email in emails:
        domain = email.split("@")[1]
        grouped[domain].append(email)

    results = []
    progress = st.progress(0.0)
    status_text = st.empty()

    processed = 0

    for domain, group_emails in grouped.items():
        status_text.text(f"Processing {domain} ({len(group_emails)} emails)")

        mx = get_mx(domain)
        server = safe_smtp_connect(mx) if mx else None

        catch_all = False
        if server:
            catch_all = is_catch_all(server, domain)

        for email in group_emails:
            if catch_all:
                score, status, reason = score_and_classify(email, None)
                score = min(score, 58)
                reason = reason + ",catch_all" if reason != "ok" else "catch_all"
                if status == "valid":
                    status = "probably_valid"
            else:
                score, status, reason = score_and_classify(email, server)

            results.append({
                "email": email,
                "score": score,
                "status": status,
                "reason": reason,
                "domain": email.split("@")[1]
            })

            processed += 1
            progress.progress(processed / total)

        if server:
            try:
                server.quit()
            except:
                pass

        # Smart inter-domain delay (key to robustness)
        time.sleep(0.8 + random.uniform(0, 0.8))  # 0.8–1.6s

    progress.progress(1.0)
    status_text.text("Verification finished!")

    df = pd.DataFrame(results)

    # Nice summary
    summary = df["status"].value_counts().to_dict()
    summary["total"] = len(df)

    return df, summary

# =============================
# STREAMLIT APP
# =============================
st.set_page_config(page_title="Email Verifier • Robust", layout="wide")
st.title("📧 Email Verifier (Robust Edition)")
st.caption(f"Last improved • {datetime.now().strftime('%Y-%m')} • Delay between domains only")

tab1, tab2 = st.tabs(["Batch Verify", "Quick Check"])

with tab1:
    uploaded = st.file_uploader("Upload CSV (must have 'email' column)", type=["csv"])

    if uploaded:
        try:
            df_in = pd.read_csv(uploaded)
            if "email" not in df_in.columns:
                st.error("File must contain an 'email' column")
            else:
                emails = df_in["email"].dropna().astype(str).tolist()
                st.info(f"Found {len(emails)} email entries (will deduplicate)")

                col1, col2 = st.columns([1, 4])
                with col1:
                    if st.button("Start Verification", type="primary", use_container_width=True):
                        with st.spinner("Working... (this may take a few minutes for large lists)"):
                            result_df, summary = verify_emails(emails)

                            if not result_df.empty:
                                st.success("Done!")
                                st.subheader("Summary")
                                cols = st.columns(5)
                                cols[0].metric("Total", summary.get("total", 0))
                                cols[1].metric("Valid", summary.get("valid", 0), delta_color="normal")
                                cols[2].metric("Probably", summary.get("probably_valid", 0))
                                cols[3].metric("Risky", summary.get("risky", 0))
                                cols[4].metric("Invalid", summary.get("invalid", 0))

                                st.subheader("Results")
                                st.dataframe(
                                    result_df[["email", "score", "status", "reason"]].sort_values("score", ascending=False),
                                    use_container_width=True,
                                    hide_index=True
                                )

                                csv = result_df.to_csv(index=False).encode('utf-8')
                                st.download_button(
                                    "Download Full CSV",
                                    csv,
                                    "email_verification_results.csv",
                                    "text/csv",
                                    key="download_full",
                                    type="primary"
                                )
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")

with tab2:
    single = st.text_input("Single email check")
    if single and st.button("Verify Now"):
        score, status, reason = score_and_classify(single.strip().lower())
        color = {"valid": "green", "probably_valid": "blue", "risky": "orange", "invalid": "red"}.get(status, "grey")
        st.markdown(f"**{status.upper()}** – Score: **{score}/100**  \nReason: {reason}", unsafe_allow_html=True)

st.markdown("---")
st.caption("• Small delay between domains only (helps avoid blocks)  \n• Retries on connect  \n• Catch-all detection  \n• Deduplication & better regex")
