import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
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

def clean_for_json(obj):
    """Safely clean scalar NaN/NaT values for Supabase JSON upload."""
    if pd.api.types.is_scalar(obj):
        if pd.isna(obj):
            return None
        if isinstance(obj, (float, np.float64, np.float32)) and (np.isnan(obj) or np.isinf(obj)):
            return None
        return obj
    if isinstance(obj, dict):
        return {str(k): clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    return obj

def load_cloud_state():
    if not supabase:
        return None
    try:
        res = supabase.table("app_state").select("data").eq("id", 1).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]["data"]
    except Exception as e:
        print(f"Error loading cloud state: {e}")
    return None

def save_cloud_state():
    if not supabase:
        return False, "Supabase client not initialized."
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
            "uploaded_filename": st.session_state.get("uploaded_filename", None)
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
    st.session_state.uploaded_filename = cloud_data.get("uploaded_filename", None)
    
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

# ---------------------------------------------------------
# 1. SIDEBAR CONFIGURATIONS & DEFAULTS
# ---------------------------------------------------------
st.sidebar.header("☁️ Cloud Sync Control")
if st.sidebar.button("💾 Save All Data & Trips to Cloud", type="primary"):
    success, err_msg = save_cloud_state()
    if success:
        st.sidebar.success("✅ Successfully saved to cloud!")
    else:
        st.sidebar.error(f"❌ Failed: {err_msg}")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Host Configuration")
host_a = st.sidebar.text_input("Host A Name", key="host_a_val")
host_b = st.sidebar.text_input("Host B Name", key="host_b_val")
host_c = st.sidebar.text_input("Host C Name", key="host_c_val")

hosts = [host_a, host_b, host_c]

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Operational Task Defaults")
default_clean_fee = st.sidebar.number_input("Default Cleaning Fee ($)", min_value=0.0, step=5.0, key="clean_fee_val")
default_delivery_fee = st.sidebar.number_input("Default Delivery Fee ($)", min_value=0.0, step=5.0, key="delivery_fee_val")

st.sidebar.markdown("---")
st.sidebar.header("🚘 Fleet Ownership & Splits")

def init_default_vehicles():
    return [
        {"id": 0, "name": "Dodge Journey", "splits": {host_a: 50, host_b: 50, host_c: 0}},
        {"id": 1, "name": "Kia Forte", "splits": {host_a: 0, host_b: 0, host_c: 100}},
    ]

if not st.session_state.vehicles:
    st.session_state.vehicles = init_default_vehicles()

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
        st.rerun()

with col_reset:
    if st.sidebar.button("🔄 Reset Fleet"):
        st.session_state.vehicles = init_default_vehicles()
        st.rerun()

vehicle_configs = []
to_delete = None

for idx, car in enumerate(st.session_state.vehicles):
    car_id = car["id"]
    with st.sidebar.expander(f"🚗 {car['name']}", expanded=False):
        new_name = st.text_input("Vehicle Name", value=car["name"], key=f"car_name_{car_id}")
        if new_name != car["name"]:
            car["name"] = new_name
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
    st.rerun()

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

            new_df = pd.DataFrame(parsed_trips)
            
            if not st.session_state.trips_data.empty and is_new_file:
                combined_df = pd.concat([st.session_state.trips_data, new_df]).drop_duplicates(subset=["Guest", "Start Date", "Net Total"], keep="last")
                st.session_state.trips_data = combined_df
            else:
                st.session_state.trips_data = new_df

            st.session_state.uploaded_filename = uploaded_file.name
            st.success("✅ File processed! Click 'Save All Data & Trips to Cloud' in the sidebar to persist.")
        except Exception as e:
            st.error(f"Error parsing uploaded file: {e}")

# ---------------------------------------------------------
# Dynamic Guest List Builder
# ---------------------------------------------------------
guest_list = ["General / Unspecified"]
if not st.session_state.trips_data.empty and "Guest" in st.session_state.trips_data.columns:
    guests = sorted([str(g) for g in st.session_state.trips_data["Guest"].dropna().unique() if str(g).strip()])
    guest_list.extend(guests)

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
        
        # Tally Cleaning Logs
        for log in st.session_state.cleaning_logs:
            v = log.get("Vehicle", "General / Unspecified")
            amt = log.get("Amount ($)", 0.0)
            host = log.get("Host")
            
            vehicle_task_deductions[v] = vehicle_task_deductions.get(v, 0.0) + amt
            if host in host_totals:
                host_totals[host]["Tasks Completed"] += 1
                host_totals[host]["Cleaning Earned"] += amt

        # Tally Delivery Logs
        for log in st.session_state.delivery_logs:
            v = log.get("Vehicle", "General / Unspecified")
            amt = log.get("Amount ($)", 0.0)
            host = log.get("Host")
            
            vehicle_task_deductions[v] = vehicle_task_deductions.get(v, 0.0) + amt
            if host in host_totals:
                host_totals[host]["Tasks Completed"] += 1
                host_totals[host]["Delivery Earned"] += amt

        # Tally Expense Logs
        for log in st.session_state.expense_logs:
            v = log.get("Vehicle", "General / Unspecified")
            amt = log.get("Amount ($)", 0.0)
            host = log.get("Host")
            
            vehicle_task_deductions[v] = vehicle_task_deductions.get(v, 0.0) + amt
            if host in host_totals:
                host_totals[host]["Expenses Reimbursed"] += amt

        total_tasks_cost = sum(vehicle_task_deductions.values())

        vehicle_gross_totals = filtered_df.groupby("Vehicle")["Net Total"].sum().to_dict()
        
        # Calculate pool split earnings per vehicle
        for v_config in vehicle_configs:
            v_name = v_config["name"]
            v_gross = vehicle_gross_totals.get(v_name, 0.0)
            v_deduction = vehicle_task_deductions.get(v_name, 0.0)
            v_net_pool = max(0.0, v_gross - v_deduction)
            
            for h, pct in v_config["splits"].items():
                if h in host_totals:
                    host_totals[h]["Pool Split Earnings"] += v_net_pool * pct

        # Deduct general unspecified expenses proportionally from the pool
        general_deduction = vehicle_task_deductions.get("General Fleet", 0.0) + vehicle_task_deductions.get("General / Unspecified", 0.0)
        if general_deduction > 0:
            for h in hosts:
                host_totals[h]["Pool Split Earnings"] -= (general_deduction / len(hosts))

        # Calculate Final Net
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
                "Tasks Completed": st.column_config.NumberColumn(format="%d"),
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
                "Trips": st.column_config.NumberColumn(format="%d")
            },
            hide_index=True,
            use_container_width=True
        )

    else:
        st.info("💡 Upload a Turo Earnings CSV and click **Save All Data & Trips to Cloud** in the sidebar.")

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

    # --- CLEANING TASKS ---
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            cleaner = st.selectbox("Host Cleaner", hosts, key="cleaner_input")
            clean_car = st.selectbox("Vehicle", [v["name"] for v in vehicle_configs] + ["General / Unspecified"], key="clean_car_input")
            clean_d = st.date_input("Date", datetime.now(), key="clean_date_input")
        with c2:
            clean_guest = st.selectbox("Related Renter (Guest)", guest_list, key="clean_guest_input")
            clean_fee = st.number_input("Cleaning Fee ($)", min_value=0.0, value=float(default_clean_fee), step=5.0, key="clean_amt_input")

        if st.button("➕ Log Cleaning"):
            st.session_state.cleaning_logs.append({
                "Date": clean_d.strftime("%Y-%m-%d"),
                "Host": cleaner,
                "Vehicle": clean_car,
                "Guest": clean_guest,
                "Amount ($)": clean_fee
            })
            st.success("✅ Cleaning task logged! (Click 'Save All Data' in sidebar to persist)")
            st.rerun()

        if st.session_state.cleaning_logs:
            st.markdown("#### Existing Cleaning Logs")
            to_del = None
            for i, log in enumerate(st.session_state.cleaning_logs):
                # EDIT MODE
                if st.session_state.edit_mode.get("type") == "clean" and st.session_state.edit_mode.get("index") == i:
                    with st.container():
                        st.write(f"**✏️ Editing Log {i+1}**")
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_date = st.date_input("Date", pd.to_datetime(log.get("Date", datetime.now())).date(), key=f"e_cd_{i}")
                            e_host = st.selectbox("Host Cleaner", hosts, index=hosts.index(log.get("Host")) if log.get("Host") in hosts else 0, key=f"e_ch_{i}")
                            car_opts = [v["name"] for v in vehicle_configs] + ["General / Unspecified"]
                            e_car = st.selectbox("Vehicle", car_opts, index=car_opts.index(log.get("Vehicle")) if log.get("Vehicle") in car_opts else 0, key=f"e_cv_{i}")
                        with ec2:
                            e_guest = st.selectbox("Related Renter", guest_list, index=guest_list.index(log.get("Guest")) if log.get("Guest") in guest_list else 0, key=f"e_cg_{i}")
                            e_amt = st.number_input("Cleaning Fee ($)", min_value=0.0, value=float(log.get("Amount ($)", 0.0)), step=5.0, key=f"e_ca_{i}")
                        
                        sc1, sc2 = st.columns([1, 5])
                        if sc1.button("💾 Save", key=f"e_csave_{i}"):
                            st.session_state.cleaning_logs[i] = {
                                "Date": e_date.strftime("%Y-%m-%d"),
                                "Host": e_host,
                                "Vehicle": e_car,
                                "Guest": e_guest,
                                "Amount ($)": e_amt
                            }
                            st.session_state.edit_mode = {"type": None, "index": None}
                            st.rerun()
                        if sc2.button("❌ Cancel", key=f"e_ccancel_{i}"):
                            st.session_state.edit_mode = {"type": None, "index": None}
                            st.rerun()
                        st.markdown("---")
                # VIEW MODE
                else:
                    col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 1, 2, 2, 1, 0.5, 0.5])
                    col1.write(f"📅 {log.get('Date', 'N/A')}")
                    col2.write(f"👤 {log.get('Host', '')}")
                    col3.write(f"🚗 {log.get('Vehicle', '')}")
                    col4.write(f"🧑 {log.get('Guest', 'General / Unspecified')}")
                    col5.write(f"💵 ${log.get('Amount ($)', 0):.2f}")
                    if col6.button("✏️", key=f"edit_c_{i}"):
                        st.session_state.edit_mode = {"type": "clean", "index": i}
                        st.rerun()
                    if col7.button("🗑️", key=f"del_c_{i}"):
                        to_del = i

            if to_del is not None:
                st.session_state.cleaning_logs.pop(to_del)
                st.session_state.edit_mode = {"type": None, "index": None}
                st.rerun()

    # --- EXPENSES ---
    with t2:
        e1, e2 = st.columns(2)
        with e1:
            payer = st.selectbox("Payer Host", hosts, key="payer_input")
            exp_car = st.selectbox("Vehicle", [v["name"] for v in vehicle_configs] + ["General Fleet"], key="exp_car_input")
            exp_d = st.date_input("Date", datetime.now(), key="exp_date_input")
        with e2:
            exp_guest = st.selectbox("Related Renter (Guest)", guest_list, key="exp_guest_input")
            exp_amt = st.number_input("Expense ($)", min_value=0.0, value=0.0, step=5.0, key="exp_amt_input")
            exp_desc = st.text_input("Description", "Gas / Tolls / Maintenance", key="exp_desc_input")

        if st.button("➕ Log Expense") and exp_amt > 0:
            st.session_state.expense_logs.append({
                "Date": exp_d.strftime("%Y-%m-%d"),
                "Host": payer,
                "Vehicle": exp_car,
                "Guest": exp_guest,
                "Description": exp_desc,
                "Amount ($)": exp_amt
            })
            st.success("✅ Expense logged! (Click 'Save All Data' in sidebar to persist)")
            st.rerun()

        if st.session_state.expense_logs:
            st.markdown("#### Existing Expense Logs")
            to_del = None
            for i, log in enumerate(st.session_state.expense_logs):
                # EDIT MODE
                if st.session_state.edit_mode.get("type") == "exp" and st.session_state.edit_mode.get("index") == i:
                    with st.container():
                        st.write(f"**✏️ Editing Log {i+1}**")
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_date = st.date_input("Date", pd.to_datetime(log.get("Date", datetime.now())).date(), key=f"e_ed_{i}")
                            e_host = st.selectbox("Payer Host", hosts, index=hosts.index(log.get("Host")) if log.get("Host") in hosts else 0, key=f"e_eh_{i}")
                            car_opts = [v["name"] for v in vehicle_configs] + ["General Fleet"]
                            e_car = st.selectbox("Vehicle", car_opts, index=car_opts.index(log.get("Vehicle")) if log.get("Vehicle") in car_opts else 0, key=f"e_ev_{i}")
                        with ec2:
                            e_guest = st.selectbox("Related Renter", guest_list, index=guest_list.index(log.get("Guest")) if log.get("Guest") in guest_list else 0, key=f"e_eg_{i}")
                            e_amt = st.number_input("Expense ($)", min_value=0.0, value=float(log.get("Amount ($)", 0.0)), step=5.0, key=f"e_ea_{i}")
                            e_desc = st.text_input("Description", log.get("Description", ""), key=f"e_edesc_{i}")
                        
                        sc1, sc2 = st.columns([1, 5])
                        if sc1.button("💾 Save", key=f"e_esave_{i}"):
                            st.session_state.expense_logs[i] = {
                                "Date": e_date.strftime("%Y-%m-%d"),
                                "Host": e_host,
                                "Vehicle": e_car,
                                "Guest": e_guest,
                                "Description": e_desc,
                                "Amount ($)": e_amt
                            }
                            st.session_state.edit_mode = {"type": None, "index": None}
                            st.rerun()
                        if sc2.button("❌ Cancel", key=f"e_ecancel_{i}"):
                            st.session_state.edit_mode = {"type": None, "index": None}
                            st.rerun()
                        st.markdown("---")
                # VIEW MODE
                else:
                    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 1, 2, 2, 2, 1, 0.5, 0.5])
                    col1.write(f"📅 {log.get('Date', 'N/A')}")
                    col2.write(f"👤 {log.get('Host', '')}")
                    col3.write(f"🚗 {log.get('Vehicle', '')}")
                    col4.write(f"🧑 {log.get('Guest', 'General / Unspecified')}")
                    col5.write(f"📝 {log.get('Description', '')}")
                    col6.write(f"💵 ${log.get('Amount ($)', 0):.2f}")
                    if col7.button("✏️", key=f"edit_e_{i}"):
                        st.session_state.edit_mode = {"type": "exp", "index": i}
                        st.rerun()
                    if col8.button("🗑️", key=f"del_e_{i}"):
                        to_del = i
            
            if to_del is not None:
                st.session_state.expense_logs.pop(to_del)
                st.session_state.edit_mode = {"type": None, "index": None}
                st.rerun()

    # --- VEHICLE DELIVERIES ---
    with t3:
        d1, d2 = st.columns(2)
        with d1:
            driver = st.selectbox("Delivery Host", hosts, key="driver_input")
            del_car = st.selectbox("Vehicle Delivered", [v["name"] for v in vehicle_configs], key="del_car_input")
            del_d = st.date_input("Date", datetime.now(), key="del_date_input")
        with d2:
            del_guest = st.selectbox("Related Renter (Guest)", guest_list, key="del_guest_input")
            del_fee = st.number_input("Delivery Fee ($)", min_value=0.0, value=float(default_delivery_fee), step=5.0, key="del_amt_input")
            del_loc = st.text_input("Location", "Airport / Address", key="del_loc_input")

        if st.button("➕ Log Delivery") and del_fee > 0:
            st.session_state.delivery_logs.append({
                "Date": del_d.strftime("%Y-%m-%d"),
                "Host": driver,
                "Vehicle": del_car,
                "Guest": del_guest,
                "Location": del_loc,
                "Amount ($)": del_fee
            })
            st.success("✅ Delivery logged! (Click 'Save All Data' in sidebar to persist)")
            st.rerun()

        if st.session_state.delivery_logs:
            st.markdown("#### Existing Delivery Logs")
            to_del = None
            for i, log in enumerate(st.session_state.delivery_logs):
                # EDIT MODE
                if st.session_state.edit_mode.get("type") == "del" and st.session_state.edit_mode.get("index") == i:
                    with st.container():
                        st.write(f"**✏️ Editing Log {i+1}**")
                        ec1, ec2 = st.columns(2)
                        with ec1:
                            e_date = st.date_input("Date", pd.to_datetime(log.get("Date", datetime.now())).date(), key=f"e_dd_{i}")
                            e_host = st.selectbox("Delivery Host", hosts, index=hosts.index(log.get("Host")) if log.get("Host") in hosts else 0, key=f"e_dh_{i}")
                            car_opts = [v["name"] for v in vehicle_configs]
                            e_car = st.selectbox("Vehicle Delivered", car_opts, index=car_opts.index(log.get("Vehicle")) if log.get("Vehicle") in car_opts else 0, key=f"e_dv_{i}")
                        with ec2:
                            e_guest = st.selectbox("Related Renter", guest_list, index=guest_list.index(log.get("Guest")) if log.get("Guest") in guest_list else 0, key=f"e_dg_{i}")
                            e_amt = st.number_input("Delivery Fee ($)", min_value=0.0, value=float(log.get("Amount ($)", 0.0)), step=5.0, key=f"e_da_{i}")
                            e_loc = st.text_input("Location", log.get("Location", ""), key=f"e_dloc_{i}")
                        
                        sc1, sc2 = st.columns([1, 5])
                        if sc1.button("💾 Save", key=f"e_dsave_{i}"):
                            st.session_state.delivery_logs[i] = {
                                "Date": e_date.strftime("%Y-%m-%d"),
                                "Host": e_host,
                                "Vehicle": e_car,
                                "Guest": e_guest,
                                "Location": e_loc,
                                "Amount ($)": e_amt
                            }
                            st.session_state.edit_mode = {"type": None, "index": None}
                            st.rerun()
                        if sc2.button("❌ Cancel", key=f"e_dcancel_{i}"):
                            st.session_state.edit_mode = {"type": None, "index": None}
                            st.rerun()
                        st.markdown("---")
                # VIEW MODE
                else:
                    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([2, 1, 2, 2, 2, 1, 0.5, 0.5])
                    col1.write(f"📅 {log.get('Date', 'N/A')}")
                    col2.write(f"👤 {log.get('Host', '')}")
                    col3.write(f"🚗 {log.get('Vehicle', '')}")
                    col4.write(f"🧑 {log.get('Guest', 'General / Unspecified')}")
                    col5.write(f"📍 {log.get('Location', '')}")
                    col6.write(f"💵 ${log.get('Amount ($)', 0):.2f}")
                    if col7.button("✏️", key=f"edit_d_{i}"):
                        st.session_state.edit_mode = {"type": "del", "index": i}
                        st.rerun()
                    if col8.button("🗑️", key=f"del_d_{i}"):
                        to_del = i
            
            if to_del is not None:
                st.session_state.delivery_logs.pop(to_del)
                st.session_state.edit_mode = {"type": None, "index": None}
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
