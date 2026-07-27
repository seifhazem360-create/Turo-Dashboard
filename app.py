import streamlit as st
import pandas as pd
from datetime import datetime
import json
from supabase import create_client, Client

# Page Configuration
st.set_page_config(page_title="Fleet Command | Turo Fleet Dashboard", page_icon="🚗", layout="wide")

st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: 600; font-size: 16px; }
</style>
""", unsafe_allow_html=True)

st.title("🚗 FleetCommand Dashboard")
st.caption("Multi-Host Turo Fleet Analytics, Revenue Splitting & Operations Manager")

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

def load_cloud_state():
    if not supabase:
        return None
    try:
        res = supabase.table("app_state").select("data").eq("id", 1).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["data"]
    except Exception:
        pass
    return None

def save_cloud_state():
    if not supabase:
        return
    try:
        state_payload = {
            "host_a": st.session_state.get("host_a_val", "AH"),
            "host_b": st.session_state.get("host_b_val", "SA"),
            "host_c": st.session_state.get("host_c_val", "OM"),
            "default_clean_fee": st.session_state.get("clean_fee_val", 25.0),
            "default_delivery_fee": st.session_state.get("delivery_fee_val", 30.0),
            "vehicles": st.session_state.get("vehicles", []),
            "cleaning_logs": st.session_state.get("cleaning_logs", []),
            "expense_logs": st.session_state.get("expense_logs", []),
            "delivery_logs": st.session_state.get("delivery_logs", []),
        }
        supabase.table("app_state").upsert({"id": 1, "data": state_payload}).execute()
    except Exception:
        pass

cloud_data = load_cloud_state() or {}

# ---------------------------------------------------------
# 1. SIDEBAR CONFIGURATIONS & DEFAULTS
# ---------------------------------------------------------
st.sidebar.header("⚙️ Host Configuration")
saved_host_a = cloud_data.get("host_a", "AH")
saved_host_b = cloud_data.get("host_b", "SA")
saved_host_c = cloud_data.get("host_c", "OM")

host_a = st.sidebar.text_input("Host A Name", saved_host_a, key="host_a_val")
host_b = st.sidebar.text_input("Host B Name", saved_host_b, key="host_b_val")
host_c = st.sidebar.text_input("Host C Name", saved_host_c, key="host_c_val")

hosts = [host_a, host_b, host_c]

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Operational Task Defaults")
saved_clean_fee = cloud_data.get("default_clean_fee", 25.0)
saved_delivery_fee = cloud_data.get("default_delivery_fee", 30.0)

default_clean_fee = st.sidebar.number_input("Default Cleaning Fee ($)", min_value=0.0, value=float(saved_clean_fee), step=5.0, key="clean_fee_val")
default_delivery_fee = st.sidebar.number_input("Default Delivery Fee ($)", min_value=0.0, value=float(saved_delivery_fee), step=5.0, key="delivery_fee_val")

st.sidebar.markdown("---")
st.sidebar.header("🚘 Fleet Ownership & Splits")

def init_default_vehicles():
    return [
        {"id": 0, "name": "Dodge Journey", "splits": {host_a: 50, host_b: 50, host_c: 0}},
        {"id": 1, "name": "Kia Forte", "splits": {host_a: 0, host_b: 0, host_c: 100}},
    ]

if "vehicles" not in st.session_state:
    if "vehicles" in cloud_data and cloud_data["vehicles"]:
        st.session_state.vehicles = cloud_data["vehicles"]
    else:
        st.session_state.vehicles = init_default_vehicles()

if "cleaning_logs" not in st.session_state:
    st.session_state.cleaning_logs = cloud_data.get("cleaning_logs", [])

if "expense_logs" not in st.session_state:
    st.session_state.expense_logs = cloud_data.get("expense_logs", [])

if "delivery_logs" not in st.session_state:
    st.session_state.delivery_logs = cloud_data.get("delivery_logs", [])

if "trips_data" not in st.session_state:
    st.session_state.trips_data = pd.DataFrame()

if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None

for idx, car in enumerate(st.session_state.vehicles):
    if "id" not in car:
        car["id"] = idx

if "next_id" not in st.session_state:
    st.session_state.next_id = max([c["id"] for c in st.session_state.vehicles], default=0) + 1

col_add, col_reset = st.sidebar.columns(2)
with col_add:
    if st.sidebar.button("➕ Add Car"):
        new_id = st.session_state.next_id
        st.session_state.vehicles.append(
            {"id": new_id, "name": f"Vehicle {new_id + 1}", "splits": {host_a: 33, host_b: 33, host_c: 34}}
        )
        st.session_state.next_id += 1
        save_cloud_state()
        st.rerun()

with col_reset:
    if st.sidebar.button("🔄 Reset Fleet"):
        st.session_state.vehicles = init_default_vehicles()
        save_cloud_state()
        st.rerun()

vehicle_configs = []
to_delete = None

for idx, car in enumerate(st.session_state.vehicles):
    car_id = car["id"]
    with st.sidebar.expander(f"🚗 {car['name']}", expanded=False):
        new_name = st.text_input("Vehicle Name", value=car["name"], key=f"car_name_{car_id}")
        if new_name != car["name"]:
            car["name"] = new_name
            save_cloud_state()
            st.rerun()

        st.markdown("**Host Split Shares %**")
        splits = {}
        total_pct = 0
        for h in hosts:
            default_val = car["splits"].get(h, 0)
            val = st.number_input(f"{h} Cut %", min_value=0, max_value=100, value=int(default_val), key=f"split_{car_id}_{h}")
            car["splits"][h] = val
            splits[h] = val / 100.0
            total_pct += val
        
        if total_pct != 100:
            st.warning(f"⚠️ Split is **{total_pct}%** (needs to be 100%).")
        
        if st.button("🗑️ Remove Car", key=f"delete_{car_id}"):
            to_delete = idx

        vehicle_configs.append({"name": car["name"], "splits": splits})

if to_delete is not None:
    st.session_state.vehicles.pop(to_delete)
    save_cloud_state()
    st.rerun()

# Automatically save cloud state when sidebar defaults change
save_cloud_state()

# ---------------------------------------------------------
# 2. FILE UPLOADER & DYNAMIC PARSER
# ---------------------------------------------------------
uploaded_file = st.file_uploader("📂 Upload Turo Earnings File (CSV / TSV)", type=["csv", "tsv", "txt"])

def parse_currency(val):
    if pd.isna(val):
        return 0.0
    s = str(val).strip()
    is_negative = '-' in s
    s = s.replace('-', '').replace('US$', '').replace('$', '').replace(',', '').strip()
    try:
        amount = float(s)
        return -amount if is_negative else amount
    except ValueError:
        return 0.0

def parse_date(date_str):
    try:
        return pd.to_datetime(date_str).date()
    except Exception:
        return None

if uploaded_file is not None:
    is_new_file = st.session_state.uploaded_filename != uploaded_file.name
    is_old_structure = not st.session_state.trips_data.empty and "Fees & Deductions" not in st.session_state.trips_data.columns

    if is_new_file or is_old_structure:
        try:
            content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
            uploaded_file.seek(0)
            sep = '\t' if '\t' in content.split('\n')[0] else ','
            df_raw = pd.read_csv(uploaded_file, sep=sep, header=None)

            parsed_trips = []
            for _, row in df_raw.iterrows():
                if len(row) < 10:
                    continue
                
                guest_name = str(row.iloc[1])
                vehicle_text = f"{str(row.iloc[2])} {str(row.iloc[3])}".lower()
                start_date = parse_date(row.iloc[6])
                end_date = parse_date(row.iloc[7])
                status = str(row.iloc[10]).strip()
                
                trip_earnings = parse_currency(row.iloc[15]) if len(row) > 15 else 0.0
                net_total = parse_currency(row.iloc[-1])
                
                pos_reimbursements = 0.0
                neg_deductions = 0.0
                if len(row) > 16:
                    for col_idx in range(16, len(row) - 1):
                        val = parse_currency(row.iloc[col_idx])
                        if val > 0:
                            pos_reimbursements += val
                        elif val < 0:
                            neg_deductions += val
                
                matched_car = "Unmatched Vehicles"
                car_splits = {h: 1.0 / len(hosts) for h in hosts}
                
                for v_config in vehicle_configs:
                    if v_config["name"].lower() in vehicle_text and v_config["name"].strip() != "":
                        matched_car = v_config["name"]
                        car_splits = v_config["splits"]
                        break

                parsed_trips.append({
                    "Guest": guest_name,
                    "Vehicle": matched_car,
                    "Start Date": start_date,
                    "End Date": end_date,
                    "Status": status,
                    "Trip Earnings": trip_earnings,
                    "Extras & Reimbursements": pos_reimbursements,
                    "Fees & Deductions": neg_deductions,
                    "Net Total": net_total,
                    "Splits": car_splits
                })

            st.session_state.trips_data = pd.DataFrame(parsed_trips)
            st.session_state.uploaded_filename = uploaded_file.name
            st.success("✅ File processed and synced to cloud!")
        except Exception as e:
            st.error(f"Error parsing uploaded file: {e}")

# ---------------------------------------------------------
# 3. MAIN NAVIGATION TABS
# ---------------------------------------------------------
nav_tab1, nav_tab2, nav_tab3, nav_tab4 = st.tabs([
    "📊 Overview & Analytics", 
    "📑 Trip Ledger & Details", 
    "📝 Task & Expense Operations", 
    "⚙️ Fleet Management"
])

filtered_df = pd.DataFrame()
if not st.session_state.trips_data.empty:
    st.markdown("### 🔍 Filters")
    f_col1, f_col2, f_col3 = st.columns(3)
    
    with f_col1:
        min_d = st.session_state.trips_data["Start Date"].dropna().min() if not st.session_state.trips_data["Start Date"].dropna().empty else datetime.now().date()
        max_d = st.session_state.trips_data["End Date"].dropna().max() if not st.session_state.trips_data["End Date"].dropna().empty else datetime.now().date()
        selected_dates = st.date_input("Date Range", [min_d, max_d])
        
    with f_col2:
        car_options = ["All Vehicles"] + list(st.session_state.trips_data["Vehicle"].unique())
        selected_car = st.selectbox("Filter by Vehicle", car_options)
        
    with f_col3:
        status_options = ["All Statuses"] + list(st.session_state.trips_data["Status"].unique())
        selected_status = st.selectbox("Filter by Trip Status", status_options)

    filtered_df = st.session_state.trips_data.copy()
    if len(selected_dates) == 2:
        filtered_df = filtered_df[
            (filtered_df["Start Date"] >= selected_dates[0]) & 
            (filtered_df["Start Date"] <= selected_dates[1])
        ]
    if selected_car != "All Vehicles":
        filtered_df = filtered_df[filtered_df["Vehicle"] == selected_car]
    if selected_status != "All Statuses":
        filtered_df = filtered_df[filtered_df["Status"] == selected_status]

# ---------------------------------------------------------
# TAB 1: OVERVIEW & ANALYTICS
# ---------------------------------------------------------
with nav_tab1:
    if not filtered_df.empty:
        total_gross = filtered_df["Net Total"].sum()
        total_trips = len(filtered_df)
        completed_trips = len(filtered_df[filtered_df["Status"].str.lower() == "completed"])
        
        host_totals = {
            h: {
                "Pool Split Earnings": 0.0,
                "Cleaning Earned": 0.0,
                "Delivery Earned": 0.0,
                "Expenses Reimbursed": 0.0,
                "Net Final Payout": 0.0,
                "Tasks Completed": 0
            } for h in hosts
        }

        vehicle_task_deductions = {}
        for log in st.session_state.cleaning_logs:
            v = log["Vehicle"]
            vehicle_task_deductions[v] = vehicle_task_deductions.get(v, 0.0) + log["Amount ($)"]
            if log["Host"] in host_totals:
                host_totals[log["Host"]]["Tasks Completed"] += 1
                host_totals[log["Host"]]["Cleaning Earned"] += log["Amount ($)"]

        for log in st.session_state.delivery_logs:
            v = log["Vehicle"]
            vehicle_task_deductions[v] = vehicle_task_deductions.get(v, 0.0) + log["Amount ($)"]
            if log["Host"] in host_totals:
                host_totals[log["Host"]]["Tasks Completed"] += 1
                host_totals[log["Host"]]["Delivery Earned"] += log["Amount ($)"]

        for log in st.session_state.expense_logs:
            v = log["Vehicle"]
            vehicle_task_deductions[v] = vehicle_task_deductions.get(v, 0.0) + log["Amount ($)"]
            if log["Host"] in host_totals:
                host_totals[log["Host"]]["Expenses Reimbursed"] += log["Amount ($)"]

        total_tasks_cost = sum(vehicle_task_deductions.values())

        vehicle_gross_totals = filtered_df.groupby("Vehicle")["Net Total"].sum().to_dict()
        
        for v_config in vehicle_configs:
            v_name = v_config["name"]
            v_gross = vehicle_gross_totals.get(v_name, 0.0)
            v_deduction = vehicle_task_deductions.get(v_name, 0.0)
            v_net_pool = max(0.0, v_gross - v_deduction)
            
            for h, pct in v_config["splits"].items():
                if h in host_totals:
                    host_totals[h]["Pool Split Earnings"] += v_net_pool * pct

        general_deduction = vehicle_task_deductions.get("General Fleet", 0.0) + vehicle_task_deductions.get("General / Unspecified", 0.0)
        if general_deduction > 0:
            for h in hosts:
                host_totals[h]["Pool Split Earnings"] -= (general_deduction / len(hosts))

        for h in hosts:
            host_totals[h]["Net Final Payout"] = (
                host_totals[h]["Pool Split Earnings"] +
                host_totals[h]["Cleaning Earned"] +
                host_totals[h]["Delivery Earned"] +
                host_totals[h]["Expenses Reimbursed"]
            )

        st.markdown("---")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Filtered Gross Revenue", f"${total_gross:,.2f}")
        m2.metric("Total Trips", f"{total_trips} ({completed_trips} Completed)")
        m3.metric("Tasks & Expense Pool", f"${total_tasks_cost:,.2f}")
        m4.metric("Net Host Payout Pool", f"${sum(h['Net Final Payout'] for h in host_totals.values()):,.2f}")

        st.markdown("### 📊 Host Payout Breakdown")
        summary_df = pd.DataFrame(host_totals).T.reset_index()
        summary_df.rename(columns={"index": "Host Name"}, inplace=True)
        st.dataframe(
            summary_df,
            column_config={
                "Pool Split Earnings": st.column_config.NumberColumn(format="$%.2f"),
                "Cleaning Earned": st.column_config.NumberColumn(format="$%.2f"),
                "Delivery Earned": st.column_config.NumberColumn(format="$%.2f"),
                "Expenses Reimbursed": st.column_config.NumberColumn(format="$%.2f"),
                "Net Final Payout": st.column_config.NumberColumn(format="$%.2f"),
            },
            hide_index=True,
            use_container_width=True
        )

        st.markdown("### 🏎️ Vehicle Revenue Performance")
        car_perf = filtered_df.groupby("Vehicle")["Net Total"].agg(["count", "sum"]).reset_index()
        car_perf.columns = ["Vehicle Name", "Trips", "Gross Revenue"]
        st.dataframe(
            car_perf,
            column_config={
                "Gross Revenue": st.column_config.NumberColumn(format="$%.2f"),
            },
            hide_index=True,
            use_container_width=True
        )

    else:
        st.info("💡 Upload a Turo Earnings CSV to view analytics.")

# ---------------------------------------------------------
# TAB 2: TRIP LEDGER & DETAILS
# ---------------------------------------------------------
with nav_tab2:
    if not filtered_df.empty:
        st.markdown("### 📑 Master Trip Ledger")
        st.dataframe(
            filtered_df[["Guest", "Vehicle", "Start Date", "End Date", "Status", "Trip Earnings", "Extras & Reimbursements", "Fees & Deductions", "Net Total"]],
            column_config={
                "Trip Earnings": st.column_config.NumberColumn(format="$%.2f"),
                "Extras & Reimbursements": st.column_config.NumberColumn(format="$%.2f"),
                "Fees & Deductions": st.column_config.NumberColumn(format="$%.2f"),
                "Net Total": st.column_config.NumberColumn(format="$%.2f"),
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("💡 Awaiting CSV upload to populate trip details.")

# ---------------------------------------------------------
# TAB 3: TASK & EXPENSE OPERATIONS
# ---------------------------------------------------------
with nav_tab3:
    st.markdown("### 📝 Active Operational Logs")
    t1, t2, t3 = st.tabs(["🧼 Cleaning Tasks", "💸 Out-of-Pocket Expenses", "🚚 Vehicle Deliveries"])

    with t1:
        with st.form("clean_form", clear_on_submit=True):
            c1, c2, c3 = st.columns([2, 2, 1])
            with c1:
                cleaner = st.selectbox("Host Cleaner", hosts)
                clean_car = st.selectbox("Vehicle", [v["name"] for v in vehicle_configs] + ["General / Unspecified"])
            with c2:
                clean_fee = st.number_input("Cleaning Fee ($)", min_value=0.0, value=default_clean_fee, step=5.0)
                clean_d = st.date_input("Date", datetime.now())
            with c3:
                st.write("")
                st.write("")
                if st.form_submit_button("➕ Log Cleaning"):
                    st.session_state.cleaning_logs.append({
                        "Date": clean_d.strftime("%Y-%m-%d"),
                        "Host": cleaner,
                        "Vehicle": clean_car,
                        "Amount ($)": clean_fee
                    })
                    save_cloud_state()
                    st.rerun()

        if st.session_state.cleaning_logs:
            to_del = None
            for i, log in enumerate(st.session_state.cleaning_logs):
                col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
                col1.write(f"📅 {log['Date']}")
                col2.write(f"👤 {log['Host']}")
                col3.write(f"🚗 {log['Vehicle']}")
                col4.write(f"💵 ${log['Amount ($)']:.2f}")
                if col5.button("🗑️", key=f"del_c_{i}"):
                    to_del = i
            if to_del is not None:
                st.session_state.cleaning_logs.pop(to_del)
                save_cloud_state()
                st.rerun()

    with t2:
        with st.form("exp_form", clear_on_submit=True):
            e1, e2, e3 = st.columns([2, 2, 1])
            with e1:
                payer = st.selectbox("Payer Host", hosts)
                exp_car = st.selectbox("Vehicle", [v["name"] for v in vehicle_configs] + ["General Fleet"])
            with e2:
                exp_amt = st.number_input("Expense ($)", min_value=0.0, value=0.0, step=5.0)
                exp_desc = st.text_input("Description", "Gas / Tolls / Maintenance")
            with e3:
                st.write("")
                st.write("")
                if st.form_submit_button("➕ Log Expense") and exp_amt > 0:
                    st.session_state.expense_logs.append({
                        "Date": datetime.now().strftime("%Y-%m-%d"),
                        "Host": payer,
                        "Vehicle": exp_car,
                        "Description": exp_desc,
                        "Amount ($)": exp_amt
                    })
                    save_cloud_state()
                    st.rerun()

        if st.session_state.expense_logs:
            to_del = None
            for i, log in enumerate(st.session_state.expense_logs):
                col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 3, 2, 1])
                col1.write(f"📅 {log['Date']}")
                col2.write(f"👤 {log['Host']}")
                col3.write(f"🚗 {log['Vehicle']}")
                col4.write(f"📝 {log['Description']}")
                col5.write(f"💵 ${log['Amount ($)']:.2f}")
                if col6.button("🗑️", key=f"del_e_{i}"):
                    to_del = i
            if to_del is not None:
                st.session_state.expense_logs.pop(to_del)
                save_cloud_state()
                st.rerun()

    with t3:
        with st.form("del_form", clear_on_submit=True):
            d1, d2, d3 = st.columns([2, 2, 1])
            with d1:
                driver = st.selectbox("Delivery Host", hosts)
                del_car = st.selectbox("Vehicle Delivered", [v["name"] for v in vehicle_configs])
            with d2:
                del_fee = st.number_input("Delivery Fee ($)", min_value=0.0, value=default_delivery_fee, step=5.0)
                del_loc = st.text_input("Location", "Airport / Address")
            with d3:
                st.write("")
                st.write("")
                if st.form_submit_button("➕ Log Delivery") and del_fee > 0:
                    st.session_state.delivery_logs.append({
                        "Date": datetime.now().strftime("%Y-%m-%d"),
                        "Host": driver,
                        "Vehicle": del_car,
                        "Location": del_loc,
                        "Amount ($)": del_fee
                    })
                    save_cloud_state()
                    st.rerun()

        if st.session_state.delivery_logs:
            to_del = None
            for i, log in enumerate(st.session_state.delivery_logs):
                col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 3, 2, 1])
                col1.write(f"📅 {log['Date']}")
                col2.write(f"👤 {log['Host']}")
                col3.write(f"🚗 {log['Vehicle']}")
                col4.write(f"📍 {log['Location']}")
                col5.write(f"💵 ${log['Amount ($)']:.2f}")
                if col6.button("🗑️", key=f"del_d_{i}"):
                    to_del = i
            if to_del is not None:
                st.session_state.delivery_logs.pop(to_del)
                save_cloud_state()
                st.rerun()

# ---------------------------------------------------------
# TAB 4: FLEET MANAGEMENT
# ---------------------------------------------------------
with nav_tab4:
    st.markdown("### 🚘 Fleet Overview & Ownership Shares")
    f_cols = st.columns(len(vehicle_configs) if vehicle_configs else 1)
    for idx, v in enumerate(vehicle_configs):
        with f_cols[idx % len(f_cols)]:
            st.subheader(f"🚗 {v['name']}")
            for h, split in v["splits"].items():
                st.write(f"**{h}:** {split*100:.0f}%")
