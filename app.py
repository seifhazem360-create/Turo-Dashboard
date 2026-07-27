import streamlit as st
import pandas as pd
from datetime import datetime

# Set up clean user interface
st.set_page_config(page_title="Multi-Host Turo Splitter", layout="wide")
st.title("🚗 Multi-Host Turo Fleet Dashboard")
st.subheader("Upload your Turo CSV to instantly split earnings, calculate bonuses, and track expenses.")

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

# Safely handle old session states without an 'id'
for idx, car in enumerate(st.session_state.vehicles):
    if "id" not in car:
        car["id"] = idx

if "next_id" not in st.session_state:
    st.session_state.next_id = len(st.session_state.vehicles)

col_add, col_reset = st.sidebar.columns(2)
with col_add:
    if st.button("➕ Add Vehicle"):
        new_id = st.session_state.next_id
        st.session_state.vehicles.append(
            {"id": new_id, "name": f"Vehicle {new_id + 1}", "splits": {host_a: 33, host_b: 33, host_c: 34}}
        )
        st.session_state.next_id += 1
        st.rerun()

with col_reset:
    if st.button("🔄 Reset Fleet"):
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
uploaded_file = st.file_uploader("Drag and drop your Turo Earnings CSV here", type=["csv", "tsv", "txt"])

# 3. Create Manual Inputs for Cleaning and Expense tracking
st.write("---")
col1, col2 = st.columns(2)
with col1:
    st.markdown("### 🧼 Active Cleaning Log")
    cleaner = st.selectbox("Who cleaned a vehicle?", hosts)
    clean_bonus = st.number_input("Cleaning Bonus Amount ($)", min_value=0.0, value=25.0, step=5.0)
    add_clean = st.checkbox("Apply cleaning bonus to final payout?")

with col2:
    st.markdown("### 💸 Active Expense Log")
    payer = st.selectbox("Who paid out of pocket?", hosts)
    expense_amt = st.number_input("Expense Bill Amount ($)", min_value=0.0, value=0.0, step=5.0)
    add_expense = st.checkbox("Deduct expense from final payout?")

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

# 4. Data Processing Core
if uploaded_file is not None:
    try:
        # Detect delimiter (comma or tab)
        content = uploaded_file.getvalue().decode('utf-8', errors='ignore')
        uploaded_file.seek(0)
        sep = '\t' if '\t' in content.split('\n')[0] else ','
        
        df = pd.read_csv(uploaded_file, sep=sep, header=None)

        totals = {h: {"Trip Earnings": 0.0, "Cleaning Bonuses": 0.0, "Expenses": 0.0, "Net Final Payout": 0.0} for h in hosts}
        car_totals = {}

        for _, row in df.iterrows():
            if len(row) < 3:
                continue
            
            # Extract vehicle text from column 3 (index 2) or column 4 (index 3)
            vehicle_text = f"{str(row.iloc[2])} {str(row.iloc[3])}".lower()
            
            # Last column always contains the total net payout for the trip
            earnings = parse_currency(row.iloc[-1])
            
            matched = False
            for v_config in vehicle_configs:
                v_name = v_config["name"].strip()
                if v_name != "" and v_name.lower() in vehicle_text:
                    car_totals[v_name] = car_totals.get(v_name, 0.0) + earnings
                    for h, split in v_config["splits"].items():
                        totals[h]["Trip Earnings"] += earnings * split
                    matched = True
                    break
            
            # Fallback if vehicle isn't matched
            if not matched and earnings != 0:
                car_totals["Unmatched Vehicles"] = car_totals.get("Unmatched Vehicles", 0.0) + earnings
                split_even = 1.0 / len(hosts)
                for h in hosts:
                    totals[h]["Trip Earnings"] += earnings * split_even

        # Process manual items
        if add_clean:
            totals[cleaner]["Cleaning Bonuses"] += clean_bonus
            
        if add_expense:
            totals[payer]["Expenses"] += expense_amt

        # Compute net final payouts
        for h in hosts:
            totals[h]["Net Final Payout"] = (
                totals[h]["Trip Earnings"] + totals[h]["Cleaning Bonuses"] - totals[h]["Expenses"]
            )

        st.write("---")
        st.success(f"📊 Dashboard Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        st.markdown("### 💵 Total Earnings per Vehicle")
        vehicle_df = pd.DataFrame(list(car_totals.items()), columns=["Vehicle", "Total Net Earnings"])
        st.dataframe(vehicle_df.style.format({"Total Net Earnings": "${:,.2f}"}), use_container_width=True)

        st.markdown("### 📊 Host Payout Summary")
        summary_df = pd.DataFrame(totals).T
        st.dataframe(summary_df.style.format("${:,.2f}"), use_container_width=True)

    except Exception as e:
        st.error(f"Error parsing file structure. Technical details: {e}")
else:
    st.info("💡 Awaiting Turo CSV file upload to calculate live payouts.")
