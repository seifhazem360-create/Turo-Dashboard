import streamlit as st
import pandas as pd
from datetime import datetime

# Set up clean user interface
st.set_page_config(page_title="Multi-Host Turo Fleet Dashboard", page_icon="🚗", layout="wide")

st.title("🚗 Multi-Host Turo Fleet Dashboard")
st.caption("Upload your Turo CSV to split earnings, track cleaning, manage expenses, and log delivery fees.")

# ---------------------------------------------------------
# 1. SIDEBAR CONFIGURATIONS & SETTINGS
# ---------------------------------------------------------
st.sidebar.header("⚙️ Host Configurations")
host_a = st.sidebar.text_input("Host A Name", "AH")
host_b = st.sidebar.text_input("Host B Name", "SA")
host_c = st.sidebar.text_input("Host C Name", "OM")

hosts = [host_a, host_b, host_c]

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Task Default Values")
default_clean_fee = st.sidebar.number_input("Default Cleaning Fee ($)", min_value=0.0, value=25.0, step=5.0)
default_delivery_fee = st.sidebar.number_input("Default Delivery Fee ($)", min_value=0.0, value=30.0, step=5.0)

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

# Ensure all stored vehicles have an 'id'
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

if to_delete is not None:
    st.session_state.vehicles.pop(to_delete)
    st.rerun()

# ---------------------------------------------------------
# 2. FILE UPLOADER
# ---------------------------------------------------------
uploaded_file = st.file_uploader("📂 Drag and drop your Turo Earnings CSV here", type=["csv", "tsv", "txt"])

# ---------------------------------------------------------
# 3. INTERACTIVE TASK LOGS (WITH INDIVIDUAL DELETION)
# ---------------------------------------------------------
st.markdown("---")
st.subheader("📝 Fleet Activity & Task Logs")

tab1, tab2, tab3 = st.tabs(["🧼 Cleaning Logs", "💸 Expense Logs", "🚚 Vehicle Delivery Tasks"])

# --- TAB 1: Cleaning Logs ---
with tab1:
    with st.form("cleaning_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            cleaner = st.selectbox("Who cleaned the vehicle?", hosts)
            clean_car = st.selectbox("Vehicle Cleaned", [v["name"] for v in vehicle_configs] + ["General / Unspecified"])
        with c2:
            clean_bonus = st.number_input("Cleaning Fee ($)", min_value=0.0, value=default_clean_fee, step=5.0)
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
            st.success(f"Logged ${clean_bonus:.2f} cleaning task for {cleaner}!")
            st.rerun()

    if st.session_state.cleaning_logs:
        st.write("### Active Cleaning Tasks")
        to_del_clean = None
        for i, log in enumerate(st.session_state.cleaning_logs):
            lc1, lc2, lc3, lc4, lc5 = st.columns([2, 2, 2, 2, 1])
            lc1.write(f"📅 {log['Date']}")
            lc2.write(f"👤 {log['Host']}")
            lc3.write(f"🚗 {log['Vehicle']}")
            lc4.write(f"💵 ${log['Amount ($)']:.2f}")
            if lc5.button("🗑️", key=f"del_clean_{i}"):
                to_del_clean = i
        if to_del_clean is not None:
            st.session_state.cleaning_logs.pop(to_del_clean)
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
            st.success(f"Logged ${expense_amt:.2f} expense for {payer}!")
            st.rerun()

    if st.session_state.expense_logs:
        st.write("### Active Expense Logs")
        to_del_exp = None
        for i, log in enumerate(st.session_state.expense_logs):
            ec1, ec2, ec3, ec4, ec5, ec6 = st.columns([2, 2, 2, 3, 2, 1])
            ec1.write(f"📅 {log['Date']}")
            ec2.write(f"👤 {log['Host']}")
            ec3.write(f"🚗 {log['Vehicle']}")
            ec4.write(f"📝 {log['Description']}")
            ec5.write(f"💵 ${log['Amount ($)']:.2f}")
            if ec6.button("🗑️", key=f"del_exp_{i}"):
                to_del_exp = i
        if to_del_exp is not None:
            st.session_state.expense_logs.pop(to_del_exp)
            st.rerun()

# --- TAB 3: Delivery Logs ---
with tab3:
    with st.form("delivery_form", clear_on_submit=True):
        d1, d2, d3 = st.columns([2, 2, 1])
        with d1:
            driver = st.selectbox("Who delivered vehicle?", hosts)
            delivery_car = st.selectbox("Delivered Vehicle", [v["name"] for v in vehicle_configs])
        with d2:
            delivery_amt = st.number_input("Delivery Fee ($)", min_value=0.0, value=default_delivery_fee, step=5.0)
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
            st.success(f"Logged ${delivery_amt:.2f} delivery task for {driver}!")
            st.rerun()

    if st.session_state.delivery_logs:
        st.write("### Active Delivery Tasks")
        to_del_del = None
        for i, log in enumerate(st.session_state.delivery_logs):
            dc1, dc2, dc3, dc4, dc5, dc6 = st.columns([2, 2, 2, 3, 2, 1])
            dc1.write(f"📅 {log['Date']}")
            dc2.write(f"👤 {log['Host']}")
            dc3.write(f"🚗 {log['Vehicle']}")
            dc4.write(f"📍 {log['Location']}")
            dc5.write(f"💵 ${log['Amount ($)']:.2f}")
            if dc6.button("🗑️", key=f"del_del_{i}"):
                to_del_del = i
        if to_del_del is not None:
            st.session_state.delivery_logs.pop(to_del_del)
            st.rerun()

# Helper function to parse currency
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

# ---------------------------------------------------------
# 4. DATA PROCESSING & ANALYTICS DASHBOARD
# ---------------------------------------------------------
if uploaded_file is not None:
    try:
        content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
        uploaded_file.seek(0)
        sep = '\t' if '\t' in content.split('\n')[0] else ','
        
        df = pd.read_csv(uploaded_file, sep=sep, header=None)

        # Parse detailed rows for CSV table
        detailed_trips = []
        car_analytics = {}
        total_fleet_gross = 0.0

        # Totals per host
        host_totals = {
            h: {
                "Pool Split Earnings": 0.0,
                "Cleaning Earned": 0.0,
                "Delivery Earned": 0.0,
                "Expenses Reimbursed": 0.0,
                "Net Final Payout": 0.0,
                "Total Tasks Done": 0
            } for h in hosts
        }

        # Calculate Tasks Completed Count
        for log in st.session_state.cleaning_logs:
            if log["Host"] in host_totals:
                host_totals[log["Host"]]["Total Tasks Done"] += 1
                host_totals[log["Host"]]["Cleaning Earned"] += log["Amount ($)"]

        for log in st.session_state.delivery_logs:
            if log["Host"] in host_totals:
                host_totals[log["Host"]]["Total Tasks Done"] += 1
                host_totals[log["Host"]]["Delivery Earned"] += log["Amount ($)"]

        for log in st.session_state.expense_logs:
            if log["Host"] in host_totals:
                host_totals[log["Host"]]["Expenses Reimbursed"] += log["Amount ($)"]

        total_task_costs = (
            sum(l["Amount ($)"] for l in st.session_state.cleaning_logs) +
            sum(l["Amount ($)"] for l in st.session_state.delivery_logs) +
            sum(l["Amount ($)"] for l in st.session_state.expense_logs)
        )

        # Process each trip
        for idx, row in df.iterrows():
            if len(row) < 10:
                continue
            
            guest_name = str(row.iloc[1])
            vehicle_text = f"{str(row.iloc[2])} {str(row.iloc[3])}".lower()
            trip_status = str(row.iloc[10])
            
            # Extract financial details safely
            trip_earnings = parse_currency(row.iloc[15]) if len(row) > 15 else 0.0
            extras = parse_currency(row.iloc[27]) if len(row) > 27 else 0.0
            reimbursements = parse_currency(row.iloc[29]) if len(row) > 29 else 0.0
            total_net = parse_currency(row.iloc[-1])
            
            total_fleet_gross += total_net
            
            # Identify car
            matched_car = "Unmatched Vehicles"
            car_splits = {h: 1.0 / len(hosts) for h in hosts}
            
            for v_config in vehicle_configs:
                if v_config["name"].lower() in vehicle_text and v_config["name"].strip() != "":
                    matched_car = v_config["name"]
                    car_splits = v_config["splits"]
                    break

            if matched_car not in car_analytics:
                car_analytics[matched_car] = {"Trips": 0, "Gross Revenue": 0.0}
            
            car_analytics[matched_car]["Trips"] += 1
            car_analytics[matched_car]["Gross Revenue"] += total_net

            detailed_trips.append({
                "Guest Name": guest_name,
                "Vehicle": matched_car,
                "Status": trip_status,
                "Trip Earnings ($)": trip_earnings,
                "Extras ($)": extras,
                "Reimbursements ($)": reimbursements,
                "Net Total ($)": total_net
            })

            # Distribute earnings logic: Pool = Gross - Tasks/Expenses
            pool_for_trip = total_net
            for h, split in car_splits.items():
                host_totals[h]["Pool Split Earnings"] += pool_for_trip * split

        # Adjust Pool split: Deduct tasks/expenses from the overall pool proportionally or evenly
        if total_fleet_gross > 0 and total_task_costs > 0:
            task_deduction_per_host = total_task_costs / len(hosts)
            for h in hosts:
                host_totals[h]["Pool Split Earnings"] -= task_deduction_per_host

        # Calculate Net Final Payouts
        total_net_payouts = 0.0
        for h in hosts:
            net = (
                host_totals[h]["Pool Split Earnings"] +
                host_totals[h]["Cleaning Earned"] +
                host_totals[h]["Delivery Earned"] +
                host_totals[h]["Expenses Reimbursed"]
            )
            host_totals[h]["Net Final Payout"] = net
            total_net_payouts += net

        # ---------------------------------------------------------
        # DISPLAY PERFORMANCE METRICS & DASHBOARD
        # ---------------------------------------------------------
        st.markdown("---")
        st.subheader("📈 Performance Overview & Big Metrics")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(label="Total Fleet Gross Earnings", value=f"${total_fleet_gross:,.2f}")
        m2.metric(label="Total Net Host Payouts", value=f"${total_net_payouts:,.2f}")
        m3.metric(label="Deducted Task & Expense Pool", value=f"${total_task_costs:,.2f}")
        m4.metric(label="Total Fleet Trips", value=len(detailed_trips))

        st.markdown("### 🏎️ Vehicle Performance Summary")
        car_df = pd.DataFrame([
            {"Vehicle": k, "Completed Trips": v["Trips"], "Gross Revenue": v["Gross Revenue"]}
            for k, v in car_analytics.items()
        ])
        st.dataframe(
            car_df,
            column_config={
                "Gross Revenue": st.column_config.NumberColumn(format="$%.2f"),
            },
            hide_index=True,
            use_container_width=True
        )

        st.markdown("### 📊 Host Payout & Task Summary")
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
                "Total Tasks Done": st.column_config.NumberColumn(format="%d Tasks"),
            },
            hide_index=True,
            use_container_width=True
        )

        st.markdown("### 📑 Detailed Trip & Reimbursement Export")
        trips_df = pd.DataFrame(detailed_trips)
        st.dataframe(
            trips_df,
            column_config={
                "Trip Earnings ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Extras ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Reimbursements ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Net Total ($)": st.column_config.NumberColumn(format="$%.2f"),
            },
            hide_index=True,
            use_container_width=True
        )

    except Exception as e:
        st.error(f"Error processing file. Technical details: {e}")
else:
    st.info("💡 Awaiting Turo CSV file upload to calculate live payouts.")
