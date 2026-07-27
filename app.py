import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
import json
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client, Client

# ---------------------------------------------------------
# PAGE CONFIGURATION & MATTE UI STYLING
# ---------------------------------------------------------
st.set_page_config(page_title="Fleet Command V2", page_icon="🏎️", layout="wide", initial_sidebar_state="expanded")

# Injecting Custom CSS for a sleek, matte dark/red dashboard aesthetic
st.markdown("""
<style>
    /* Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        border-left: 4px solid #E50914; /* Sleek Red Accent */
    }
    div[data-testid="metric-container"] > div {
        color: #FFFFFF;
    }
    /* Headers & Text */
    h1, h2, h3 {
        color: #F5F5F5 !important;
        font-weight: 600;
    }
    /* Expander styling */
    .streamlit-expanderHeader {
        background-color: #1E1E1E !important;
        border-radius: 5px;
    }
    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; 
        font-weight: 600; 
        font-size: 16px; 
        background-color: transparent;
        border-radius: 5px 5px 0px 0px;
    }
    .stTabs [aria-selected="true"] {
        border-bottom: 3px solid #E50914 !important;
        color: #E50914 !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# SUPABASE CLOUD CONNECTION
# ---------------------------------------------------------
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception:
        return None

supabase = init_supabase()

def clean_for_json(obj):
    if pd.api.types.is_scalar(obj):
        if pd.isna(obj): return None
        if isinstance(obj, (float, np.float64, np.float32)) and (np.isnan(obj) or np.isinf(obj)): return None
        return obj
    if isinstance(obj, dict): return {str(k): clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list): return [clean_for_json(v) for v in obj]
    return obj

def load_cloud_state():
    if not supabase: return None
    try:
        res = supabase.table("app_state").select("data").eq("id", 1).execute()
        if res.data and len(res.data) > 0: return res.data[0]["data"]
    except Exception: pass
    return None

def save_cloud_state():
    if not supabase: return False, "DB not connected"
    try:
        trips_list = []
        if "trips_data" in st.session_state and not st.session_state.trips_data.empty:
            df_temp = st.session_state.trips_data.copy()
            for col in ["Start Date", "End Date"]:
                if col in df_temp.columns:
                    df_temp[col] = pd.to_datetime(df_temp[col]).dt.strftime("%Y-%m-%d")
            df_temp = df_temp.where(pd.notnull(df_temp), None)
            trips_list = df_temp.to_dict(orient="records")

        raw_payload = {
            "host_a": st.session_state.get("host_a_val", "AH"),
            "host_b": st.session_state.get("host_b_val", "SA"),
            "host_c": st.session_state.get("host_c_val", "OM"),
            "default_clean_fee": st.session_state.get("clean_fee_val", 25.0),
            "default_delivery_fee": st.session_state.get("delivery_fee_val", 30.0),
            "vehicles": st.session_state.get("vehicles", []),
            "cleaning_logs": st.session_state.get("cleaning_logs", []),
            "expense_logs": st.session_state.get("expense_logs", []),
            "delivery_logs": st.session_state.get("delivery_logs", []),
            "trips_data": trips_list,
        }
        state_payload = clean_for_json(raw_payload)
        supabase.table("app_state").upsert({"id": 1, "data": state_payload}, on_conflict="id").execute()
        return True, ""
    except Exception as e:
        return False, str(e)

# Initialize Edit State
if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = {"type": None, "index": None}

# Load state from cloud once at startup
if "cloud_loaded" not in st.session_state:
    cloud_data = load_cloud_state() or {}
    st.session_state.host_a_val = cloud_data.get("host_a", "AH")
    st.session_state.host_b_val = cloud_data.get("host_b", "SA")
    st.session_state.host_c_val = cloud_data.get("host_c", "OM")
    st.session_state.clean_fee_val = float(cloud_data.get("default_clean_fee", 25.0))
    st.session_state.delivery_fee_val = float(cloud_data.get("default_delivery_fee", 30.0))
    st.session_state.vehicles = cloud_data.get("vehicles", [])
    st.session_state.cleaning_logs = cloud_data.get("cleaning_logs", [])
    st.session_state.expense_logs = cloud_data.get("expense_logs", [])
    st.session_state.delivery_logs = cloud_data.get("delivery_logs", [])
    
    saved_trips = cloud_data.get("trips_data", [])
    if saved_trips:
        df_restored = pd.DataFrame(saved_trips)
        for col in ["Start Date", "End Date"]:
            if col in df_restored.columns:
                df_restored[col] = pd.to_datetime(df_restored[col]).dt.date
        st.session_state.trips_data = df_restored
    else:
        st.session_state.trips_data = pd.DataFrame()
        
    st.session_state.cloud_loaded = True

hosts = [st.session_state.host_a_val, st.session_state.host_b_val, st.session_state.host_c_val]

if not st.session_state.vehicles:
    st.session_state.vehicles = [
        {"id": 0, "name": "Dodge Journey", "splits": {hosts[0]: 50, hosts[1]: 50, hosts[2]: 0}},
        {"id": 1, "name": "Kia Forte", "splits": {hosts[0]: 0, hosts[1]: 0, hosts[2]: 100}}
    ]

guest_list = ["General / Unspecified"]
if not st.session_state.trips_data.empty and "Guest" in st.session_state.trips_data.columns:
    guests = sorted([str(g) for g in st.session_state.trips_data["Guest"].dropna().unique() if str(g).strip()])
    guest_list.extend(guests)

# ---------------------------------------------------------
# SIDEBAR NAVIGATION & GLOBAL FILTERS
# ---------------------------------------------------------
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Turo_logo.svg/1024px-Turo_logo.svg.png", width=150)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

nav_selection = st.sidebar.radio("NAVIGATION", [
    "📊 Command Center", 
    "🧑‍✈️ Host Performance", 
    "🛠️ Operations Desk", 
    "⚙️ Settings & Data"
])

st.sidebar.markdown("---")

filtered_df = pd.DataFrame()
if not st.session_state.trips_data.empty:
    st.sidebar.subheader("🔍 Global Filters")
    min_d = st.session_state.trips_data["Start Date"].dropna().min()
    max_d = st.session_state.trips_data["End Date"].dropna().max()
    
    selected_dates = st.sidebar.date_input("Date Range", [min_d, max_d])
    
    car_options = ["All Vehicles"] + list(st.session_state.trips_data["Vehicle"].unique())
    selected_car = st.sidebar.selectbox("Vehicle", car_options)
    
    status_options = ["All Statuses"] + list(st.session_state.trips_data["Status"].unique())
    selected_status = st.sidebar.selectbox("Trip Status", status_options)

    filtered_df = st.session_state.trips_data.copy()
    if len(selected_dates) == 2:
        filtered_df = filtered_df[(filtered_df["Start Date"] >= selected_dates[0]) & (filtered_df["Start Date"] <= selected_dates[1])]
    if selected_car != "All Vehicles":
        filtered_df = filtered_df[filtered_df["Vehicle"] == selected_car]
    if selected_status != "All Statuses":
        filtered_df = filtered_df[filtered_df["Status"] == selected_status]

st.sidebar.markdown("---")
if st.sidebar.button("💾 Save State to Cloud", type="primary", use_container_width=True):
    success, msg = save_cloud_state()
    if success: st.sidebar.success("Cloud Synced!")
    else: st.sidebar.error(f"Failed: {msg}")

# ---------------------------------------------------------
# CORE DATA PROCESSING (Runs globally so all pages have access)
# ---------------------------------------------------------
host_totals = {h: {"Pool Split": 0.0, "Cleaning": 0.0, "Delivery": 0.0, "Reimbursed": 0.0, "Tasks_Count": 0} for h in hosts}
vehicle_task_deductions = {}

for log in st.session_state.cleaning_logs:
    v, amt, h = log.get("Vehicle", "General / Unspecified"), log.get("Amount ($)", 0.0), log.get("Host")
    vehicle_task_deductions[v] = vehicle_task_deductions.get(v, 0.0) + amt
    if h in host_totals:
        host_totals[h]["Tasks_Count"] += 1
        host_totals[h]["Cleaning"] += amt

for log in st.session_state.delivery_logs:
    v, amt, h = log.get("Vehicle", "General / Unspecified"), log.get("Amount ($)", 0.0), log.get("Host")
    vehicle_task_deductions[v] = vehicle_task_deductions.get(v, 0.0) + amt
    if h in host_totals:
        host_totals[h]["Tasks_Count"] += 1
        host_totals[h]["Delivery"] += amt

for log in st.session_state.expense_logs:
    v, amt, h = log.get("Vehicle", "General / Unspecified"), log.get("Amount ($)", 0.0), log.get("Host")
    vehicle_task_deductions[v] = vehicle_task_deductions.get(v, 0.0) + amt
    if h in host_totals:
        host_totals[h]["Reimbursed"] += amt

total_tasks_cost = sum(vehicle_task_deductions.values())
vehicle_gross_totals = filtered_df.groupby("Vehicle")["Net Total"].sum().to_dict() if not filtered_df.empty else {}

for v_config in st.session_state.vehicles:
    v_name = v_config["name"]
    v_gross = vehicle_gross_totals.get(v_name, 0.0)
    v_deduction = vehicle_task_deductions.get(v_name, 0.0)
    v_net_pool = max(0.0, v_gross - v_deduction)
    for h, pct in v_config["splits"].items():
        if h in host_totals:
            host_totals[h]["Pool Split"] += v_net_pool * (pct / 100.0)

general_deduction = vehicle_task_deductions.get("General Fleet", 0.0) + vehicle_task_deductions.get("General / Unspecified", 0.0)
if general_deduction > 0:
    for h in hosts: host_totals[h]["Pool Split"] -= (general_deduction / len(hosts))

for h in hosts:
    host_totals[h]["Net Final Payout"] = host_totals[h]["Pool Split"] + host_totals[h]["Cleaning"] + host_totals[h]["Delivery"] + host_totals[h]["Reimbursed"]

# ---------------------------------------------------------
# PAGE 1: COMMAND CENTER
# ---------------------------------------------------------
if nav_selection == "📊 Command Center":
    st.header("Executive Overview")
    
    if filtered_df.empty:
        st.info("No data available for the selected filters. Please upload a CSV in 'Settings & Data'.")
    else:
        # Top KPI Metrics
        total_gross = filtered_df["Net Total"].sum()
        total_payout_pool = sum(h["Net Final Payout"] for h in host_totals.values())
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Gross Revenue", f"${total_gross:,.2f}")
        m2.metric("Total Expenses & Tasks", f"${total_tasks_cost:,.2f}")
        m3.metric("Net Host Pool", f"${total_payout_pool:,.2f}")
        m4.metric("Completed Trips", len(filtered_df[filtered_df["Status"].str.lower() == "completed"]))
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Charts Row
        c1, c2 = st.columns([3, 2])
        
        with c1:
            st.subheader("Revenue by Vehicle")
            v_rev = filtered_df.groupby("Vehicle")["Net Total"].sum().reset_index()
            fig_bar = px.bar(v_rev, x="Vehicle", y="Net Total", text="Net Total", color="Vehicle", 
                             color_discrete_sequence=px.colors.qualitative.Set2, template="plotly_dark")
            fig_bar.update_traces(texttemplate='$%{text:,.2f}', textposition='outside')
            fig_bar.update_layout(margin=dict(t=30, b=0, l=0, r=0), showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with c2:
            st.subheader("Host Payout Distribution")
            payouts = {h: host_totals[h]["Net Final Payout"] for h in hosts if host_totals[h]["Net Final Payout"] > 0}
            if payouts:
                fig_donut = go.Figure(data=[go.Pie(labels=list(payouts.keys()), values=list(payouts.values()), hole=.5,
                                                   marker_colors=['#E50914', '#564d4d', '#B0B0B0'])])
                fig_donut.update_layout(margin=dict(t=30, b=0, l=0, r=0), template="plotly_dark", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_donut, use_container_width=True)
            else:
                st.write("No payout data generated yet.")

# ---------------------------------------------------------
# PAGE 2: HOST PERFORMANCE PORTALS
# ---------------------------------------------------------
elif nav_selection == "🧑‍✈️ Host Performance":
    st.header("Host Portals")
    
    selected_host = st.selectbox("Select Host to View Performance", hosts)
    
    st.markdown(f"### Performance Review: **{selected_host}**")
    
    h_data = host_totals[selected_host]
    
    pc1, pc2, pc3 = st.columns(3)
    pc1.metric("Total Final Payout", f"${h_data['Net Final Payout']:,.2f}")
    pc2.metric("Passive Income (Pool Split)", f"${h_data['Pool Split']:,.2f}")
    pc3.metric("Active Income (Tasks Completed)", f"${(h_data['Cleaning'] + h_data['Delivery']):,.2f}", f"{h_data['Tasks_Count']} Tasks")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Detail Breakdown Table
    st.subheader("Income Breakdown")
    breakdown_df = pd.DataFrame([
        {"Category": "Vehicle Pool Split", "Amount": h_data["Pool Split"]},
        {"Category": "Cleaning Fees Earned", "Amount": h_data["Cleaning"]},
        {"Category": "Delivery Fees Earned", "Amount": h_data["Delivery"]},
        {"Category": "Out-of-Pocket Reimbursed", "Amount": h_data["Reimbursed"]}
    ])
    st.dataframe(
        breakdown_df, 
        column_config={"Amount": st.column_config.NumberColumn(format="$%.2f")}, 
        hide_index=True, use_container_width=True
    )

# ---------------------------------------------------------
# PAGE 3: OPERATIONS DESK
# ---------------------------------------------------------
elif nav_selection == "🛠️ Operations Desk":
    st.header("Operations Desk")
    st.caption("Log physical work, cleaning, and expenses to ensure accurate accounting.")
    
    t1, t2, t3 = st.tabs(["🧼 Cleanings", "💸 Expenses", "🚚 Deliveries"])
    
    def render_edit_form(log, idx, log_type):
        with st.container(border=True):
            st.write(f"**✏️ Editing Log {idx+1}**")
            c1, c2 = st.columns(2)
            with c1:
                e_date = st.date_input("Date", pd.to_datetime(log.get("Date", datetime.now())).date(), key=f"e_{log_type}d_{idx}")
                e_host = st.selectbox("Host", hosts, index=hosts.index(log.get("Host")) if log.get("Host") in hosts else 0, key=f"e_{log_type}h_{idx}")
                opts = [v["name"] for v in st.session_state.vehicles] + (["General Fleet"] if log_type == "exp" else (["General / Unspecified"] if log_type == "cln" else []))
                e_car = st.selectbox("Vehicle", opts, index=opts.index(log.get("Vehicle")) if log.get("Vehicle") in opts else 0, key=f"e_{log_type}v_{idx}")
            with c2:
                e_guest = st.selectbox("Guest", guest_list, index=guest_list.index(log.get("Guest")) if log.get("Guest") in guest_list else 0, key=f"e_{log_type}g_{idx}")
                e_amt = st.number_input("Amount ($)", min_value=0.0, value=float(log.get("Amount ($)", 0.0)), step=5.0, key=f"e_{log_type}a_{idx}")
                e_extra = st.text_input("Desc/Location", log.get("Description", log.get("Location", "")), key=f"e_{log_type}x_{idx}") if log_type in ["exp", "del"] else None
            
            s1, s2 = st.columns([1, 5])
            if s1.button("💾 Save", key=f"e_{log_type}save_{idx}"):
                new_data = {"Date": e_date.strftime("%Y-%m-%d"), "Host": e_host, "Vehicle": e_car, "Guest": e_guest, "Amount ($)": e_amt}
                if log_type == "exp": new_data["Description"] = e_extra
                if log_type == "del": new_data["Location"] = e_extra
                
                if log_type == "cln": st.session_state.cleaning_logs[idx] = new_data
                elif log_type == "exp": st.session_state.expense_logs[idx] = new_data
                elif log_type == "del": st.session_state.delivery_logs[idx] = new_data
                
                st.session_state.edit_mode = {"type": None, "index": None}
                st.rerun()
            if s2.button("❌ Cancel", key=f"e_{log_type}cancel_{idx}"):
                st.session_state.edit_mode = {"type": None, "index": None}
                st.rerun()

    # --- CLEANING TAB ---
    with t1:
        with st.container(border=True):
            st.subheader("Log New Cleaning")
            cc1, cc2, cc3 = st.columns([2, 2, 1])
            with cc1:
                cleaner = st.selectbox("Cleaner", hosts)
                clean_car = st.selectbox("Cleaned Vehicle", [v["name"] for v in st.session_state.vehicles] + ["General / Unspecified"])
            with cc2:
                clean_d = st.date_input("Cleaning Date", datetime.now())
                clean_guest = st.selectbox("Renter (Guest)", guest_list)
            with cc3:
                clean_fee = st.number_input("Fee ($)", min_value=0.0, value=st.session_state.clean_fee_val, step=5.0)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕ Log Cleaning", use_container_width=True):
                    st.session_state.cleaning_logs.append({"Date": clean_d.strftime("%Y-%m-%d"), "Host": cleaner, "Vehicle": clean_car, "Guest": clean_guest, "Amount ($)": clean_fee})
                    st.rerun()
        
        if st.session_state.cleaning_logs:
            st.markdown("#### Cleaning History")
            to_del = None
            for i, log in enumerate(st.session_state.cleaning_logs):
                if st.session_state.edit_mode == {"type": "cln", "index": i}:
                    render_edit_form(log, i, "cln")
                else:
                    c1, c2, c3, c4, c5, c6 = st.columns([2, 2, 2, 2, 1, 1])
                    c1.write(f"📅 {log.get('Date')}")
                    c2.write(f"👤 {log.get('Host')}")
                    c3.write(f"🚗 {log.get('Vehicle')}")
                    c4.write(f"💵 ${log.get('Amount ($)'):.2f}")
                    if c5.button("✏️", key=f"edit_c_{i}"):
                        st.session_state.edit_mode = {"type": "cln", "index": i}
                        st.rerun()
                    if c6.button("🗑️", key=f"del_c_{i}"): to_del = i
            if to_del is not None:
                st.session_state.cleaning_logs.pop(to_del)
                st.rerun()

    # --- EXPENSES TAB ---
    with t2:
        with st.container(border=True):
            st.subheader("Log Out-of-Pocket Expense")
            ec1, ec2, ec3 = st.columns([2, 2, 1])
            with ec1:
                payer = st.selectbox("Payer Host", hosts)
                exp_car = st.selectbox("Expense Vehicle", [v["name"] for v in st.session_state.vehicles] + ["General Fleet"])
                exp_desc = st.text_input("Description", "Gas / Wash / Maintenance")
            with ec2:
                exp_d = st.date_input("Expense Date", datetime.now())
                exp_guest = st.selectbox("Renter (Guest)", guest_list, key="exp_guest")
            with ec3:
                exp_amt = st.number_input("Cost ($)", min_value=0.0, value=0.0, step=5.0)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕ Log Expense", use_container_width=True) and exp_amt > 0:
                    st.session_state.expense_logs.append({"Date": exp_d.strftime("%Y-%m-%d"), "Host": payer, "Vehicle": exp_car, "Guest": exp_guest, "Description": exp_desc, "Amount ($)": exp_amt})
                    st.rerun()
        
        if st.session_state.expense_logs:
            st.markdown("#### Expense History")
            to_del = None
            for i, log in enumerate(st.session_state.expense_logs):
                if st.session_state.edit_mode == {"type": "exp", "index": i}:
                    render_edit_form(log, i, "exp")
                else:
                    c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1.5, 2, 2.5, 1, 0.5, 0.5])
                    c1.write(f"📅 {log.get('Date')}")
                    c2.write(f"👤 {log.get('Host')}")
                    c3.write(f"🚗 {log.get('Vehicle')}")
                    c4.write(f"📝 {log.get('Description')}")
                    c5.write(f"💵 ${log.get('Amount ($)'):.2f}")
                    if c6.button("✏️", key=f"edit_e_{i}"):
                        st.session_state.edit_mode = {"type": "exp", "index": i}
                        st.rerun()
                    if c7.button("🗑️", key=f"del_e_{i}"): to_del = i
            if to_del is not None:
                st.session_state.expense_logs.pop(to_del)
                st.rerun()

    # --- DELIVERIES TAB ---
    with t3:
        with st.container(border=True):
            st.subheader("Log Vehicle Delivery")
            dc1, dc2, dc3 = st.columns([2, 2, 1])
            with dc1:
                driver = st.selectbox("Driver", hosts)
                del_car = st.selectbox("Delivered Vehicle", [v["name"] for v in st.session_state.vehicles])
                del_loc = st.text_input("Location", "Airport / Address")
            with dc2:
                del_d = st.date_input("Delivery Date", datetime.now())
                del_guest = st.selectbox("Renter (Guest)", guest_list, key="del_guest")
            with dc3:
                del_fee = st.number_input("Fee ($)", min_value=0.0, value=st.session_state.delivery_fee_val, step=5.0)
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("➕ Log Delivery", use_container_width=True) and del_fee > 0:
                    st.session_state.delivery_logs.append({"Date": del_d.strftime("%Y-%m-%d"), "Host": driver, "Vehicle": del_car, "Guest": del_guest, "Location": del_loc, "Amount ($)": del_fee})
                    st.rerun()
        
        if st.session_state.delivery_logs:
            st.markdown("#### Delivery History")
            to_del = None
            for i, log in enumerate(st.session_state.delivery_logs):
                if st.session_state.edit_mode == {"type": "del", "index": i}:
                    render_edit_form(log, i, "del")
                else:
                    c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 1.5, 2, 2.5, 1, 0.5, 0.5])
                    c1.write(f"📅 {log.get('Date')}")
                    c2.write(f"👤 {log.get('Host')}")
                    c3.write(f"🚗 {log.get('Vehicle')}")
                    c4.write(f"📍 {log.get('Location')}")
                    c5.write(f"💵 ${log.get('Amount ($)'):.2f}")
                    if c6.button("✏️", key=f"edit_d_{i}"):
                        st.session_state.edit_mode = {"type": "del", "index": i}
                        st.rerun()
                    if c7.button("🗑️", key=f"del_d_{i}"): to_del = i
            if to_del is not None:
                st.session_state.delivery_logs.pop(to_del)
                st.rerun()

# ---------------------------------------------------------
# PAGE 4: SETTINGS & DATA
# ---------------------------------------------------------
elif nav_selection == "⚙️ Settings & Data":
    st.header("Settings & Data Management")
    
    with st.expander("📂 Upload & Sync Turo Earnings Data", expanded=True):
        uploaded_file = st.file_uploader("Drop your Turo CSV export here", type=["csv", "tsv", "txt"])
        
        def parse_currency(val):
            if pd.isna(val): return 0.0
            s = str(val).strip().replace('-', '').replace('US$', '').replace('$', '').replace(',', '')
            try: return -float(s) if '-' in str(val) else float(s)
            except ValueError: return 0.0

        if uploaded_file is not None:
            if st.session_state.get("uploaded_filename") != uploaded_file.name:
                try:
                    content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
                    uploaded_file.seek(0)
                    sep = '\t' if '\t' in content.split('\n')[0] else ','
                    df_raw = pd.read_csv(uploaded_file, sep=sep, header=None)
                    
                    parsed_trips = []
                    for _, row in df_raw.iterrows():
                        if len(row) < 10: continue
                        v_text = f"{str(row.iloc[2])} {str(row.iloc[3])}".lower()
                        
                        matched_car, car_splits = "Unmatched Vehicles", {h: 1.0/len(hosts) for h in hosts}
                        for v_config in st.session_state.vehicles:
                            if v_config["name"].lower() in v_text and v_config["name"].strip():
                                matched_car, car_splits = v_config["name"], v_config["splits"]
                                break
                        
                        try: s_date, e_date = pd.to_datetime(row.iloc[6]).date(), pd.to_datetime(row.iloc[7]).date()
                        except: s_date, e_date = None, None
                        
                        pos, neg = 0.0, 0.0
                        if len(row) > 16:
                            for idx in range(16, len(row)-1):
                                v = parse_currency(row.iloc[idx])
                                if v > 0: pos += v
                                elif v < 0: neg += v
                                
                        parsed_trips.append({
                            "Guest": str(row.iloc[1]), "Vehicle": matched_car, "Start Date": s_date, "End Date": e_date,
                            "Status": str(row.iloc[10]).strip(), "Trip Earnings": parse_currency(row.iloc[15]) if len(row) > 15 else 0.0,
                            "Extras & Reimbursements": pos, "Fees & Deductions": neg, "Net Total": parse_currency(row.iloc[-1]), "Splits": car_splits
                        })

                    new_df = pd.DataFrame(parsed_trips)
                    if not st.session_state.trips_data.empty:
                        st.session_state.trips_data = pd.concat([st.session_state.trips_data, new_df]).drop_duplicates(subset=["Guest", "Start Date", "Net Total"], keep="last")
                    else:
                        st.session_state.trips_data = new_df
                        
                    st.session_state.uploaded_filename = uploaded_file.name
                    st.success("✅ File parsed successfully! Use the sidebar button to save to cloud.")
                except Exception as e:
                    st.error(f"Upload error: {e}")

    with st.expander("🚘 Global Fleet Settings (Ownership Splits)"):
        c1, c2 = st.columns(2)
        with c1:
            if st.button("➕ Add Vehicle"):
                new_id = max([c["id"] for c in st.session_state.vehicles], default=0) + 1
                st.session_state.vehicles.append({"id": new_id, "name": f"Vehicle {new_id}", "splits": {hosts[0]: 33, hosts[1]: 33, hosts[2]: 34}})
                st.rerun()
        
        to_del = None
        for i, car in enumerate(st.session_state.vehicles):
            st.markdown(f"**{car['name']}**")
            cols = st.columns(len(hosts) + 2)
            new_name = cols[0].text_input("Name", car["name"], key=f"nm_{car['id']}", label_visibility="collapsed")
            if new_name != car["name"]: car["name"] = new_name
            
            for j, h in enumerate(hosts):
                val = cols[j+1].number_input(h, min_value=0, max_value=100, value=int(car["splits"].get(h,0)), key=f"sp_{car['id']}_{h}")
                car["splits"][h] = val
            if cols[-1].button("🗑️", key=f"rm_{car['id']}"): to_del = i
            st.markdown("---")
        if to_del is not None:
            st.session_state.vehicles.pop(to_del)
            st.rerun()

    with st.expander("⚙️ System Config (Hosts & Default Fees)"):
        c1, c2, c3 = st.columns(3)
        st.session_state.host_a_val = c1.text_input("Host 1", st.session_state.host_a_val)
        st.session_state.host_b_val = c2.text_input("Host 2", st.session_state.host_b_val)
        st.session_state.host_c_val = c3.text_input("Host 3", st.session_state.host_c_val)
        
        c4, c5 = st.columns(2)
        st.session_state.clean_fee_val = c4.number_input("Default Cleaning Fee ($)", value=st.session_state.clean_fee_val, step=5.0)
        st.session_state.delivery_fee_val = c5.number_input("Default Delivery Fee ($)", value=st.session_state.delivery_fee_val, step=5.0)

    st.subheader("Raw Master Ledger")
    if not st.session_state.trips_data.empty:
        st.dataframe(
            st.session_state.trips_data[["Guest", "Vehicle", "Start Date", "End Date", "Status", "Trip Earnings", "Extras & Reimbursements", "Fees & Deductions", "Net Total"]],
            column_config={
                "Trip Earnings": st.column_config.NumberColumn(format="$%.2f"),
                "Extras & Reimbursements": st.column_config.NumberColumn(format="$%.2f"),
                "Fees & Deductions": st.column_config.NumberColumn(format="$%.2f"),
                "Net Total": st.column_config.NumberColumn(format="$%.2f"),
            },
            hide_index=True, use_container_width=True
        )
