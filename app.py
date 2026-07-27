import streamlit as st
import pandas as pd
from datetime import datetime

# Set up clean user interface
st.set_page_config(page_title="Multi-Host Turo Fleet Dashboard", page_icon="🚗", layout="wide")

st.title("🚗 Multi-Host Turo Fleet Dashboard")
st.caption("Upload your Turo CSV to split earnings, track cleaning, manage expenses, and log delivery fees.")

# 1. Sidebar Configurations for custom user names & splits
st.sidebar.header("⚙️ Host Configurations")
host_a = st.sidebar.text_input("Host A Name", "AH")
host_b = st.sidebar.text_input("Host B Name", "SA")
host_c = st.sidebar.text_input("Host C Name", "OM")

hosts = [host_a, host_b, host_c]

st.sidebar.markdown("---")
st.sidebar.header("🚘 Fleet & Ownership Splits")

# Initialize default vehicles in session state if missing
def init_default_vehicles():
    st.session_state.vehicles = [
        {"id": 0, "name": "Dodge Journey", "splits": {host_a: 50, host_b: 50, host_c: 0}},
        {"id": 1, "name": "Kia Forte", "splits": {host_a: 0, host_b: 0, host_c: 100}},
    ]
    st.session_state.next_id = 2

if "vehicles" not in st.session_state:
    init_default_vehicles()

# Session State for Activity Logs
if "cleaning_logs" not in st.session_state:
    st.session_state.cleaning_logs = []

if "expense_logs" not in st.session_state:
    st.session_state.expense_logs = []

if "delivery_logs" not in st.session_state:
    st.session_state.delivery_logs = []

# Safely handle old session states without an 'id'
for idx, car in enumerate(st.session_state.vehicles):
    if "id" not in car:
        car["id"] = idx

if "next_id" not in st.session_state:
    st.session_state.next_id = len(st.session_state.vehicles)

col_add, col_reset = st.sidebar.columns(2)
with col_add:
    if st.sidebar.button("➕ Add Vehicle"):
        new_id = st.session_state.next_id
        st.session_state.vehicles.append(
            {"id": new_id, "name": f"Vehicle {new_id + 1}", "splits": {host_a: 33, host_b: 33, host_c: 34}}
        )
        st.session_state.next_id += 1
        st.rerun()

with col_reset:
    if st.sidebar.button("🔄 Reset Fleet"):
        init_default_vehicles()
        st.rerun()

# Render controls for each vehicle
vehicle_configs = []
to_delete = None

for idx, car in enumerate(st.session_state.vehicles):
    car_id = car["id"]
    with st.sidebar.expander(f"🚗 {car['name']}", expanded=False):
        new_name = st.text_input("Vehicle Name", value=car["name"], key=f"car_name_{car_id}")
        if new_name != car["name"]:
            car["name"] = new_name
            st.rerun()

        st.markdown("**Host Equity / Split %**")
        
        splits = {}
        total_pct = 0
        for h in hosts:
            default_val = car["splits"].get(h, 0)
            val = st.number_input(
                f"{h} Cut %", 
                min_value=0, 
                max_value=100, 
                value=default_val, 
                key=f"split_{car_id}_{h}"
            )
            car["splits"][h] = val
            splits[h] = val / 100.0
            total_pct += val
        
        if total_pct != 100:
            st.warning(f"⚠️ Total split is currently **{total_pct}%** (should equal 100%).")
        
        if st.button("🗑️ Delete Vehicle", key=f"delete_{car_id}"):
            to_delete = idx

        vehicle_configs.append({"name": car["name"], "splits": splits})

# Handle vehicle deletion
if to_delete is not None:
    st.session_state.vehicles.pop(to_delete)
    st.rerun()

# 2. File Upload Interface
uploaded_file = st.file_uploader("📂 Drag and drop your Turo Earnings CSV here", type=["csv", "tsv", "txt"])

# 3. Interactive Task Logs & Manual Inputs
st.markdown("---")
st.subheader("📝 Fleet Activity & Manual Task Logs")

tab1, tab2, tab3 = st.tabs(["🧼 Cleaning Logs", "💸 Expense Logs", "🚚 Vehicle Delivery Tasks"])

# --- TAB 1: Cleaning Logs ---
with tab1:
    with st.form("cleaning_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            cleaner = st.selectbox("Who cleaned the vehicle?", hosts)
            clean_car = st.selectbox("Vehicle Cleaned", [v["name"] for v in vehicle_configs] + ["General / Unspecified"])
        with c2:
            clean_bonus = st.number_input("Cleaning Fee / Bonus ($)", min_value=0.0, value=25.0, step=5.0)
            clean_date = st.date_input("Date Completed", datetime.now())
        with c3:
            st.write("")
            st.write("")
            submit_clean = st.form_submit_button("➕ Add Cleaning Log")
            
        if submit_clean:
            st.session_state.cleaning_logs.append({
                "Date": clean_date.strftime("%Y-%m-%d"),
                "Host": cleaner,
                "Vehicle": clean_car,
                "Amount ($)": clean_bonus
            })
            st.success(f"Added ${clean_bonus:.2f} cleaning log for {cleaner}!")
            st.rerun()

    if st.session_state.cleaning_logs:
        df_clean = pd.DataFrame(st.session_state.cleaning_logs)
        st.dataframe(df_clean.style.format({"Amount ($)": "${:,.2f}"}), use_container_width=True)
        if st.button("🗑️ Clear All Cleaning Logs"):
            st.session_state.cleaning_logs = []
            st.rerun()

# --- TAB 2: Expense Logs ---
with tab2:
    with st.form("expense_form", clear_on_submit=True):
        e1, e2, e3 = st.columns([2, 2, 1])
        with e1:
            payer = st.selectbox("Who paid out of pocket?", hosts)
            expense_car = st.selectbox("Vehicle for Expense", [v["name"] for v in vehicle_configs] + ["General Fleet"])
        with e2:
            expense_amt = st.number_input("Expense Amount ($)", min_value=0.0, value=0.0, step=5.0)
            expense_note = st.text_input("Expense Description / Category", "Gas, Maintenance, Tolls")
        with e3:
            st.write("")
            st.write("")
            submit_expense = st.form_submit_button("➕ Add Expense Log")
            
        if submit_expense and expense_amt > 0:
            st.session_state.expense_logs.append({
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Host": payer,
                "Vehicle": expense_car,
                "Description": expense_note,
                "Amount ($)": expense_amt
            })
            st.success(f"Added ${expense_amt:.2f} expense log for {payer}!")
            st.rerun()

    if st.session_state.expense_logs:
        df_exp = pd.DataFrame(st.session_state.expense_logs)
        st.dataframe(df_exp.style.format({"Amount ($)": "${:,.2f}"}), use_container_width=True)
        if st.button("🗑️ Clear All Expense Logs"):
            st.session_state.expense_logs = []
            st.rerun()

# --- TAB 3: Delivery Logs ---
with tab3:
    with st.form("delivery_form", clear_on_submit=True):
        d1, d2, d3 = st.columns([2, 2, 1])
        with d1:
            driver = st.selectbox("Who delivered/dropped off vehicle?", hosts)
            delivery_car = st.selectbox("Delivered Vehicle", [v["name"] for v in vehicle_configs])
        with d2:
            delivery_amt = st.number_input("Delivery Fee Earned ($)", min_value=0.0, value=30.0, step=5.0)
            delivery_loc = st.text_input("Delivery Location", "Airport / Custom Address")
        with d3:
            st.write("")
            st.write("")
            submit_delivery = st.form_submit_button("➕ Add Delivery Task")
            
        if submit_delivery and delivery_amt > 0:
            st.session_state.delivery_logs.append({
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Host": driver,
                "Vehicle": delivery_car,
                "Location": delivery_loc,
                "Amount ($)": delivery_amt
            })
            st.success(f"Added ${delivery_amt:.2f} delivery fee for {driver}!")
            st.rerun()

    if st.session_state.delivery_logs:
        df_del = pd.DataFrame(st.session_state.delivery_logs)
        st.dataframe(df_del.style.format({"Amount ($)": "${:,.2f}"}), use_container_width=True)
        if st.button("🗑️ Clear All Delivery Logs"):
            st.session_state.delivery_logs = []
            st.rerun()


# Function to safely convert Turo currency string to float
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

# 4. Data Processing & Dashboard Display
if uploaded_file is not None:
    try:
        content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
        uploaded_file.seek(0)
        sep = '\t' if '\t' in content.split('\n')[0] else ','
        
        df = pd.read_csv(uploaded_file, sep=sep, header=None)

        totals = {
            h: {
                "Trip Earnings": 0.0, 
                "Cleaning Bonuses": 0.0, 
                "Delivery Fees": 0.0, 
                "Expenses": 0.0, 
                "Net Final Payout": 0.0
            } for h in hosts
        }
        car_totals = {}
        total_fleet_raw = 0.0

        for _, row in df.iterrows():
            if len(row) < 3:
                continue
            
            vehicle_text = f"{str(row.iloc[2])} {str(row.iloc[3])}".lower()
            earnings = parse_currency(row.iloc[-1])
            total_fleet_raw += earnings
            
            matched = False
            for v_config in vehicle_configs:
                v_name = v_config["name"].strip()
                if v_name != "" and v_name.lower() in vehicle_text:
                    car_totals[v_name] = car_totals.get(v_name, 0.0) + earnings
                    for h, split in v_config["splits"].items():
                        totals[h]["Trip Earnings"] += earnings * split
                    matched = True
                    break
            
            if not matched and earnings != 0:
                car_totals["Unmatched Vehicles"] = car_totals.get("Unmatched Vehicles", 0.0) + earnings
                split_even = 1.0 / len(hosts)
                for h in hosts:
                    totals[h]["Trip Earnings"] += earnings * split_even

        # Sum up interactive logs
        for log in st.session_state.cleaning_logs:
            if log["Host"] in totals:
                totals[log["Host"]]["Cleaning Bonuses"] += log["Amount ($)"]

        for log in st.session_state.delivery_logs:
            if log["Host"] in totals:
                totals[log["Host"]]["Delivery Fees"] += log["Amount ($)"]

        for log in st.session_state.expense_logs:
            if log["Host"] in totals:
                totals[log["Host"]]["Expenses"] += log["Amount ($)"]

        # Compute net final payouts
        total_net_payouts = 0.0
        for h in hosts:
            net = (
                totals[h]["Trip Earnings"] 
                + totals[h]["Cleaning Bonuses"] 
                + totals[h]["Delivery Fees"] 
                - totals[h]["Expenses"]
            )
            totals[h]["Net Final Payout"] = net
            total_net_payouts += net

        st.markdown("---")
        st.subheader("📈 Performance Overview & Big Metrics")
        
        # High-Impact KPI Displays
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(label="Total Fleet Gross Earnings", value=f"${total_fleet_raw:,.2f}")
        m2.metric(label="Total Net Host Payouts", value=f"${total_net_payouts:,.2f}")
        m3.metric(label="Active Cleaning Bonuses", value=f"${sum(l['Amount ($)'] for l in st.session_state.cleaning_logs):,.2f}")
        m4.metric(label="Total Logged Expenses", value=f"${sum(l['Amount ($)'] for l in st.session_state.expense_logs):,.2f}")

        st.markdown("### 📊 Host Payout Summary")
        summary_df = pd.DataFrame(totals).T
        st.dataframe(
            summary_df.style.format("${:,.2f}")
            .background_gradient(cmap="Greens", subset=["Net Final Payout"]),
            use_container_width=True
        )

        st.markdown("### 💵 Earnings Breakdown per Vehicle")
        vehicle_df = pd.DataFrame(list(car_totals.items()), columns=["Vehicle Name", "Total Net Revenue"])
        st.dataframe(
            vehicle_df.style.format({"Total Net Revenue": "${:,.2f}"})
            .background_gradient(cmap="Blues", subset=["Total Net Revenue"]),
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Error parsing file structure. Technical details: {e}")
else:
    st.info("💡 Awaiting Turo CSV file upload to calculate live payouts.")
