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
st.set_page_config(page_title="Email Verifier 2026", layout="wide")
st.title("📧 Email Verifier (March 2026 Edition)")
st.caption("Better handling of Gmail / Outlook / Yahoo • Delay between domains only")

tab1, tab2 = st.tabs(["Batch", "Single"])

with tab1:
    uploaded = st.file_uploader("Upload CSV with 'email' column", type="csv")

    if uploaded:
        try:
            df_in = pd.read_csv(uploaded)
            emails = df_in.get("email", pd.Series()).dropna().astype(str).tolist()
            st.info(f"Loaded {len(emails)} emails (will remove duplicates)")

            if st.button("Start Verification", type="primary"):
                with st.spinner("Verifying..."):
                    result_df, summary = verify_emails(emails)

                    if not result_df.empty:
                        st.success("Done!")

                        cols = st.columns(5)
                        cols[0].metric("Total", summary.get("total", 0))
                        cols[1].metric("Valid", summary.get("valid", 0))
                        cols[2].metric("Probably", summary.get("probably_valid", 0))
                        cols[3].metric("Risky", summary.get("risky", 0))
                        cols[4].metric("Invalid", summary.get("invalid", 0))

                        st.dataframe(
                            result_df[["email", "score", "status", "reason"]]
                            .sort_values("score", ascending=False),
                            use_container_width=True,
                            hide_index=True
                        )

                        csv = result_df.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            "↓ Download full report",
                            csv,
                            "verification_results.csv",
                            "text/csv",
                            type="primary"
                        )
        except Exception as e:
            st.error(f"File reading error: {str(e)}")

with tab2:
    single = st.text_input("Single email")
    if single and st.button("Check"):
        score, status, reason = score_and_classify(single.strip().lower())
        color_map = {"valid": "🟢", "probably_valid": "🔵", "risky": "🟠", "invalid": "🔴"}
        icon = color_map.get(status, "⚪")
        st.markdown(f"**{icon} {status.upper()}**  –  **{score}/100**  \nReason: {reason}")

st.caption("• Gmail/Outlook/Yahoo get special treatment (they block probes)  \n• Small delay between domains only  \n• Catch-all detection included")
