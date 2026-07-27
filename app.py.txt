import streamlit as st
import pandas as pd
from datetime import datetime

# Set up clean user interface
st.set_page_config(page_title="Multi-Host Turo Splitter", layout="wide")
st.title("🚗 Multi-Host Turo Fleet Dashboard")
st.subheader("Upload your Turo CSV to instantly split earnings, calculate bonuses, and track expenses.")

# 1. Sidebar Configurations for custom user names & splits
st.sidebar.header("⚙️ Host Configurations & Splits")
host_a = st.sidebar.text_input("Host A Name", "Alice")
host_b = st.sidebar.text_input("Host B Name", "Bob")
host_c = st.sidebar.text_input("Host C Name", "Charlie")

st.sidebar.subheader("Vehicle Ownership Assignment")
car1_owner = st.sidebar.selectbox("Tesla Model 3 Owner", [host_a, host_b, host_c], index=0)
car1_split = st.sidebar.slider("Tesla Owner Cut %", 0, 100, 70) / 100

car2_owner = st.sidebar.selectbox("Honda Civic Owner", [host_a, host_b, host_c], index=1)
car2_split = st.sidebar.slider("Honda Owner Cut %", 0, 100, 80) / 100

# 2. File Upload Interface
uploaded_file = st.file_uploader("Drag and drop your Turo Earnings CSV here", type=["csv"])

# 3. Create Manual Inputs for Cleaning and Expense tracking
st.write("---")
col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🧼 Active Cleaning Log")
    cleaner = st.selectbox("Who cleaned a vehicle?", [host_a, host_b, host_c])
    clean_bonus = st.number_input("Cleaning Bonus Amount ($)", min_value=0.0, value=25.0, step=5.0)
    add_clean = st.checkbox("Apply cleaning bonus to final payout?")

with col2:
    st.markdown("### 💸 Active Expense Log")
    payer = st.selectbox("Who paid out of pocket?", [host_a, host_b, host_c])
    expense_amt = st.number_input("Expense Bill Amount ($)", min_value=0.0, value=0.0, step=5.0)
    add_expense = st.checkbox("Deduct expense from final payout?")

# 4. Data Processing Core
if uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Initialize calculations
        totals = {
            host_a: {"Trip Earnings": 0.0, "Cleaning Bonuses": 0.0, "Expenses": 0.0, "Net Final Payout": 0.0},
            host_b: {"Trip Earnings": 0.0, "Cleaning Bonuses": 0.0, "Expenses": 0.0, "Net Final Payout": 0.0},
            host_c: {"Trip Earnings": 0.0, "Cleaning Bonuses": 0.0, "Expenses": 0.0, "Net Final Payout": 0.0}
        }
        
        # Match Turo vehicle strings to assigned user settings
        for _, row in df.iterrows():
            vehicle = str(row.get('Vehicle', '')).lower()
            earnings = float(row.get('Earnings', 0.0))
            
            if 'tesla' in vehicle:
                totals[car1_owner]["Trip Earnings"] += earnings * car1_split
                manager = host_b if car1_owner == host_a else host_a
                totals[manager]["Trip Earnings"] += earnings * (1 - car1_split)
            elif 'honda' in vehicle:
                totals[car2_owner]["Trip Earnings"] += earnings * car2_split
                manager = host_c if car2_owner == host_b else host_b
                totals[manager]["Trip Earnings"] += earnings * (1 - car2_split)
            else:
                totals[host_a]["Trip Earnings"] += earnings * 0.5
                totals[host_b]["Trip Earnings"] += earnings * 0.5

        # Process manual items
        if add_clean:
            totals[cleaner]["Cleaning Bonuses"] += clean_bonus
        if add_expense:
            totals[payer]["Expenses"] += expense_amt

        # Compute ultimate payouts
        for host in totals:
            totals[host]["Net Final Payout"] = totals[host]["Trip Earnings"] + totals[host]["Cleaning Bonuses"] - totals[host]["Expenses"]

        # Display Live Dashboard
        st.write("---")
        st.success(f"📊 Dashboard Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        summary_df = pd.DataFrame(totals).T
        st.dataframe(summary_df.style.format("${:,.2f}"))
        
    except Exception as e:
        st.error(f"Error reading file structure. Technical details: {e}")
else:
    st.info("💡 Awaiting Turo CSV file upload to calculate live payouts.")
