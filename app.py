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

# Initialize default vehicles in session state if not already present
if "vehicles" not in st.session_state:
    st.session_state.vehicles = [
        {"id": 0, "name": "Dodge Journey", "splits": {host_a: 36, host_b: 64, host_c: 0}},
        {"id": 1, "name": "Honda Civic", "splits": {host_a: 0, host_b: 80, host_c: 20}},
    ]

# Track highest assigned ID for unique key generation
if "next_id" not in st.session_state:
    st.session_state.next_id = len(st.session_state.vehicles)

# Button to dynamically add a new car
if st.sidebar.button("➕ Add New Vehicle"):
    new_id = st.session_state.next_id
    st.session_state.vehicles.append(
        {"id": new_id, "name": f"Vehicle {new_id + 1}", "splits": {host_a: 33, host_b: 33, host_c: 34}}
    )
    st.session_state.next_id += 1
    st.rerun()

# Render controls for each vehicle
vehicle_configs = []
to_delete = None

for idx, car in enumerate(st.session_state.vehicles):
    car_id = car["id"]
    with st.sidebar.expander(f"🚗 {car['name']}", expanded=False):
        # Allow editing name and persist immediately to session state
        new_name = st.text_input(
            "Vehicle Name", 
            value=car["name"], 
            key=f"car_name_{car_id}"
        )
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
            car["splits"][h] = val  # Update split in session state
            splits[h] = val / 100.0
            total_pct += val
        
        if total_pct != 100:
            st.warning(f"⚠️ Total split is currently **{total_pct}%** (should equal 100%).")
        
        # Delete button for individual car
        if st.button("🗑️ Delete Vehicle", key=f"delete_{car_id}"):
            to_delete = idx

        vehicle_configs.append({"name": car["name"], "splits": splits})

# Handle vehicle deletion outside loop to avoid state disruption
if to_delete is not None:
    st.session_state.vehicles.pop(to_delete)
    st.rerun()

# 2. File Upload Interface
uploaded_file = st.file_uploader("Drag and drop your Turo Earnings CSV here", type=["csv"])

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

# 4. Data Processing Core
if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Initialize calculations
        totals = {h: {"Trip Earnings": 0.0, "Cleaning Bonuses": 0.0, "Expenses": 0.0, "Net Final Payout": 0.0} for h in hosts}

        # Process each row in the Turo CSV
        for _, row in df.iterrows():
            vehicle_text = str(row.get('Vehicle', '')).lower()
            earnings = float(row.get('Earnings', 0.0))
            
            matched = False
            for v_config in vehicle_configs:
                # Check if the vehicle name matches the CSV row
                if v_config["name"].lower() in vehicle_text and v_config["name"].strip() != "":
                    for h, split in v_config["splits"].items():
                        totals[h]["Trip Earnings"] += earnings * split
                    matched = True
                    break
            
            # Fallback split if vehicle doesn't match any listed cars
            if not matched:
                split_even = 1.0 / len(hosts)
                for h in hosts:
                    totals[h]["Trip Earnings"] += earnings * split_even

        # Process manual items
        if add_clean:
            totals[cleaner]["Cleaning Bonuses"] += clean_bonus
            
        if add_expense:
            totals[payer]["Expenses"] += expense_amt

        # Compute ultimate payouts
        for h in hosts:
            totals[h]["Net Final Payout"] = (
                totals[h]["Trip Earnings"] + totals[h]["Cleaning Bonuses"] - totals[h]["Expenses"]
            )

        # Display Live Dashboard
        st.write("---")
        st.success(f"📊 Dashboard Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        summary_df = pd.DataFrame(totals).T
        st.dataframe(summary_df.style.format("${:,.2f}"))

    except Exception as e:
        st.error(f"Error reading file structure. Technical details: {e}")
else:
    st.info("💡 Awaiting Turo CSV file upload to calculate live payouts.")
